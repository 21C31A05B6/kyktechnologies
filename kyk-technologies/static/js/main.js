// main.js — shared behavior across all pages.
const API = "/api";
const USER_TOKEN_KEY = "kyk_user_token";
const ADMIN_TOKEN_KEY = "kyk_admin_token";
const PUBLIC_ROLE_HOME = {
  super_admin: "admin.html",
  hr_manager: "hr-dashboard.html",
  recruiter: "recruiter-dashboard.html",
  content_manager: "content-dashboard.html",
  client: "client-portal.html",
  team_lead: "team-lead-dashboard.html",
  employee: "employee-dashboard.html",
  viewer: "viewer-dashboard.html",
};

function getUserToken() {
  return localStorage.getItem(USER_TOKEN_KEY) || "";
}

function getAdminToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

function setAuthControlVisible(element, visible) {
  if (element) element.classList.toggle("auth-control-hidden", !visible);
}

function addDashboardLink(navCta, dashboardPath) {
  let dashboardLink = navCta.querySelector(".dashboard-link");
  if (!dashboardLink) {
    dashboardLink = document.createElement("a");
    dashboardLink.className = "btn btn-primary dashboard-link";
    dashboardLink.style.cssText = "padding:9px 18px;font-size:.85rem;";
    dashboardLink.textContent = "Dashboard";
    navCta.insertBefore(dashboardLink, navCta.firstElementChild);
  }
  dashboardLink.href = "/" + dashboardPath;
}

function addLogoutButton(navCta, loginLink, clearTokens) {
  let logoutButton = navCta.querySelector(".user-logout-btn");
  if (!logoutButton) {
    logoutButton = document.createElement("button");
    logoutButton.type = "button";
    logoutButton.className = "btn btn-primary user-logout-btn";
    logoutButton.style.cssText = "padding:9px 18px;font-size:.85rem;";
    logoutButton.textContent = "Logout";
    logoutButton.addEventListener("click", () => {
      clearTokens();
      location.reload();
    });
    navCta.insertBefore(logoutButton, loginLink);
  }
  return logoutButton;
}

