/* ==========================================================================
   communication.js — Enterprise Real-Time Chat & WebRTC Meeting Client
   KYK Technologies
   ========================================================================== */

(function () {
  'use strict';

  const TOKEN_KEY = 'kyk_admin_token';
  const urlToken = new URLSearchParams(location.search).get('token') || '';
  let parentToken = '';
  try {
    if (window.parent && window.parent !== window && window.parent.gToken) {
      parentToken = window.parent.gToken;
    }
  } catch (e) {}
  let openerToken = '';
  try {
    if (window.opener && window.opener.gToken) {
      openerToken = window.opener.gToken;
    }
  } catch (e) {}

  const gToken = urlToken || localStorage.getItem(TOKEN_KEY) || localStorage.getItem('kyk_user_token') || parentToken || openerToken || '';

  if (gToken) {
    try {
      localStorage.setItem(TOKEN_KEY, gToken);
      localStorage.setItem('kyk_user_token', gToken);
    } catch (e) {}
  }

  if (!gToken) {
    if (window.self === window.top) {
      location.replace('/login.html');
    }
    return;
  }

  // ── Global State ───────────────────────────────────────────────────────────
  let currentUser = null;
  let socket = null;
  let conversations = [];
  let currentConvId = null;
  let messages = [];
  let currentFilter = 'all';
  let onlineUserIds = new Set();
  let replyingTo = null;
  let pendingAttachments = [];
  let typingTimeout = null;

  // WebRTC & Meeting State
  let activeMeeting = null;
  let localStream = null;
  let screenStream = null;
  let peerConnections = {}; // targetSid -> RTCPeerConnection
  let isMicMuted = false;
  let isCamOff = false;
  let isScreenSharing = false;
  let meetingChatOpen = false;

  const RTC_CONFIG = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  };

  // ── DOM Helpers ────────────────────────────────────────────────────────────
  const $ = id => document.getElementById(id);
  const esc = str => String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  async function api(path, opts = {}) {
    const res = await fetch('/api' + path, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + gToken,
        ...(opts.headers || {})
      }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) {
        if (window.self === window.top) {
          localStorage.removeItem(TOKEN_KEY);
          location.replace('/login.html');
        }
      }
      throw new Error(data.error || 'Request failed');
    }
    return data;
  }

  // ── Initialization ─────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', async () => {
    try {
      const meData = await api('/auth/me');
      currentUser = meData.admin || meData.user;
      const role = String(currentUser?.role || '').toLowerCase().trim();
      if (role === 'viewer' || role === 'user') {
        alert('Access Denied: Viewers and general users do not have permissions for chat and meetings.');
        location.replace(role === 'viewer' ? '/viewer-dashboard.html' : '/user-dashboard.html');
        return;
      }
      const roleHomeMap = {
        super_admin: 'admin.html',
        admin: 'admin.html',
        hr_manager: 'hr-dashboard.html',
        hr: 'hr-dashboard.html',
        team_lead: 'team-lead-dashboard.html',
        manager: 'team-lead-dashboard.html',
        employee: 'employee-dashboard.html',
        recruiter: 'recruiter-dashboard.html',
        content_manager: 'content-dashboard.html',
        viewer: 'viewer-dashboard.html',
        client: 'client-portal.html',
        user: 'user-dashboard.html'
      };
      const backLink = $('backToDashLink');
      if (backLink) {
        const dest = roleHomeMap[role] || 'admin.html';
        backLink.href = '/' + dest + (gToken ? '?token=' + encodeURIComponent(gToken) : '');
      }
      renderCurrentUser();
      initSocket();
      loadConversations();
      initUIEvents();
    } catch (err) {
      console.error('Initialization error:', err);
    }
  });

  function renderCurrentUser() {
    const avatar = $('userAvatar');
    if (avatar) avatar.textContent = (currentUser.name || 'U').charAt(0).toUpperCase();
  }

  // ── Socket.IO Real-Time Engine ─────────────────────────────────────────────
  function initSocket() {
    if (typeof io === 'undefined') {
      console.warn('Socket.IO client library not loaded yet.');
      return;
    }

    socket = io({
      auth: { token: gToken },
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000
    });

    socket.on('connect', () => {
      console.log('Connected to real-time communication server.');
      updateConnectionBadge(true);
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from real-time server.');
      updateConnectionBadge(false);
    });

    socket.on('connected_ready', data => {
      if (data.onlineUserIds) {
        onlineUserIds = new Set(data.onlineUserIds);
        updatePresenceIndicators();
      }
    });

    socket.on('user_presence_update', data => {
      if (data.status === 'online') {
        onlineUserIds.add(data.userId);
      } else {
        onlineUserIds.delete(data.userId);
      }
      updatePresenceIndicators();
    });

    socket.on('new_message', msg => {
      if (msg.conversationId === currentConvId) {
        appendMessage(msg);
        scrollToBottom();
        markConversationRead(currentConvId, msg.id);
      }
      updateConversationSnippet(msg);
    });

    socket.on('conversation_alert', data => {
      if (data.conversationId !== currentConvId) {
        loadConversations(); // refresh list & badges
      }
    });

    socket.on('message_edited', msg => {
      if (msg.conversationId === currentConvId) {
        const msgEl = $(`msg-${msg.id}`);
        if (msgEl) {
          const contentEl = msgEl.querySelector('.comm-msg-content');
          if (contentEl) contentEl.innerHTML = formatContent(msg.content) + '<span class="comm-edited-tag">(edited)</span>';
        }
      }
    });

    socket.on('message_deleted', data => {
      if (data.conversationId === currentConvId) {
        const msgEl = $(`msg-${data.id}`);
        if (msgEl) {
          const contentEl = msgEl.querySelector('.comm-msg-content');
          if (contentEl) {
            contentEl.classList.add('deleted');
            contentEl.textContent = 'This message was deleted.';
          }
        }
      }
    });

    socket.on('message_reactions_updated', data => {
      if (data.conversationId === currentConvId) {
        renderReactions(data.messageId, data.reactions);
      }
    });

    socket.on('message_pinned', data => {
      if (data.conversationId === currentConvId) {
        loadPinnedBanner(currentConvId);
      }
    });

    socket.on('user_typing', data => {
      if (data.conversationId === currentConvId) {
        const bar = $('typingBar');
        if (bar) {
          bar.textContent = `${data.userName} is typing…`;
          bar.style.display = 'flex';
        }
      }
    });

    socket.on('user_stopped_typing', data => {
      if (data.conversationId === currentConvId) {
        const bar = $('typingBar');
        if (bar) bar.style.display = 'none';
      }
    });

    // WebRTC Signaling Events
    socket.on('peer_joined_meeting', async data => {
      console.log('Peer joined meeting:', data);
      await createPeerConnection(data.sid, data.userName, true);
    });

    socket.on('webrtc_signal_forward', async data => {
      await handlePeerSignal(data.senderSid, data.senderName, data.payload);
    });

    socket.on('peer_left_meeting', data => {
      removePeerVideo(data.sid);
    });

    socket.on('peer_media_state', data => {
      updatePeerMediaState(data);
    });

    socket.on('meeting_ended_by_host', data => {
      alert(`The meeting was ended by host (${data.endedBy}).`);
      leaveMeetingSession(false);
    });

    socket.on('new_meeting_chat', msg => {
      appendMeetingChatMessage(msg);
    });
  }

  function updateConnectionBadge(online) {
    const badge = $('connBadge');
    if (badge) {
      badge.className = 'comm-presence-dot ' + (online ? 'online' : 'busy');
      badge.title = online ? 'Connected to live chat network' : 'Reconnecting to network…';
    }
  }

  function updatePresenceIndicators() {
    document.querySelectorAll('[data-user-id]').forEach(el => {
      const uid = parseInt(el.dataset.userId, 10);
      const dot = el.querySelector('.comm-presence-dot');
      if (dot) {
        if (onlineUserIds.has(uid)) {
          dot.className = 'comm-presence-dot online';
        } else {
          dot.className = 'comm-presence-dot';
        }
      }
    });
  }

  // ── Conversations ──────────────────────────────────────────────────────────
  async function loadConversations() {
    try {
      conversations = await api('/chat/conversations');
      renderConversationsList();
      if (!currentConvId && conversations.length > 0) {
        selectConversation(conversations[0].id);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }

  function renderConversationsList() {
    const list = $('conversationList');
    if (!list) return;
    list.innerHTML = '';

    const filtered = conversations.filter(c => {
      if (currentFilter === 'all') return true;
      if (currentFilter === 'direct') return c.type === 'direct';
      if (currentFilter === 'group') return c.type === 'group';
      if (currentFilter === 'department') return c.type === 'department';
      if (currentFilter === 'announcement') return c.isAnnouncement || c.type === 'announcement';
      return true;
    });

    if (filtered.length === 0) {
      list.innerHTML = '<div style="padding:24px;text-align:center;color:var(--comm-steel);font-size:0.85rem;">No conversations found.</div>';
      return;
    }

    filtered.forEach(conv => {
      const item = document.createElement('div');
      item.className = `comm-conv-item ${conv.id === currentConvId ? 'active' : ''}`;
      item.id = `conv-item-${conv.id}`;
      item.addEventListener('click', () => selectConversation(conv.id));

      const isDirect = conv.type === 'direct';
      const isAnnounce = conv.isAnnouncement || conv.type === 'announcement';
      const avatarClass = isDirect ? 'direct' : (isAnnounce ? 'announcement' : 'department');

      const isPeerOnline = isDirect && conv.peer && onlineUserIds.has(conv.peer.id);
      const presenceClass = isPeerOnline ? 'online' : '';

      const lastSnippet = conv.lastMessage
        ? esc(conv.lastMessage.content).slice(0, 36) + (conv.lastMessage.content.length > 36 ? '…' : '')
        : 'No messages yet';

      const timeStr = conv.lastMessage ? formatShortTime(conv.lastMessage.createdAt) : '';

      item.innerHTML = `
        <div class="comm-conv-avatar ${avatarClass}">
          ${isDirect ? esc((conv.title || 'U').charAt(0).toUpperCase()) : (isAnnounce ? '📢' : '#')}
          ${isDirect ? `<div class="comm-presence-dot ${presenceClass}"></div>` : ''}
        </div>
        <div class="comm-conv-info">
          <div class="comm-conv-top">
            <span class="comm-conv-name">${esc(conv.title || 'Conversation')}</span>
            <span class="comm-conv-time">${timeStr}</span>
          </div>
          <div class="comm-conv-preview">
            <span>${lastSnippet}</span>
            ${conv.unreadCount > 0 ? `<span class="comm-unread-badge">${conv.unreadCount}</span>` : ''}
          </div>
        </div>
      `;
      list.appendChild(item);
    });
  }

  function updateConversationSnippet(msg) {
    const conv = conversations.find(c => c.id === msg.conversationId);
    if (conv) {
      conv.lastMessage = msg;
      conv.updatedAt = msg.createdAt;
      if (msg.conversationId !== currentConvId && msg.senderId !== currentUser.id) {
        conv.unreadCount = (conv.unreadCount || 0) + 1;
      }
      conversations.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
      renderConversationsList();
    }
  }

  async function selectConversation(convId) {
    if (currentConvId && socket) {
      socket.emit('leave_conversation', { conversationId: currentConvId });
    }

    currentConvId = convId;
    document.querySelectorAll('.comm-conv-item').forEach(el => el.classList.remove('active'));
    const activeEl = $(`conv-item-${convId}`);
    if (activeEl) {
      activeEl.classList.add('active');
      const unreadEl = activeEl.querySelector('.comm-unread-badge');
      if (unreadEl) unreadEl.remove();
    }

    const conv = conversations.find(c => c.id === convId);
    if (conv) {
      conv.unreadCount = 0;
      renderChatHeader(conv);
    }

    if (socket) {
      socket.emit('join_conversation', { conversationId: convId });
    }

    loadPinnedBanner(convId);
    await loadMessages(convId);
    markConversationRead(convId);
  }

  function renderChatHeader(conv) {
    const titleEl = $('chatHeaderTitle');
    const subEl = $('chatHeaderSub');
    const callBtnGroup = $('chatCallBtns');

    if (titleEl) {
      titleEl.innerHTML = `
        <span>${conv.isAnnouncement ? '📢' : (conv.type === 'direct' ? '👤' : '#')}</span>
        <span>${esc(conv.title || 'Chat')}</span>
      `;
    }

    if (subEl) {
      if (conv.type === 'direct' && conv.peer) {
        const isOnline = onlineUserIds.has(conv.peer.id);
        subEl.innerHTML = `
          <span class="comm-role-badge">${esc(conv.peer.role || 'Employee')}</span>
          <span>&bull;</span>
          <span style="color:${isOnline ? 'var(--comm-green)' : 'var(--comm-steel)'}">${isOnline ? 'Active Now' : 'Offline'}</span>
          <span>&bull;</span>
          <span>${esc(conv.peer.email || '')}</span>
        `;
      } else {
        subEl.innerHTML = `
          <span class="comm-role-badge">${esc(conv.type)}</span>
          <span>&bull;</span>
          <span>${esc(conv.description || 'Channel conversation')}</span>
        `;
      }
    }

    // Call buttons available for all conversations
    if (callBtnGroup) {
      callBtnGroup.style.display = 'flex';
    }
  }

  // ── Messages ───────────────────────────────────────────────────────────────
  async function loadMessages(convId) {
    const container = $('messagesContainer');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--comm-steel);">Loading messages…</div>';

    try {
      messages = await api(`/chat/conversations/${convId}/messages?limit=60`);
      container.innerHTML = '';
      if (messages.length === 0) {
        container.innerHTML = `
          <div style="text-align:center;padding:60px 20px;color:var(--comm-steel);">
            <div style="font-size:2.2rem;margin-bottom:10px;">💬</div>
            <h3 style="margin:0 0 8px;font-size:1.1rem;color:var(--comm-ink);">Welcome to the conversation</h3>
            <p style="margin:0;font-size:0.85rem;">This is the start of this channel. Say hello!</p>
          </div>
        `;
        return;
      }

      let lastDate = '';
      messages.forEach(msg => {
        const dStr = new Date(msg.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        if (dStr !== lastDate) {
          const pill = document.createElement('div');
          pill.className = 'comm-date-pill';
          pill.textContent = dStr;
          container.appendChild(pill);
          lastDate = dStr;
        }
        appendMessage(msg, false);
      });
      scrollToBottom();
    } catch (err) {
      container.innerHTML = `<div style="text-align:center;padding:40px;color:var(--comm-red);">${esc(err.message)}</div>`;
    }
  }

  function appendMessage(msg, scroll = true) {
    const container = $('messagesContainer');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'comm-msg-row';
    row.id = `msg-${msg.id}`;

    const isMe = msg.senderId === currentUser.id;
    const canModerate = currentUser.role === 'super_admin' || currentUser.role === 'admin' || currentUser.role === 'hr_manager';
    const canEdit = isMe && !msg.isDeleted;
    const canDelete = (isMe || canModerate) && !msg.isDeleted;

    let replyHtml = '';
    if (msg.replyTo) {
      replyHtml = `
        <div class="comm-reply-quote">
          <b>${esc(msg.replyTo.senderName)}</b>: ${esc(msg.replyTo.content)}
        </div>
      `;
    }

    let attachmentsHtml = '';
    if (msg.attachments && msg.attachments.length > 0) {
      attachmentsHtml = '<div class="comm-attachments-grid">';
      msg.attachments.forEach(att => {
        const isImg = att.fileType.startsWith('image/');
        if (isImg) {
          attachmentsHtml += `
            <a href="${esc(att.fileUrl)}" target="_blank" rel="noopener">
              <img src="${esc(att.fileUrl)}" class="comm-attachment-img" alt="${esc(att.filename)}"/>
            </a>
          `;
        } else {
          attachmentsHtml += `
            <a href="${esc(att.fileUrl)}" class="comm-attachment-card" download="${esc(att.filename)}">
              <span>📎</span>
              <div>
                <b>${esc(att.filename)}</b>
                <div style="font-size:0.7rem;color:var(--comm-steel-dark);">${(att.fileSize / 1024).toFixed(1)} KB</div>
              </div>
            </a>
          `;
        }
      });
      attachmentsHtml += '</div>';
    }

    row.innerHTML = `
      <div class="comm-msg-avatar">${esc((msg.senderName || 'U').charAt(0).toUpperCase())}</div>
      <div class="comm-msg-body">
        <div class="comm-msg-header">
          <span class="comm-msg-sender">${esc(msg.senderName)}</span>
          <span class="comm-role-badge">${esc(msg.senderRole || 'member')}</span>
          <span class="comm-msg-time">${formatTime(msg.createdAt)}</span>
        </div>
        ${replyHtml}
        <div class="comm-msg-content ${msg.isDeleted ? 'deleted' : ''}">
          ${msg.isDeleted ? 'This message was deleted.' : formatContent(msg.content)}
          ${msg.isEdited && !msg.isDeleted ? '<span class="comm-edited-tag">(edited)</span>' : ''}
        </div>
        ${attachmentsHtml}
        <div class="comm-reactions-wrap" id="reactions-${msg.id}"></div>
      </div>
      <div class="comm-msg-toolbar">
        <button class="comm-msg-tool-btn" title="React 👍" onclick="window.commApp.reactToMsg(${msg.id}, '👍')">👍</button>
        <button class="comm-msg-tool-btn" title="React ❤️" onclick="window.commApp.reactToMsg(${msg.id}, '❤️')">❤️</button>
        <button class="comm-msg-tool-btn" title="React 🚀" onclick="window.commApp.reactToMsg(${msg.id}, '🚀')">🚀</button>
        <button class="comm-msg-tool-btn" title="Reply" onclick="window.commApp.replyToMsg(${msg.id})">↩️</button>
        <button class="comm-msg-tool-btn" title="${msg.isPinned ? 'Unpin' : 'Pin'}" onclick="window.commApp.pinMsg(${msg.id})">📌</button>
        ${canEdit ? `<button class="comm-msg-tool-btn" title="Edit" onclick="window.commApp.editMsg(${msg.id})">✏️</button>` : ''}
        ${canDelete ? `<button class="comm-msg-tool-btn" title="Delete" onclick="window.commApp.deleteMsg(${msg.id})">🗑️</button>` : ''}
      </div>
    `;

    container.appendChild(row);
    if (msg.reactions && msg.reactions.length > 0) {
      renderReactions(msg.id, msg.reactions);
    }
    if (scroll) scrollToBottom();
  }

  function renderReactions(msgId, reactions) {
    const wrap = $(`reactions-${msgId}`);
    if (!wrap) return;
    wrap.innerHTML = '';
    if (!reactions || reactions.length === 0) return;

    // Group by emoji
    const grouped = {};
    reactions.forEach(r => {
      if (!grouped[r.emoji]) grouped[r.emoji] = [];
      grouped[r.emoji].push(r);
    });

    Object.entries(grouped).forEach(([emoji, list]) => {
      const chip = document.createElement('div');
      const reactedByMe = list.some(r => r.userId === currentUser.id);
      chip.className = `comm-reaction-chip ${reactedByMe ? 'active' : ''}`;
      chip.innerHTML = `<span>${emoji}</span><span>${list.length}</span>`;
      chip.title = list.map(r => r.userName).join(', ');
      chip.addEventListener('click', () => window.commApp.reactToMsg(msgId, emoji));
      wrap.appendChild(chip);
    });
  }

  async function loadPinnedBanner(convId) {
    const banner = $('pinnedBanner');
    if (!banner) return;
    try {
      const details = await api(`/chat/conversations/${convId}`);
      if (details.pinnedMessages && details.pinnedMessages.length > 0) {
        const topPinned = details.pinnedMessages[0];
        banner.style.display = 'flex';
        banner.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px;overflow:hidden;">
            <span>📌</span>
            <b>Pinned Message:</b>
            <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(topPinned.content)}</span>
          </div>
          <button class="small-btn" onclick="window.commApp.scrollToMsg(${topPinned.id})" style="flex-shrink:0;">View</button>
        `;
      } else {
        banner.style.display = 'none';
      }
    } catch (e) {
      banner.style.display = 'none';
    }
  }

  async function markConversationRead(convId, lastMsgId = null) {
    try {
      await api(`/chat/conversations/${convId}/read`, {
        method: 'POST',
        body: JSON.stringify({ lastMessageId: lastMsgId })
      });
    } catch (e) {}
  }

  async function sendMessage() {
    const textarea = $('composerTextarea');
    if (!textarea || !currentConvId) return;

    const content = textarea.value.trim();
    if (!content && pendingAttachments.length === 0) return;

    try {
      const payload = {
        content: content,
        replyToId: replyingTo ? replyingTo.id : null,
        attachments: pendingAttachments
      };

      textarea.value = '';
      cancelReply();
      clearAttachments();

      if (socket && socket.connected) {
        socket.emit('send_chat_message', {
          conversationId: currentConvId,
          ...payload
        });
      } else {
        // Fallback REST POST
        const saved = await api(`/chat/conversations/${currentConvId}/messages`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        appendMessage(saved);
        scrollToBottom();
      }
    } catch (err) {
      alert('Error sending message: ' + err.message);
    }
  }

  function handleTyping() {
    if (!socket || !currentConvId) return;
    socket.emit('typing_start', { conversationId: currentConvId });
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
      socket.emit('typing_stop', { conversationId: currentConvId });
    }, 2500);
  }

  // ── Meetings (Audio / Video / Screen Share) ────────────────────────────────
  async function startInstantMeeting() {
    try {
      const title = `${currentUser.name}'s Meeting Room`;
      const meet = await api('/meetings/instant', {
        method: 'POST',
        body: JSON.stringify({ title: title })
      });
      // Post link in current conversation
      if (currentConvId) {
        const joinLink = `${location.origin}/communication.html?meeting=${meet.meetingCode}`;
        const inviteMsg = `🚀 I started an instant audio/video meeting: **${meet.title}**\nJoin here: ${joinLink}`;
        api(`/chat/conversations/${currentConvId}/messages`, {
          method: 'POST',
          body: JSON.stringify({ content: inviteMsg })
        });
      }
      openMeetingSession(meet.meetingCode, true);
    } catch (err) {
      alert('Failed to start instant meeting: ' + err.message);
    }
  }

  async function openMeetingSession(meetingCode, isHost = false) {
    const overlay = $('meetingOverlay');
    if (!overlay) return;
    overlay.style.display = 'flex';

    try {
      activeMeeting = await api(`/meetings/${meetingCode}`);
      $('meetingTitleHeader').textContent = activeMeeting.title;
      $('meetingCodeTag').textContent = meetingCode;

      // Start local media stream
      await startLocalMedia();

      // Join socket meeting room
      if (socket) {
        socket.emit('join_meeting_room', { meetingCode: meetingCode });
      }
    } catch (err) {
      alert('Could not join meeting: ' + err.message);
      leaveMeetingSession(false);
    }
  }

  async function startLocalMedia() {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true
      });
      const localVideo = $('localVideoTile');
      if (localVideo) {
        localVideo.srcObject = localStream;
        localVideo.muted = true;
      }
      isMicMuted = false;
      isCamOff = false;
      updateMediaBtnStates();
    } catch (err) {
      console.warn('Could not access camera/mic, falling back to audio only or view only:', err);
      try {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        isCamOff = true;
        updateMediaBtnStates();
      } catch (e) {
        console.warn('View only mode active.');
      }
    }
  }

  async function createPeerConnection(targetSid, targetName, isInitiator) {
    if (peerConnections[targetSid]) return peerConnections[targetSid];

    const pc = new RTCPeerConnection(RTC_CONFIG);
    peerConnections[targetSid] = pc;

    if (localStream) {
      localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
    }

    pc.onicecandidate = evt => {
      if (evt.candidate && socket) {
        socket.emit('webrtc_signal', {
          targetSid: targetSid,
          payload: { candidate: evt.candidate }
        });
      }
    };

    pc.ontrack = evt => {
      const stream = evt.streams[0];
      addOrUpdatePeerVideo(targetSid, targetName, stream);
    };

    if (isInitiator) {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      socket.emit('webrtc_signal', {
        targetSid: targetSid,
        payload: { sdp: pc.localDescription }
      });
    }

    return pc;
  }

  async function handlePeerSignal(senderSid, senderName, payload) {
    let pc = peerConnections[senderSid];
    if (!pc) {
      pc = await createPeerConnection(senderSid, senderName, false);
    }

    if (payload.sdp) {
      await pc.setRemoteDescription(new RTCSessionDescription(payload.sdp));
      if (payload.sdp.type === 'offer') {
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        socket.emit('webrtc_signal', {
          targetSid: senderSid,
          payload: { sdp: pc.localDescription }
        });
      }
    } else if (payload.candidate) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(payload.candidate));
      } catch (e) {
        console.error('Error adding ICE candidate:', e);
      }
    }
  }

  function addOrUpdatePeerVideo(sid, name, stream) {
    const grid = $('meetingVideoGrid');
    if (!grid) return;

    let tile = $(`peer-tile-${sid}`);
    if (!tile) {
      tile = document.createElement('div');
      tile.className = 'comm-video-tile';
      tile.id = `peer-tile-${sid}`;
      tile.innerHTML = `
        <video class="comm-video-el" autoplay playsinline id="peer-video-${sid}"></video>
        <div class="comm-tile-tag">
          <span id="peer-mic-${sid}">🎤</span>
          <span>${esc(name || 'Participant')}</span>
        </div>
      `;
      grid.appendChild(tile);
    }
    const videoEl = $(`peer-video-${sid}`);
    if (videoEl && videoEl.srcObject !== stream) {
      videoEl.srcObject = stream;
    }
  }

  function removePeerVideo(sid) {
    const tile = $(`peer-tile-${sid}`);
    if (tile) tile.remove();
    if (peerConnections[sid]) {
      peerConnections[sid].close();
      delete peerConnections[sid];
    }
  }

  function toggleMic() {
    if (!localStream) return;
    const audioTrack = localStream.getAudioTracks()[0];
    if (audioTrack) {
      audioTrack.enabled = !audioTrack.enabled;
      isMicMuted = !audioTrack.enabled;
      updateMediaBtnStates();
      broadcastMediaState();
    }
  }

  function toggleCam() {
    if (!localStream) return;
    const videoTrack = localStream.getVideoTracks()[0];
    if (videoTrack) {
      videoTrack.enabled = !videoTrack.enabled;
      isCamOff = !videoTrack.enabled;
      updateMediaBtnStates();
      broadcastMediaState();
    }
  }

  async function toggleScreenShare() {
    if (isScreenSharing) {
      stopScreenShare();
    } else {
      try {
        screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
        const screenTrack = screenStream.getVideoTracks()[0];

        // Replace track in all peer connections
        Object.values(peerConnections).forEach(pc => {
          const senders = pc.getSenders();
          const videoSender = senders.find(s => s.track && s.track.kind === 'video');
          if (videoSender) videoSender.replaceTrack(screenTrack);
        });

        const localVideo = $('localVideoTile');
        if (localVideo) {
          localVideo.srcObject = screenStream;
          localVideo.classList.add('screen');
        }

        screenTrack.onended = () => stopScreenShare();
        isScreenSharing = true;
        updateMediaBtnStates();
        broadcastMediaState();
      } catch (err) {
        console.warn('Screen share canceled or denied:', err);
      }
    }
  }

  function stopScreenShare() {
    if (screenStream) {
      screenStream.getTracks().forEach(t => t.stop());
      screenStream = null;
    }
    if (localStream) {
      const origVideoTrack = localStream.getVideoTracks()[0];
      Object.values(peerConnections).forEach(pc => {
        const senders = pc.getSenders();
        const videoSender = senders.find(s => s.track && s.track.kind === 'video');
        if (videoSender && origVideoTrack) videoSender.replaceTrack(origVideoTrack);
      });
      const localVideo = $('localVideoTile');
      if (localVideo) {
        localVideo.srcObject = localStream;
        localVideo.classList.remove('screen');
      }
    }
    isScreenSharing = false;
    updateMediaBtnStates();
    broadcastMediaState();
  }

  function broadcastMediaState() {
    if (socket && activeMeeting) {
      socket.emit('media_state_change', {
        meetingCode: activeMeeting.meetingCode,
        audioEnabled: !isMicMuted,
        videoEnabled: !isCamOff,
        screenSharing: isScreenSharing
      });
    }
  }

  function updatePeerMediaState(data) {
    const micIcon = $(`peer-mic-${data.sid}`);
    if (micIcon) {
      micIcon.textContent = data.audioEnabled ? '🎤' : '🔇';
    }
  }

  function updateMediaBtnStates() {
    const micBtn = $('toggleMicBtn');
    const camBtn = $('toggleCamBtn');
    const screenBtn = $('toggleScreenBtn');

    if (micBtn) {
      micBtn.classList.toggle('active', isMicMuted);
      micBtn.textContent = isMicMuted ? '🔇' : '🎤';
    }
    if (camBtn) {
      camBtn.classList.toggle('active', isCamOff);
      camBtn.textContent = isCamOff ? '🚫' : '📹';
    }
    if (screenBtn) {
      screenBtn.classList.toggle('active', isScreenSharing);
    }
  }

  function leaveMeetingSession(notifyServer = true) {
    if (notifyServer && socket && activeMeeting) {
      socket.emit('leave_meeting_room', { meetingCode: activeMeeting.meetingCode });
    }

    if (localStream) {
      localStream.getTracks().forEach(t => t.stop());
      localStream = null;
    }
    if (screenStream) {
      screenStream.getTracks().forEach(t => t.stop());
      screenStream = null;
    }

    Object.values(peerConnections).forEach(pc => pc.close());
    peerConnections = {};

    const overlay = $('meetingOverlay');
    if (overlay) overlay.style.display = 'none';

    // Clear remote peer tiles
    const grid = $('meetingVideoGrid');
    if (grid) {
      grid.querySelectorAll('.comm-video-tile:not(#localTileContainer)').forEach(el => el.remove());
    }

    activeMeeting = null;
    isScreenSharing = false;
  }

  async function endMeetingForAll() {
    if (!activeMeeting) return;
    if (confirm('End this meeting for all participants?')) {
      try {
        await api(`/meetings/${activeMeeting.meetingCode}/end`, { method: 'POST' });
        leaveMeetingSession(false);
      } catch (err) {
        alert(err.message);
      }
    }
  }

  function sendMeetingChat() {
    const input = $('meetingChatInput');
    if (!input || !activeMeeting || !input.value.trim()) return;

    if (socket) {
      socket.emit('send_meeting_chat', {
        meetingCode: activeMeeting.meetingCode,
        content: input.value.trim()
      });
      input.value = '';
    }
  }

  function appendMeetingChatMessage(msg) {
    const container = $('meetingChatMessages');
    if (!container) return;

    const div = document.createElement('div');
    div.style.cssText = 'background:rgba(255,255,255,0.04);border-radius:8px;padding:6px 10px;font-size:0.82rem;';
    div.innerHTML = `
      <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:var(--comm-steel-dark);margin-bottom:2px;">
        <b>${esc(msg.senderName)}</b>
        <span>${formatShortTime(msg.createdAt)}</span>
      </div>
      <div>${esc(msg.content)}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  // ── Modals & Action Helpers ────────────────────────────────────────────────
  function initUIEvents() {
    // Send button & enter key
    const sendBtn = $('sendMsgBtn');
    if (sendBtn) sendBtn.addEventListener('click', sendMessage);

    const textarea = $('composerTextarea');
    if (textarea) {
      textarea.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
      textarea.addEventListener('input', handleTyping);
    }

    // Filter tabs
    document.querySelectorAll('.comm-filter-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.comm-filter-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderConversationsList();
      });
    });

    // File attachments
    const fileInput = $('chatFileInput');
    const attachBtn = $('attachFileBtn');
    if (attachBtn && fileInput) {
      attachBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', handleFileUpload);
    }

    // Meeting Controls
    const micBtn = $('toggleMicBtn');
    if (micBtn) micBtn.addEventListener('click', toggleMic);

    const camBtn = $('toggleCamBtn');
    if (camBtn) camBtn.addEventListener('click', toggleCam);

    const screenBtn = $('toggleScreenBtn');
    if (screenBtn) screenBtn.addEventListener('click', toggleScreenShare);

    const leaveBtn = $('leaveMeetingBtn');
    if (leaveBtn) leaveBtn.addEventListener('click', () => leaveMeetingSession(true));

    const endAllBtn = $('endMeetingAllBtn');
    if (endAllBtn) endAllBtn.addEventListener('click', endMeetingForAll);

    const chatDrawerBtn = $('meetingChatToggleBtn');
    if (chatDrawerBtn) {
      chatDrawerBtn.addEventListener('click', () => {
        const drawer = $('meetingChatDrawer');
        if (drawer) {
          meetingChatOpen = !meetingChatOpen;
          drawer.style.display = meetingChatOpen ? 'flex' : 'none';
        }
      });
    }

    const sendMeetChatBtn = $('sendMeetingChatBtn');
    if (sendMeetChatBtn) sendMeetChatBtn.addEventListener('click', sendMeetingChat);

    const meetChatInput = $('meetingChatInput');
    if (meetChatInput) {
      meetChatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') sendMeetingChat();
      });
    }

    // Instant Call from chat header
    const videoCallBtn = $('headerVideoCallBtn');
    if (videoCallBtn) videoCallBtn.addEventListener('click', startInstantMeeting);

    const audioCallBtn = $('headerAudioCallBtn');
    if (audioCallBtn) {
      audioCallBtn.addEventListener('click', () => {
        startInstantMeeting().then(() => {
          isCamOff = true;
          updateMediaBtnStates();
        });
      });
    }

    // New Direct Chat Modal
    const newChatBtn = $('newChatBtn');
    if (newChatBtn) newChatBtn.addEventListener('click', openNewChatModal);

    // New Group Modal
    const newGroupBtn = $('newGroupBtn');
    if (newGroupBtn) newGroupBtn.addEventListener('click', openNewGroupModal);

    // Schedule Meeting Modal
    const scheduleMeetBtn = $('scheduleMeetingBtn');
    if (scheduleMeetBtn) scheduleMeetBtn.addEventListener('click', openScheduleMeetingModal);

    // Search Conversation
    const searchInput = $('searchConvInput');
    if (searchInput) {
      searchInput.addEventListener('input', e => {
        const query = e.target.value.toLowerCase().trim();
        document.querySelectorAll('.comm-conv-item').forEach(el => {
          const name = el.querySelector('.comm-conv-name')?.textContent.toLowerCase() || '';
          el.style.display = name.includes(query) ? 'flex' : 'none';
        });
      });
    }

    // Check URL parameters for direct meeting link
    const urlParams = new URLSearchParams(location.search);
    const meetParam = urlParams.get('meeting');
    if (meetParam) {
      openMeetingSession(meetParam, false);
    }
  }

  async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const previewBar = $('uploadPreviewBar');
    if (previewBar) {
      previewBar.style.display = 'flex';
      previewBar.innerHTML = `<span style="font-size:0.78rem;color:var(--comm-steel);">Uploading ${esc(file.name)}…</span>`;
    }

    try {
      const res = await fetch('/api/chat/upload', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + gToken },
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Upload failed');

      pendingAttachments.push(data);
      renderUploadPreview();
    } catch (err) {
      alert('Upload failed: ' + err.message);
      if (previewBar) previewBar.style.display = 'none';
    }
  }

  function renderUploadPreview() {
    const previewBar = $('uploadPreviewBar');
    if (!previewBar) return;

    if (pendingAttachments.length === 0) {
      previewBar.style.display = 'none';
      return;
    }

    previewBar.style.display = 'flex';
    previewBar.innerHTML = '';
    pendingAttachments.forEach((att, idx) => {
      const chip = document.createElement('div');
      chip.className = 'comm-upload-chip';
      chip.innerHTML = `
        <span>📎 ${esc(att.filename)}</span>
        <button style="background:none;border:none;color:var(--comm-red);cursor:pointer;" onclick="window.commApp.removeUpload(${idx})">&times;</button>
      `;
      previewBar.appendChild(chip);
    });
  }

  function clearAttachments() {
    pendingAttachments = [];
    const previewBar = $('uploadPreviewBar');
    if (previewBar) previewBar.style.display = 'none';
  }

  function cancelReply() {
    replyingTo = null;
    const banner = $('replyBanner');
    if (banner) banner.style.display = 'none';
  }

  // ── Modals: New Chat & Groups ──────────────────────────────────────────────
  async function openNewChatModal() {
    const modal = $('newChatModal');
    const dirList = $('newChatDirectoryList');
    if (!modal || !dirList) return;

    modal.classList.add('active');
    dirList.innerHTML = '<div style="padding:20px;text-align:center;">Loading colleagues…</div>';

    try {
      let users = await api('/chat/directory');
      users = (users || []).filter(u => u && !['viewer', 'user'].includes(String(u.role || '').toLowerCase().trim()));
      dirList.innerHTML = '';
      users.forEach(u => {
        const isOnline = onlineUserIds.has(u.id);
        const name = (u.name || u.email || 'User').trim();
        const initial = name.charAt(0).toUpperCase() || 'U';
        const role = (u.role || 'employee').replace(/_/g, ' ');
        const item = document.createElement('div');
        item.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:10px;border-bottom:1px solid var(--comm-border);cursor:pointer;border-radius:8px;';
        item.innerHTML = `
          <div style="display:flex;align-items:center;gap:10px;">
            <div class="comm-conv-avatar direct" style="width:34px;height:34px;font-size:0.85rem;">
              ${esc(initial)}
            </div>
            <div>
              <div style="font-weight:600;font-size:0.88rem;">${esc(name)}</div>
              <div style="font-size:0.72rem;color:var(--comm-steel);">${esc(role)} &bull; ${esc(u.email || '')}</div>
            </div>
          </div>
          <span class="comm-presence-dot ${isOnline ? 'online' : ''}" style="position:static;"></span>
        `;
        item.addEventListener('click', async () => {
          modal.classList.remove('active');
          const conv = await api('/chat/conversations', {
            method: 'POST',
            body: JSON.stringify({ type: 'direct', targetUserId: u.id })
          });
          await loadConversations();
          selectConversation(conv.id);
        });
        dirList.appendChild(item);
      });
    } catch (err) {
      dirList.innerHTML = `<div style="color:var(--comm-red);padding:20px;">${esc(err.message)}</div>`;
    }
  }

  async function openNewGroupModal() {
    const modal = $('newGroupModal');
    if (!modal) return;
    modal.classList.add('active');

    // Populate checkboxes for members
    const memberChecklist = $('newGroupMembersChecklist');
    if (memberChecklist) {
      memberChecklist.innerHTML = 'Loading colleagues…';
      try {
        let users = await api('/chat/directory');
        users = (users || []).filter(u => u && !['viewer', 'user'].includes(String(u.role || '').toLowerCase().trim()));
        memberChecklist.innerHTML = '';
        users.forEach(u => {
          const lbl = document.createElement('label');
          lbl.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:0.82rem;padding:4px 0;cursor:pointer;';
          lbl.innerHTML = `
            <input type="checkbox" value="${u.id}" class="group-member-cb" style="accent-color:var(--comm-accent);"/>
            <span>${esc(u.name)} (${esc(u.role)})</span>
          `;
          memberChecklist.appendChild(lbl);
        });
      } catch (e) {
        memberChecklist.innerHTML = 'Could not load colleagues.';
      }
    }
  }

  async function createGroupSubmit() {
    const title = $('newGroupTitleInput').value.trim();
    const descText = $('newGroupDescInput').value.trim();
    const isAnnounce = $('newGroupIsAnnounceInput') ? $('newGroupIsAnnounceInput').checked : false;

    if (!title) {
      alert('Group name is required.');
      return;
    }

    const memberIds = Array.from(document.querySelectorAll('.group-member-cb:checked')).map(cb => parseInt(cb.value, 10));

    try {
      const conv = await api('/chat/conversations', {
        method: 'POST',
        body: JSON.stringify({
          type: isAnnounce ? 'announcement' : 'group',
          title: title,
          description: descText,
          isAnnouncement: isAnnounce,
          memberIds: memberIds
        })
      });
      $('newGroupModal').classList.remove('active');
      $('newGroupTitleInput').value = '';
      $('newGroupDescInput').value = '';
      await loadConversations();
      selectConversation(conv.id);
    } catch (err) {
      alert(err.message);
    }
  }

  async function openScheduleMeetingModal() {
    const modal = $('scheduleMeetingModal');
    if (!modal) return;
    modal.classList.add('active');

    const checklist = $('scheduleMeetingMembersChecklist');
    if (checklist) {
      checklist.innerHTML = 'Loading colleagues…';
      try {
        let users = await api('/chat/directory');
        users = (users || []).filter(u => u && !['viewer', 'user'].includes(String(u.role || '').toLowerCase().trim()));
        checklist.innerHTML = '';
        users.forEach(u => {
          const lbl = document.createElement('label');
          lbl.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:0.82rem;padding:4px 0;cursor:pointer;';
          lbl.innerHTML = `
            <input type="checkbox" value="${u.id}" class="schedule-member-cb" style="accent-color:var(--comm-accent);"/>
            <span>${esc(u.name)} (${esc(u.role)})</span>
          `;
          checklist.appendChild(lbl);
        });
      } catch (e) {
        checklist.innerHTML = 'Could not load colleagues.';
      }
    }
  }

  async function scheduleMeetingSubmit() {
    const title = $('scheduleTitleInput').value.trim();
    const descText = $('scheduleDescInput').value.trim();
    const startVal = $('scheduleStartInput').value;
    const endVal = $('scheduleEndInput').value;

    if (!title) {
      alert('Meeting title is required.');
      return;
    }

    const invitedIds = Array.from(document.querySelectorAll('.schedule-member-cb:checked')).map(cb => parseInt(cb.value, 10));

    try {
      const meet = await api('/meetings', {
        method: 'POST',
        body: JSON.stringify({
          title: title,
          description: descText,
          scheduledStart: startVal ? new Date(startVal).toISOString() : null,
          scheduledEnd: endVal ? new Date(endVal).toISOString() : null,
          invitedUserIds: invitedIds
        })
      });

      alert(`Meeting scheduled successfully!\nMeeting Code: ${meet.meetingCode}`);
      $('scheduleMeetingModal').classList.remove('active');

      // Post in chat if conversation is open
      if (currentConvId) {
        const joinLink = `${location.origin}/communication.html?meeting=${meet.meetingCode}`;
        api(`/chat/conversations/${currentConvId}/messages`, {
          method: 'POST',
          body: JSON.stringify({
            content: `📅 Scheduled Meeting: **${meet.title}**\nTime: ${meet.scheduledStart ? new Date(meet.scheduledStart).toLocaleString() : 'TBD'}\nLink: ${joinLink}`
          })
        });
      }
    } catch (err) {
      alert(err.message);
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function scrollToBottom() {
    const container = $('messagesContainer');
    if (container) container.scrollTop = container.scrollHeight;
  }

  function formatTime(isoStr) {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatShortTime(isoStr) {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  function formatContent(text) {
    if (!text) return '';
    let out = esc(text);
    // Bold
    out = out.replace(/\*(.*?)\*/g, '<b>$1</b>');
    // Italic
    out = out.replace(/_(.*?)_/g, '<i>$1</i>');
    // Inline code
    out = out.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:2px 5px;border-radius:4px;font-family:monospace;font-size:0.85em;">$1</code>');
    // URLs
    out = out.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener" style="color:var(--comm-cyan);text-decoration:underline;">$1</a>');
    // Newlines
    out = out.replace(/\n/g, '<br/>');
    return out;
  }

  // ── Global Window Hook for Toolbar Buttons ─────────────────────────────────
  window.commApp = {
    reactToMsg: async (msgId, emoji) => {
      try {
        await api(`/chat/messages/${msgId}/react`, {
          method: 'POST',
          body: JSON.stringify({ emoji: emoji })
        });
      } catch (e) {
        alert(e.message);
      }
    },
    pinMsg: async msgId => {
      try {
        await api(`/chat/messages/${msgId}/pin`, { method: 'POST' });
        loadPinnedBanner(currentConvId);
      } catch (e) {
        alert(e.message);
      }
    },
    editMsg: async msgId => {
      const msg = messages.find(m => m.id === msgId);
      if (!msg) return;
      const newText = prompt('Edit your message:', msg.content);
      if (newText !== null && newText.trim() !== '') {
        try {
          await api(`/chat/messages/${msgId}`, {
            method: 'PUT',
            body: JSON.stringify({ content: newText.trim() })
          });
        } catch (e) {
          alert(e.message);
        }
      }
    },
    deleteMsg: async msgId => {
      if (confirm('Delete this message?')) {
        try {
          await api(`/chat/messages/${msgId}`, { method: 'DELETE' });
        } catch (e) {
          alert(e.message);
        }
      }
    },
    replyToMsg: msgId => {
      const msg = messages.find(m => m.id === msgId);
      if (!msg) return;
      replyingTo = msg;
      const banner = $('replyBanner');
      if (banner) {
        banner.style.display = 'flex';
        banner.innerHTML = `
          <span>Replying to <b>${esc(msg.senderName)}</b>: "${esc(msg.content.slice(0, 40))}"</span>
          <button style="background:none;border:none;color:var(--comm-steel);cursor:pointer;" onclick="window.commApp.cancelReply()">&times;</button>
        `;
      }
      const textarea = $('composerTextarea');
      if (textarea) textarea.focus();
    },
    cancelReply: cancelReply,
    removeUpload: idx => {
      pendingAttachments.splice(idx, 1);
      renderUploadPreview();
    },
    scrollToMsg: msgId => {
      const el = $(`msg-${msgId}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    },
    createGroupSubmit: createGroupSubmit,
    scheduleMeetingSubmit: scheduleMeetingSubmit,
    closeModals: () => {
      document.querySelectorAll('.comm-modal-overlay').forEach(m => m.classList.remove('active'));
    }
  };

})();