async function updateAuthNavigation() {
  const navCta = document.querySelector(".nav-cta");
  if (!navCta) return;

  const loginLinks = document.querySelectorAll('a[href="/login.html"]');
  const signupLinks = document.querySelectorAll('a[href="/login.html?mode=signup"]');
  const loginLink = navCta.querySelector('a[href="/login.html"]');
  const signupLink = navCta.querySelector('a[href="/login.html?mode=signup"]');
  if (!loginLinks.length || !signupLinks.length || !loginLink || !signupLink) return;

  const userToken = getUserToken();
  const adminToken = getAdminToken();
  let dashboardPath = userToken ? "user-dashboard.html" : "";

  if (adminToken) {
    // Use cached role if available (avoids an API round-trip on every page)
    const ROLE_CACHE_KEY = "kyk_admin_role_cache";
    const cached = (() => { try { return JSON.parse(localStorage.getItem(ROLE_CACHE_KEY) || "null"); } catch(e) { return null; } })();
    const tokenSig = adminToken.slice(-12); // last 12 chars as a cheap token fingerprint

    if (cached && cached.sig === tokenSig && cached.role) {
      dashboardPath = PUBLIC_ROLE_HOME[cached.role] || "admin.html";
      // Silently refresh in background — doesn't block UI
      fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${adminToken}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.admin) {
            localStorage.setItem(ROLE_CACHE_KEY, JSON.stringify({ sig: tokenSig, role: data.admin.role }));
          } else {
            localStorage.removeItem(ADMIN_TOKEN_KEY);
            localStorage.removeItem(ROLE_CACHE_KEY);
          }
        }).catch(() => {});
    } else {
      try {
        const response = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${adminToken}` },
        });
        if (!response.ok) throw new Error("Admin session expired");
        const data = await response.json();
        const role = data.admin && data.admin.role;
        dashboardPath = PUBLIC_ROLE_HOME[role] || "admin.html";
        localStorage.setItem(ROLE_CACHE_KEY, JSON.stringify({ sig: tokenSig, role }));
      } catch (error) {
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        localStorage.removeItem("kyk_admin_role_cache");
      }
    }
  }

  const loggedIn = Boolean(dashboardPath);
  loginLinks.forEach((link) => setAuthControlVisible(link, !loggedIn));
  signupLinks.forEach((link) => setAuthControlVisible(link, !loggedIn));

  let dashboardLink = navCta.querySelector(".dashboard-link");
  if (loggedIn) addDashboardLink(navCta, dashboardPath);
  dashboardLink = navCta.querySelector(".dashboard-link");
  setAuthControlVisible(dashboardLink, loggedIn);

  const logoutButton = addLogoutButton(navCta, loginLink, async () => {
    const at = getAdminToken();
    const ut = getUserToken();
    if (at) {
      try { await fetch(`${API}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${at}` } }); } catch(e){}
    }
    if (ut) {
      try { await fetch(`${API}/auth/user-logout`, { method: "POST", headers: { Authorization: `Bearer ${ut}` } }); } catch(e){}
    }
    localStorage.removeItem(USER_TOKEN_KEY);
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem("kyk_admin_role_cache");
  });
  setAuthControlVisible(logoutButton, loggedIn);
}

document.addEventListener("DOMContentLoaded", updateAuthNavigation);

function requireUserAuth(redirectPath = location.pathname) {
  if (!getUserToken()) {
    const url = "/login.html?redirect=" + encodeURIComponent(redirectPath);
    location.href = url;
    return false;
  }
  return true;
}

function toast(msg, isErr = false) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.borderLeftColor = isErr ? "#B3261E" : "var(--orange)";
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 3600);
}

function setFormMsg(el, msg, ok) {
  el.textContent = msg;
  el.classList.remove("ok", "err");
  el.classList.add("show", ok ? "ok" : "err");
  if (ok && window.kykShowSuccess) {
    const card = el.closest(".form-card");
    if (card) window.kykShowSuccess(card, "Message sent", msg);
  }
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) throw new Error((data && data.error) || "Something went wrong. Please try again.");
  return data;
}

document.addEventListener("DOMContentLoaded", () => {
  // Mobile nav toggle
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
    links.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => links.classList.remove("open")));
  }

  // Highlight active nav link
  const path = location.pathname.replace(/\/$/, "") || "/index.html";
  document.querySelectorAll(".nav-links a").forEach((a) => {
    const href = "/" + a.getAttribute("href").replace(/^\.?\//, "");
    if (href === path || (path === "/" && href === "/index.html")) a.classList.add("active");
  });

  // Newsletter (footer, present on every page)
  const newsForm = document.querySelector("#newsletter-form");
  if (newsForm) {
    newsForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = newsForm.querySelector("input[type=email]").value.trim();
      const btn = newsForm.querySelector("button");
      btn.disabled = true;
      try {
        const data = await apiFetch("/newsletter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        toast(data.message || "Subscribed!");
        newsForm.reset();
      } catch (err) {
        toast(err.message, true);
      } finally {
        btn.disabled = false;
      }
    });
  }

  // Simple reveal-on-load hero animation (one orchestrated moment, not per-card)
  const hero = document.querySelector(".hero, .page-hero");
  if (hero) hero.classList.add("is-visible");
});

// Generate a few starfield-like dots for the hero globe, if present.
function scatterDots(container, count = 26) {
  if (!container) return;
  for (let i = 0; i < count; i++) {
    const d = document.createElement("div");
    d.className = "dot";
    d.style.top = Math.random() * 90 + "%";
    d.style.left = Math.random() * 90 + "%";
    d.style.opacity = (0.3 + Math.random() * 0.7).toFixed(2);
    container.appendChild(d);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const heroGlobe = document.getElementById("heroGlobe");
  if (heroGlobe) scatterDots(heroGlobe, 24);
});

/* ===================================================================
   PHASE 2 — Experience engine: backdrop, cursor, glow, tilt, magnetic
   buttons, scroll reveal, counters, theme, page-veil, loading screen,
   AI assistant widget. Runs on every page that includes main.js.
=================================================================== */
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = window.matchMedia("(hover:hover) and (pointer:fine)").matches;

  /* ---------- Loading screen (fast: 600ms safety net) ---------- */
  const loader = document.createElement("div");
  loader.className = "kyk-loader";
  loader.innerHTML = `<div class="mark">K</div><div class="word">KYK TECHNOLOGIES</div><div class="bar"><i></i></div>`;
  document.body.prepend(loader);
  const bar = loader.querySelector("i");
  requestAnimationFrame(() => { bar.style.width = "60%"; });
  function _hideLoader() {
    if (!document.body.contains(loader)) return;
    bar.style.width = "100%";
    loader.classList.add("is-hidden");
    setTimeout(() => loader.remove(), 350);
  }
  window.addEventListener("load", () => { setTimeout(_hideLoader, 80); });
  // Safety net: hide within 600ms no matter what
  setTimeout(_hideLoader, 600);

  /* ---------- Animated backdrop + particles ---------- */
  const bg = document.createElement("div");
  bg.className = "kyk-bg";
  document.body.prepend(bg);
  if (!reduceMotion) {
    const particles = document.createElement("div");
    particles.className = "kyk-particles";
    // Reduced: 10 desktop / 5 mobile — enough visual without perf hit
    const count = window.innerWidth < 700 ? 5 : 10;
    const frag = document.createDocumentFragment();
    for (let i = 0; i < count; i++) {
      const p = document.createElement("span");
      p.style.left = Math.random() * 100 + "vw";
      p.style.bottom = "-10px";
      p.style.animationDuration = 16 + Math.random() * 14 + "s";
      p.style.animationDelay = Math.random() * -22 + "s";
      frag.appendChild(p);
    }
    particles.appendChild(frag);
    document.body.prepend(particles);
  }

  /* ---------- Page transition veil ---------- */
  const veil = document.createElement("div");
  veil.className = "kyk-veil";
  document.body.appendChild(veil);
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a) return;
    const href = a.getAttribute("href") || "";
    const isInternalPage = href.endsWith(".html") && !href.startsWith("http") && a.target !== "_blank";
    if (isInternalPage && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      veil.classList.add("is-active");
      setTimeout(() => { window.location.href = href; }, reduceMotion ? 0 : 220);
    }
  });

  /* ---------- Custom cursor (RAF stops when tab hidden) ---------- */
  if (fine && !reduceMotion) {
    const dot = document.createElement("div");
    const ring = document.createElement("div");
    dot.className = "kyk-cursor-dot";
    ring.className = "kyk-cursor-ring";
    document.body.append(dot, ring);
    let rx = 0, ry = 0, tx = 0, ty = 0, rafId = 0;
    window.addEventListener("mousemove", (e) => {
      dot.style.transform = `translate(${e.clientX}px,${e.clientY}px) translate(-50%,-50%)`;
      tx = e.clientX; ty = e.clientY;
    }, { passive: true });
    function cursorLoop() {
      if (document.hidden) { rafId = 0; return; }
      rx += (tx - rx) * 0.18; ry += (ty - ry) * 0.18;
      ring.style.transform = `translate(${rx}px,${ry}px) translate(-50%,-50%)`;
      rafId = requestAnimationFrame(cursorLoop);
    }
    cursorLoop();
    // Resume loop when tab becomes visible again
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && !rafId) cursorLoop();
    });
    document.addEventListener("mouseover", (e) => {
      ring.classList.toggle("is-active", !!e.target.closest("a,button,.tilt,.cap-card,.ai-card,.job-card"));
    }, { passive: true });
  } else {
    document.documentElement.style.setProperty("--mx", "50%");
    document.documentElement.style.setProperty("--my", "30%");
  }

  /* ---------- Mouse-follow glow + 3D tilt (deferred to idle time) ---------- */
  const tiltSelectors = ".cap-card, .ai-card, .why-card, .job-card, .insight-card, .tile, .stat-card";
  const _initTilt = () => {
    document.querySelectorAll(tiltSelectors).forEach((card) => {
      card.classList.add("glass-glow");
      if (reduceMotion) return;
      card.classList.add("tilt");
      card.addEventListener("mousemove", (e) => {
        const r = card.getBoundingClientRect();
        const px = ((e.clientX - r.left) / r.width) - 0.5;
        const py = ((e.clientY - r.top) / r.height) - 0.5;
        card.style.transform = `perspective(700px) rotateY(${px*7}deg) rotateX(${-py*7}deg) translateY(-2px)`;
        card.style.setProperty("--mx", (e.clientX - r.left) + "px");
        card.style.setProperty("--my", (e.clientY - r.top) + "px");
      }, { passive: true });
      card.addEventListener("mouseleave", () => { card.style.transform = ""; });
    });
  };
  // Defer tilt setup until browser is idle so it doesn't block first paint
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(_initTilt, { timeout: 1200 });
  } else {
    setTimeout(_initTilt, 300);
  }

  /* ---------- Magnetic buttons ---------- */
  if (!reduceMotion && fine) {
    document.querySelectorAll(".btn-primary, .btn-outline, .btn-outline-light").forEach((btn) => {
      btn.addEventListener("mousemove", (e) => {
        const r = btn.getBoundingClientRect();
        const mx = (e.clientX - r.left - r.width / 2) * 0.25;
        const my = (e.clientY - r.top - r.height / 2) * 0.35;
        btn.style.transform = `translate(${mx}px, ${my}px)`;
      });
      btn.addEventListener("mouseleave", () => { btn.style.transform = ""; });
    });
  }

  /* ---------- Scroll reveal ---------- */
  const revealTargets = document.querySelectorAll(
    ".section > .wrap > *, .section .cap-grid, .section .ai-grid, .section .why-grid, " +
    ".section .job-list, .section .insight-grid, .section .service-board, .section .stats-row, " +
    ".hero .wrap > *, .page-hero .wrap > *"
  );
  revealTargets.forEach((el) => { if (!el.classList.contains("reveal")) el.classList.add("reveal"); });
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("reveal-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
  } else {
    document.querySelectorAll(".reveal").forEach((el) => el.classList.add("reveal-visible"));
  }

  /* ---------- Animated counters (stat b / [data-count]) ---------- */
  function animateCount(el) {
    const raw = el.textContent.trim();
    const match = raw.match(/^([\d,]+)(\+?)(.*)$/);
    if (!match) return;
    const target = parseInt(match[1].replace(/,/g, ""), 10);
    const suffix = match[2] + match[3];
    if (isNaN(target)) return;
    if (reduceMotion) return;
    let start = null;
    const dur = 1200;
    function step(ts) {
      if (!start) start = ts;
      const p = Math.min(1, (ts - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(eased * target).toLocaleString() + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  const counters = document.querySelectorAll(".stats-row b, .stat-card b, [data-count]");
  if ("IntersectionObserver" in window && counters.length) {
    const ioC = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { animateCount(entry.target); ioC.unobserve(entry.target); }
      });
    }, { threshold: 0.6 });
    counters.forEach((el) => ioC.observe(el));
  }

  /* ---------- Navbar shrink on scroll ---------- */
  const header = document.querySelector(".site-header");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 30);
    document.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- Theme toggle (dark / light / aurora) ---------- */
  const THEME_KEY = "kyk_theme";
  const saved = localStorage.getItem(THEME_KEY) || "dark";
  if (saved !== "dark") document.documentElement.setAttribute("data-theme", saved);
  const navCta = document.querySelector(".nav-cta");
  if (navCta) {
    const wrap = document.createElement("div");
    wrap.className = "theme-toggle";
    wrap.innerHTML = `
      <button data-theme="dark" title="Dark" aria-label="Dark theme">☾</button>
      <button data-theme="light" title="Light" aria-label="Light theme">☀</button>
      <button data-theme="aurora" title="Aurora" aria-label="Aurora theme">◐</button>`;
    navCta.prepend(wrap);
    const markActive = (t) => wrap.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.theme === t));
    markActive(saved);
    wrap.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-theme]");
      if (!btn) return;
      const t = btn.dataset.theme;
      if (t === "dark") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", t);
      localStorage.setItem(THEME_KEY, t);
      markActive(t);
    });
  }

  /* ---------- Generic drag & drop resume upload ---------- */
  window.kykInitDropzone = function (fileInputId, dzId) {
    const input = document.getElementById(fileInputId);
    const dz = document.getElementById(dzId);
    if (!input || !dz) return;
    const info = dz.querySelector(".dz-info");
    function showFile(file) {
      if (!file) { if (info) info.innerHTML = ""; return; }
      const okSize = file.size <= 5 * 1024 * 1024;
      const kb = (file.size / 1024).toFixed(0);
      if (info) {
        info.innerHTML = `<div class="dz-file"><span>📄 ${file.name} · ${kb}KB ${okSize ? "" : "(over 5MB limit)"}</span><button type="button" aria-label="Remove file">&times;</button></div>
          <div class="dz-progress"><i></i></div>`;
        info.querySelector("button").addEventListener("click", () => { input.value = ""; showFile(null); });
        const barI = info.querySelector(".dz-progress i");
        requestAnimationFrame(() => { barI.style.width = "100%"; });
      }
    }
    dz.addEventListener("click", () => input.click());
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag-over"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("drag-over"));
    dz.addEventListener("drop", (e) => {
      e.preventDefault(); dz.classList.remove("drag-over");
      if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; showFile(e.dataTransfer.files[0]); }
    });
    input.addEventListener("change", () => showFile(input.files[0]));
  };

  /* ---------- Success checkmark overlay for forms ---------- */
  window.kykShowSuccess = function (formCardEl, title, subtitle) {
    if (!formCardEl) return;
    const overlay = document.createElement("div");
    overlay.className = "kyk-success";
    overlay.innerHTML = `
      <svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="24"/><path d="M18 31l8 8 16-18"/></svg>
      <div style="font-family:var(--font-display); font-weight:700; font-size:1.05rem;">${title}</div>
      <p style="margin:0; max-width:260px; font-size:.88rem;">${subtitle}</p>`;
    formCardEl.appendChild(overlay);
    setTimeout(() => overlay.remove(), 4200);
  };

  /* ---------- Floating KYK AI assistant ---------- */
  const btn = document.createElement("button");
  btn.className = "kyk-assistant-btn";
  btn.setAttribute("aria-label", "Open KYK AI assistant");
  btn.textContent = "✦";
  const panel = document.createElement("div");
  panel.className = "kyk-assistant-panel";
  panel.innerHTML = `
    <div class="kyk-assistant-head">
      <span class="dot"></span>
      <div><b>KYK AI</b><span>Ask about services, careers or contact</span></div>
    </div>
    <div class="kyk-assistant-body" id="kykChatBody">
      <div class="kyk-msg bot">Hi! I'm the KYK assistant. Ask me about our services, open roles, or how to get in touch.</div>
    </div>
    <div class="kyk-assistant-quick">
      <button type="button" data-q="What services does KYK offer?">Services</button>
      <button type="button" data-q="What jobs are open right now?">Open roles</button>
      <button type="button" data-q="How do I contact KYK?">Contact</button>
    </div>
    <form class="kyk-assistant-form" id="kykChatForm">
      <input type="text" id="kykChatInput" placeholder="Ask a question…" autocomplete="off" />
      <button type="submit" aria-label="Send">→</button>
    </form>`;
  document.body.append(btn, panel);
  btn.addEventListener("click", () => panel.classList.toggle("is-open"));
  const chatBody = panel.querySelector("#kykChatBody");
  function pushMsg(text, who) {
    const m = document.createElement("div");
    m.className = "kyk-msg " + who;
    m.textContent = text;
    chatBody.appendChild(m);
    chatBody.scrollTop = chatBody.scrollHeight;
    return m;
  }
  async function askAssistant(question) {
    pushMsg(question, "user");
    const typing = document.createElement("div");
    typing.className = "kyk-msg bot typing";
    typing.innerHTML = "<span></span><span></span><span></span>";
    chatBody.appendChild(typing);
    chatBody.scrollTop = chatBody.scrollHeight;
    try {
      const res = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question }),
      });
      const data = await res.json();
      typing.remove();
      pushMsg(data.reply || "I'm not sure — try our contact page and the team will help directly.", "bot");
    } catch (e) {
      typing.remove();
      pushMsg("I couldn't reach the server just now. Please try the contact page.", "bot");
    }
  }
  panel.querySelectorAll(".kyk-assistant-quick button").forEach((b) => {
    b.addEventListener("click", () => askAssistant(b.dataset.q));
  });
  const chatForm = panel.querySelector("#kykChatForm");
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = panel.querySelector("#kykChatInput");
    const v = input.value.trim();
    if (!v) return;
    input.value = "";
    askAssistant(v);
  });
})();
