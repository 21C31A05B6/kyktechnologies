if (!document.querySelector('script[src="/js/pwa.js"]')) {
  const pwaScript = document.createElement("script");
  pwaScript.src = "/js/pwa.js";
  document.head.appendChild(pwaScript);
}

/* dash-common.js — shared logic for every dashboard page (admin.html,
 * hr-dashboard.html, recruiter-dashboard.html, content-dashboard.html,
 * client-portal.html). Each page includes only the <div class="panel">
 * markup and sidebar entries relevant to that role; this file guards
 * every DOM lookup so it works unmodified no matter which panels are
 * present on the current page.
 *
 * Real access control is still enforced server-side by app.py's
 * @role_required / @attendance_required decorators — the redirect below
 * is a UX convenience, not a security boundary.
 */

/* ────── XSS-safe DOM helpers ────── */
function esc(v){ return String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function txt(el,v){ if(el) el.textContent = v??''; }
function setCell(tr,col,v){ tr.cells[col]&&(tr.cells[col].textContent=v??''); }
function $(id){ return document.getElementById(id); }
function on(id,evt,fn){ const el=$(id); if(el) el.addEventListener(evt,fn); }

/* ────── auth ────── */
const TOKEN_KEY='kyk_admin_token';
const LOGIN_USER_TOKEN_KEY='kyk_user_token';
const LOGIN_PAGE='login.html';
let gToken=localStorage.getItem(TOKEN_KEY)||'';
let gAdmin=null;

function currentPage(){ return location.pathname.split('/').pop() || 'index.html'; }
function goToLogin(){ if(currentPage()!==LOGIN_PAGE) location.replace('/'+LOGIN_PAGE); }

async function api(path,opts={}){
  const res=await fetch('/api'+path,{...opts,headers:{...(opts.headers||{}),Authorization:'Bearer '+gToken}});
  let d;
  try { d = await res.json(); } catch(e) { d = {}; }
  if(!res.ok){
    if(res.status === 401 && gToken){
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.setItem('kyk_session_notice', d.error || 'Your session expired or you were logged in from another device.');
      goToLogin();
    }
    throw new Error(d.error||'Request failed');
  }
  return d;
}
function setFormMsg(el,msg,ok){ if(!el) return; el.textContent=msg; el.className='form-msg show '+(ok?'ok':'err'); }

on('loginBtn','click',async()=>{
  const msg=$('loginMsg');
  const email=$('loginEmail').value;
  const pass=$('loginPassword').value;
  const isAdminLogin = String(document.body.dataset.adminLogin || '0') === '1';
  try{
    const requestOptions={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass})};
    let res=await fetch(isAdminLogin?'/api/auth/login':'/api/auth/user-login',requestOptions);
    let d=await res.json();

    // Normal login accepts either a user or an admin account. Keep the admin
    // fallback for convenience, but preserve the admin error if both fail.
    if(!res.ok && !isAdminLogin){
      res=await fetch('/api/auth/login',requestOptions);
      d=await res.json();
    }
    if(!res.ok) throw new Error(d.error || 'Login failed');
    if (isAdminLogin || d.role && ROLE_HOME[d.role]) {
      gToken=d.token; localStorage.setItem(TOKEN_KEY,gToken);
      const adminHome = ROLE_HOME[d.role] || 'admin.html';
      location.replace(loginBtn.dataset.redirect || `/${adminHome}`);
    } else {
      localStorage.setItem(LOGIN_USER_TOKEN_KEY, d.token);
      location.replace(loginBtn.dataset.redirect || '/user-dashboard.html');
    }
  } catch(e){ setFormMsg(msg,e.message,false); }
});
on('loginEmail','keydown',e=>e.key==='Enter'&&$('loginBtn').click());
on('loginPassword','keydown',e=>e.key==='Enter'&&$('loginBtn').click());
on('logoutBtn','click',async()=>{
  if(gToken){
    try{
      await fetch('/api/auth/logout',{method:'POST',headers:{Authorization:'Bearer '+gToken}});
    }catch(e){}
  }
  localStorage.removeItem(TOKEN_KEY);
  location.replace('/'+LOGIN_PAGE);
});

/* Check and show notice if redirected after being logged out / kicked */
document.addEventListener('DOMContentLoaded',()=>{
  const notice = sessionStorage.getItem('kyk_session_notice');
  if(notice){
    sessionStorage.removeItem('kyk_session_notice');
    const msg = $('loginMsg');
    if(msg) setFormMsg(msg, notice, false);
  }
});

/* ────── tab definitions (icons + labels) ────── */
const TAB_META={
  overview:     {icon:'📊', label:'Overview'},
  jobs:         {icon:'💼', label:'Jobs'},
  applications: {icon:'📋', label:'Applications'},
  pipeline:     {icon:'🔄', label:'Pipeline'},
  talent:       {icon:'👥', label:'Talent Pool'},
  contacts:     {icon:'✉️',  label:'Contacts'},
  newsletter:   {icon:'📧', label:'Newsletter'},
  insights:     {icon:'📝', label:'Insights'},
  activity:     {icon:'🔍', label:'Activity Log'},
  admin_users:  {icon:'🔑', label:'Admin Users'},
  my_attendance:{icon:'⏱️', label:'My Attendance'},
  attendance:   {icon:'🗓️', label:'Attendance Register'},
  daily_report: {icon:'📓', label:'Daily Report'},
  report_history:{icon:'🗓️', label:'Report History'},
  reports_review:{icon:'✅', label:'Reports Review'},
  employees:    {icon:'👤', label:'Employees'},
  performance:  {icon:'📈', label:'Performance'},
  settings:     {icon:'⚙️', label:'Settings'},
  my_profile:   {icon:'🪪', label:'My Profile'},
};

/* Every role's dedicated home page. */
const ROLE_HOME={
  super_admin:     'admin.html',
  hr_manager:      'hr-dashboard.html',
  recruiter:       'recruiter-dashboard.html',
  content_manager: 'content-dashboard.html',
  client:          'client-portal.html',
  team_lead:       'team-lead-dashboard.html',
  employee:        'employee-dashboard.html',
  viewer:          'viewer-dashboard.html',
};

let currentTab='overview';

function showDashboard(d){
  const home    = ROLE_HOME[d.role] || 'admin.html';
  const current = currentPage();
  if(current!==home){ location.replace('/'+home); return; }
  if(current===LOGIN_PAGE) return; // safety net, should never happen (no role maps to login.html)

  const ls=$('loginScreen'); if(ls) ls.style.display='none';
  const shell=$('dashShell'); if(!shell) return;
  shell.style.display='flex';
  ensureRolePanels(d.tabs||[]);
  txt($('adminName'), d.name||'Admin');
  txt($('adminEmail'), d.email||'');
  const roleLabel=d.role||'viewer';
  txt($('roleLabel'), roleLabel.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()));
  buildSidebar(d.tabs||['overview']);
  const firstTab=(d.tabs&&d.tabs[0])||'overview';
  switchTab(firstTab);
}

function ensureRolePanels(tabs){
  const main=document.querySelector('.main-content'); if(!main) return;
  const panels={
    employees:`<h3>Employee Directory</h3><div class="toolbar"><input id="employeeSearch" placeholder="Search name or email"/><button class="btn btn-outline" id="employeeRefresh">Refresh</button></div><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Department</th><th>Status</th></tr></thead><tbody id="employeesBody"></tbody></table>`,
    performance:`<h3>Performance Summary</h3><div class="toolbar"><input type="month" id="performanceMonth"/><button class="btn btn-primary" id="performanceRefresh">Refresh</button></div><table><thead><tr><th>Employee</th><th>Department</th><th>Reports</th><th>Submission rate</th><th>Status</th></tr></thead><tbody id="performanceBody"></tbody></table>`,
    settings:`<h3>Portal Settings</h3><form id="settingsForm" class="form-card" style="max-inline-size:660px"><div class="field"><label>Daily report deadline</label><input type="time" id="settingsDeadline"/></div><div class="field"><label>Departments (comma separated)</label><input id="settingsDepartments"/></div><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="settingsNotifications"/> Email alert for missed reports</label><div class="field"><label>Working days</label><input id="settingsWorkingDays" placeholder="0,1,2,3,4"/></div><button class="btn btn-primary" type="submit">Save settings</button><div class="form-msg" id="settingsMsg"></div></form>`,
    my_profile:`<h3>My Profile</h3><form id="profileForm" class="form-card" style="max-inline-size:660px"><div class="field"><label>Full name</label><input id="profileName" required/></div><div class="field"><label>Email</label><input id="profileEmail" disabled/></div><div class="field"><label>Role</label><input id="profileRole" disabled/></div><div class="field"><label>Phone</label><input id="profilePhone"/></div><div class="field"><label>New password</label><input id="profilePassword" type="password" minlength="8" autocomplete="new-password"/></div><div id="profileStats" class="stat-cards"></div><button class="btn btn-primary" type="submit">Save profile</button><div class="form-msg" id="profileMsg"></div></form>`,
  };
  tabs.forEach(tab=>{
    if(!panels[tab] || $('panel-'+tab)) return;
    const panel=document.createElement('div'); panel.className='panel'; panel.id='panel-'+tab; panel.innerHTML=panels[tab]; main.appendChild(panel);
  });
}

function buildSidebar(tabs){
  const nav=$('sidebarNav'); if(!nav) return;
  nav.innerHTML='';
  tabs.forEach(t=>{
    const m=TAB_META[t]; if(!m) return;
    if(!$('panel-'+t)) return; // this page doesn't render that panel
    const btn=document.createElement('button');
    btn.dataset.tab=t;
    btn.innerHTML=`<span class="tab-icon">${m.icon}</span><span>${m.label}</span>`;
    btn.addEventListener('click',()=>switchTab(t));
    nav.appendChild(btn);
  });
}

/* Pages can override/extend a loader before this file finishes loading
 * by setting window.TAB_LOADER_OVERRIDES = { tabName: fn, ... }. Used by
 * client-portal.html to swap in a client-safe overview loader. */
function getLoaders(){
  const defaults={
    overview:loadOverview, jobs:loadJobs, applications:loadApplications,
    pipeline:loadPipeline, talent:loadTalent, contacts:loadContacts,
    newsletter:loadNewsletter, insights:loadInsights,
    activity:loadActivity, admin_users:loadUsers,
    my_attendance:loadMyAttendance, attendance:loadAttendanceRegister,
    daily_report:loadMyDailyReport, report_history:loadReportHistory, reports_review:loadReportsReview,
    employees:loadEmployees, performance:loadPerformance, settings:loadSettings,
    my_profile:loadMyProfile,
  };
  return Object.assign(defaults, window.TAB_LOADER_OVERRIDES||{});
}

function switchTab(tab){
  currentTab=tab;
  document.querySelectorAll('.sidebar nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  const panel=$('panel-'+tab);
  if(panel) panel.classList.add('active');
  const loaders=getLoaders();
  if(loaders[tab]) loaders[tab]();
}

/* ────── auto-login on page load ────── */
document.addEventListener('DOMContentLoaded',async()=>{
  if(!gToken){
    if(currentPage()!==LOGIN_PAGE) goToLogin();
    return;
  }
  try{
    const d=await api('/auth/me');
    gAdmin=d.admin; showDashboard(d.admin);
  } catch(e){
    localStorage.removeItem(TOKEN_KEY);
    goToLogin();
  }
});

/* ────── OVERVIEW ────── */
async function loadOverview(){
  const cards=$('statCards'); if(!cards) return;
  try{
    // Start independent requests together instead of waiting for two in sequence.
    const [o,apps]=await Promise.all([api('/admin/overview'),api('/admin/applications')]);
    cards.innerHTML='';
    [
      [o.activeJobs,'Active jobs'],
      [o.applications,'Applications'],
      [o.talent,'Talent profiles'],
      [o.unreadContacts+' / '+o.contacts,'Unread messages'],
    ].forEach(([v,l])=>{
      const d=document.createElement('div');
      d.className='stat-card glass-glow';
      const b=document.createElement('b'); b.textContent=v;
      const s=document.createElement('span'); s.textContent=l;
      d.append(b,s); cards.appendChild(d);
    });
    drawAppsChart(apps);
  } catch(e){console.error(e);}
}

function drawAppsChart(apps){
  const c=$('appsChart'); if(!c) return;
  const ctx=c.getContext('2d');
  const days=14;
  const buckets=Array.from({length:days},(_,i)=>{
    const d=new Date(); d.setDate(d.getDate()-(days-1-i)); d.setHours(0,0,0,0);
    return{date:d,count:0};
  });
  apps.forEach(a=>{
    const ad=new Date(a.createdAt); ad.setHours(0,0,0,0);
    const b=buckets.find(x=>x.date.getTime()===ad.getTime());
    if(b) b.count++;
  });
  const w=c.width,h=c.height,pad=28,max=Math.max(1,...buckets.map(b=>b.count));
  ctx.clearRect(0,0,w,h);
  const barW=(w-pad*2)/days*0.55,gap=(w-pad*2)/days;
  const orange='#E8622C';
  buckets.forEach((b,i)=>{
    const x=pad+i*gap+(gap-barW)/2,barH=(b.count/max)*(h-pad*2);
    const g=ctx.createLinearGradient(0,h-pad-barH,0,h-pad);
    g.addColorStop(0,orange); g.addColorStop(1,'rgba(232,98,44,.2)');
    ctx.fillStyle=g;
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(x,h-pad-barH,barW,barH,3);
    else ctx.rect(x,h-pad-barH,barW,barH);
    ctx.fill();
  });
  ctx.strokeStyle='rgba(122,130,140,.2)';
  ctx.beginPath(); ctx.moveTo(pad,h-pad); ctx.lineTo(w-pad,h-pad); ctx.stroke();
}

/* ────── JOBS ────── */
async function loadJobs(){
  const tbody=$('jobsBody'); if(!tbody) return;
  const jobs=await api('/admin/jobs');
  tbody.innerHTML='';
  if(!jobs.length){tbody.innerHTML='<tr><td colspan="6" style="color:var(--steel)">No jobs yet.</td></tr>';return;}
  jobs.forEach(j=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td></td><td></td><td></td><td></td><td></td><td style="white-space:nowrap;"></td>`;
    tr.cells[0].textContent=j.title;
    tr.cells[1].textContent=j.department;
    tr.cells[2].textContent=j.location;
    tr.cells[3].textContent=j.type;
    const badge=document.createElement('span');
    badge.className='badge '+(j.active?'badge-new':'badge-rejected');
    badge.textContent=j.active?'Active':'Inactive';
    tr.cells[4].appendChild(badge);
    const actions=tr.cells[5];
    const editBtn=document.createElement('button'); editBtn.className='small-btn'; editBtn.textContent='Edit';
    editBtn.addEventListener('click',()=>editJob(j));
    const toggleBtn=document.createElement('button'); toggleBtn.className='small-btn'; toggleBtn.textContent=j.active?'Deactivate':'Activate';
    toggleBtn.style.marginLeft='4px';
    toggleBtn.addEventListener('click',()=>toggleJob(j));
    const delBtn=document.createElement('button'); delBtn.className='small-btn danger'; delBtn.textContent='Delete';
    delBtn.style.marginLeft='4px';
    delBtn.addEventListener('click',()=>deleteJob(j.id,j.title));
    actions.append(editBtn,toggleBtn,delBtn);
    tbody.appendChild(tr);
  });
}

function editJob(j){
  $('jobEditId').value=j.id;
  $('jTitle').value=j.title||'';
  $('jDept').value=j.department||'';
  $('jLocation').value=j.location||'';
  $('jType').value=j.type||'Full-time';
  $('jLevel').value=j.level||'Mid-level';
  $('jDesc').value=j.description||'';
  $('jActive').checked=j.active!==false;
  $('jobSubmitBtn').textContent='Update job';
  $('jobCancelBtn').style.display='inline-flex';
  $('jobDetails').open=true;
  $('jobDetails').scrollIntoView({behavior:'smooth'});
}
function resetJobForm(){
  const f=$('jobForm'); if(!f) return;
  f.reset();
  $('jobEditId').value='';
  $('jobSubmitBtn').textContent='Post job';
  $('jobCancelBtn').style.display='none';
  $('jActive').checked=true;
}
on('jobCancelBtn','click',resetJobForm);
async function toggleJob(j){
  await api('/admin/jobs/'+j.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({active:!j.active})});
  loadJobs();
}
async function deleteJob(id,title){
  if(!confirm('Delete job: '+title+'?')) return;
  await api('/admin/jobs/'+id,{method:'DELETE'}); loadJobs();
}
on('jobForm','submit',async e=>{
  e.preventDefault();
  const msg=$('jobMsg');
  const editId=$('jobEditId').value;
  const payload={
    title:$('jTitle').value,
    department:$('jDept').value,
    location:$('jLocation').value,
    type:$('jType').value,
    level:$('jLevel').value,
    description:$('jDesc').value,
    active:$('jActive').checked,
  };
  try{
    if(editId) await api('/admin/jobs/'+editId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    else await api('/admin/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    setFormMsg(msg,editId?'Job updated.':'Job posted.',true);
    resetJobForm(); loadJobs();
  } catch(err){setFormMsg(msg,err.message,false);}
});

/* ────── APPLICATIONS ────── */
async function loadApplications(){
  const tbody=$('applicationsBody'); if(!tbody) return;
  const apps=await api('/admin/applications');
  tbody.innerHTML='';
  if(!apps.length){tbody.innerHTML='<tr><td colspan="6" style="color:var(--steel)">No applications yet.</td></tr>';return;}
  apps.forEach(a=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td></td><td></td><td></td><td></td><td style="max-inline-size:180px;"></td><td style="white-space:nowrap;"></td>`;
    tr.cells[0].textContent=a.name+(a.email?'\n'+a.email:'')+(a.phone?'\n'+a.phone:'');
    tr.cells[0].style.whiteSpace='pre-wrap';
    tr.cells[1].textContent=a.jobTitle||'—';
    const badge=document.createElement('span');
    badge.className='badge badge-'+(a.status||'new');
    badge.textContent=(a.status||'new');
    tr.cells[2].appendChild(badge);
    if(a.resumeFile){
      const filePath='/api/admin/files/'+encodeURIComponent(a.resumeFile)+'?token='+encodeURIComponent(gToken);
      const viewLink=document.createElement('a'); viewLink.href=filePath; viewLink.textContent='View'; viewLink.target='_blank'; viewLink.rel='noopener'; viewLink.style.cssText='color:var(--orange);font-size:.8rem;margin-right:10px;';
      const downloadLink=document.createElement('a'); downloadLink.href=filePath+'&download=1'; downloadLink.textContent='Download'; downloadLink.style.cssText='color:var(--orange);font-size:.8rem;';
      tr.cells[3].append(viewLink,downloadLink);
    } else {tr.cells[3].textContent='—';}
    const notesArea=document.createElement('textarea'); notesArea.className='notes-area';
    notesArea.value=a.notes||''; notesArea.placeholder='Add notes…';
    notesArea.addEventListener('change',()=>saveAppNotes(a.id,notesArea.value));
    tr.cells[4].appendChild(notesArea);
    const actions=tr.cells[5];
    const sel=document.createElement('select'); sel.className='small-btn'; sel.style.background='none';
    ['new','reviewing','interview','hired','rejected'].forEach(s=>{
      const opt=document.createElement('option'); opt.value=s; opt.textContent=s; if(s===a.status) opt.selected=true; sel.appendChild(opt);
    });
    sel.addEventListener('change',()=>updateAppStatus(a.id,sel.value));
    actions.appendChild(sel);
    if(a.linkedin){const li=document.createElement('a'); li.href=a.linkedin; li.target='_blank'; li.textContent='LinkedIn'; li.style.cssText='display:block;font-size:.74rem;color:var(--orange);margin-block-start:4px;'; actions.appendChild(li);}
    tbody.appendChild(tr);
  });
}
async function updateAppStatus(id,status){
  try{ await api('/admin/applications/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})}); loadApplications(); }
  catch(e){ alert(e.message); }
}
async function saveAppNotes(id,notes){
  try{ await api('/admin/applications/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({notes})}); }
  catch(e){ console.error(e); }
}

/* ────── PIPELINE (Kanban) ────── */
const PIPELINE_STAGES=['understand','source','evaluate','match','interview','place'];
async function loadPipeline(){
  const board=$('kanbanBoard'); if(!board) return;
  const talent=await api('/admin/talent');
  board.innerHTML='';
  PIPELINE_STAGES.forEach(stage=>{
    const rows=talent.filter(t=>(t.stage||'understand')===stage);
    const col=document.createElement('div'); col.className='kanban-col'; col.dataset.stage=stage;
    const h=document.createElement('h5');
    const stageName=document.createElement('span'); stageName.textContent=stage;
    const cnt=document.createElement('span'); cnt.textContent=rows.length;
    h.append(stageName,cnt); col.appendChild(h);
    rows.forEach(t=>{
      const card=document.createElement('div'); card.className='kanban-card'; card.draggable=true; card.dataset.id=t.id;
      const b=document.createElement('b'); b.textContent=t.name;
      const s=document.createElement('span'); s.textContent=(t.specialization||'General')+' · '+(t.experience||'—')+' yrs';
      card.append(b,s);
      card.addEventListener('dragstart',e=>{e.dataTransfer.setData('text/plain',card.dataset.id);setTimeout(()=>card.style.opacity='.4',0);});
      card.addEventListener('dragend',()=>card.style.opacity='1');
      col.appendChild(card);
    });
    col.addEventListener('dragover',e=>{e.preventDefault();col.classList.add('drag-over');});
    col.addEventListener('dragleave',()=>col.classList.remove('drag-over'));
    col.addEventListener('drop',async e=>{
      e.preventDefault(); col.classList.remove('drag-over');
      const id=e.dataTransfer.getData('text/plain');
      try{await api('/admin/talent/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage})});loadPipeline();}
      catch(err){alert(err.message);}
    });
    board.appendChild(col);
  });
}

/* ────── TALENT ────── */
async function loadTalent(){
  const tbody=$('talentBody'); if(!tbody) return;
  const talent=await api('/admin/talent');
  tbody.innerHTML='';
  if(!talent.length){tbody.innerHTML='<tr><td colspan="8" style="color:var(--steel)">No profiles yet.</td></tr>';return;}
  talent.forEach(t=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td></td><td></td><td></td><td></td><td></td><td></td><td style="max-inline-size:160px;"></td><td></td>`;
    tr.cells[0].textContent=t.name;
    tr.cells[1].textContent=t.specialization||'—';
    tr.cells[2].textContent=(t.experience||'—')+' yrs';
    tr.cells[3].textContent=t.marketsInterested||'—';
    const contact=document.createElement('div');
    contact.appendChild(Object.assign(document.createElement('div'),{textContent:t.email}));
    if(t.phone) contact.appendChild(Object.assign(document.createElement('div'),{textContent:t.phone,style:'font-size:.75rem;color:var(--steel);'}));
    tr.cells[4].appendChild(contact);
    const sel=document.createElement('select'); sel.className='small-btn'; sel.style.background='none';
    PIPELINE_STAGES.forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=s;if(s===(t.stage||'understand'))o.selected=true;sel.appendChild(o);});
    sel.addEventListener('change',()=>updateTalentStage(t.id,sel.value));
    tr.cells[5].appendChild(sel);
    const notesArea=document.createElement('textarea'); notesArea.className='notes-area';
    notesArea.value=t.notes||''; notesArea.placeholder='Notes…';
    notesArea.addEventListener('change',()=>saveTalentNotes(t.id,notesArea.value));
    tr.cells[6].appendChild(notesArea);
    if(t.resumeFile){
      const filePath='/api/admin/files/'+encodeURIComponent(t.resumeFile)+'?token='+encodeURIComponent(gToken);
      const viewLink=document.createElement('a'); viewLink.href=filePath; viewLink.textContent='View'; viewLink.target='_blank'; viewLink.rel='noopener'; viewLink.className='small-btn';
      const downloadLink=document.createElement('a'); downloadLink.href=filePath+'&download=1'; downloadLink.textContent='Download'; downloadLink.className='small-btn';
      const clearButton=document.createElement('button'); clearButton.type='button'; clearButton.textContent='Clear'; clearButton.className='small-btn danger'; clearButton.addEventListener('click',()=>clearTalentResume(t.id));
      tr.cells[7].append(viewLink,downloadLink,clearButton);
    } else { tr.cells[7].textContent='No resume'; }
    tbody.appendChild(tr);
  });
}
async function clearTalentResume(id){
  if(!confirm('Clear this talent profile resume?')) return;
  try{ await api('/admin/talent/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({clearResume:true})}); loadTalent(); }
  catch(e){ alert(e.message); }
}
async function updateTalentStage(id,stage){try{await api('/admin/talent/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage})});}catch(e){alert(e.message);}}
async function saveTalentNotes(id,notes){try{await api('/admin/talent/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({notes})});}catch(e){console.error(e);}}

/* ────── CONTACTS ────── */
async function loadContacts(){
  const tbody=$('contactsBody'); if(!tbody) return;
  const contacts=await api('/admin/contacts');
  tbody.innerHTML='';
  if(!contacts.length){tbody.innerHTML='<tr><td colspan="6" style="color:var(--steel)">No messages yet.</td></tr>';return;}
  contacts.forEach(c=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td></td><td></td><td></td><td style="max-inline-size:240px;white-space:pre-wrap;font-size:.8rem;"></td><td></td><td></td>`;
    tr.cells[0].textContent=c.name+(c.email?'\n'+c.email:'');
    tr.cells[0].style.whiteSpace='pre-wrap';
    tr.cells[1].textContent=c.company||'—';
    tr.cells[2].textContent=c.service||'—';
    tr.cells[3].textContent=c.message||'';
    const badge=document.createElement('span'); badge.className='badge '+(c.status==='unread'?'badge-new':c.status==='responded'?'badge-hired':'badge-reviewing');
    badge.textContent=c.status||'unread'; tr.cells[4].appendChild(badge);
    ['read','responded'].forEach(s=>{
      if(s===c.status) return;
      const btn=document.createElement('button'); btn.className='small-btn'; btn.textContent='Mark '+s; btn.style.display='block'; btn.style.marginBottom='4px';
      btn.addEventListener('click',()=>updateContact(c.id,s));
      tr.cells[5].appendChild(btn);
    });
    tbody.appendChild(tr);
  });
}
async function updateContact(id,status){try{await api('/admin/contacts/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});loadContacts();}catch(e){alert(e.message);}}

/* ────── NEWSLETTER ────── */
async function loadNewsletter(){
  const tbody=$('newsletterBody'); if(!tbody) return;
  const subs=await api('/admin/newsletter');
  tbody.innerHTML='';
  if(!subs.length){tbody.innerHTML='<tr><td colspan="2" style="color:var(--steel)">No subscribers yet.</td></tr>';return;}
  subs.forEach(s=>{
    const tr=document.createElement('tr');
    tr.innerHTML='<td></td><td></td>';
    tr.cells[0].textContent=s.email;
    tr.cells[1].textContent=new Date(s.createdAt).toLocaleDateString();
    tbody.appendChild(tr);
  });
}

/* ────── INSIGHTS ────── */
async function loadInsights(){
  const tbody=$('insightsBody'); if(!tbody) return;
  const items=await api('/admin/insights');
  tbody.innerHTML='';
  if(!items.length){tbody.innerHTML='<tr><td colspan="4" style="color:var(--steel)">No insights yet.</td></tr>';return;}
  items.forEach(i=>{
    const tr=document.createElement('tr');
    tr.innerHTML='<td></td><td></td><td></td><td style="white-space:nowrap;"></td>';
    tr.cells[0].textContent=i.title;
    tr.cells[1].textContent=i.category;
    const badge=document.createElement('span'); badge.className='badge '+(i.published!==false?'badge-new':'badge-rejected');
    badge.textContent=i.published!==false?'Published':'Draft'; tr.cells[2].appendChild(badge);
    const editBtn=document.createElement('button'); editBtn.className='small-btn'; editBtn.textContent='Edit';
    editBtn.addEventListener('click',()=>editInsight(i));
    const togBtn=document.createElement('button'); togBtn.className='small-btn'; togBtn.textContent=i.published!==false?'Unpublish':'Publish'; togBtn.style.marginLeft='4px';
    togBtn.addEventListener('click',()=>togglePublish(i.id,i.published!==false));
    const delBtn=document.createElement('button'); delBtn.className='small-btn danger'; delBtn.textContent='Delete'; delBtn.style.marginLeft='4px';
    delBtn.addEventListener('click',()=>deleteInsight(i.id,i.title));
    tr.cells[3].append(editBtn,togBtn,delBtn);
    tbody.appendChild(tr);
  });
}
function editInsight(ins){
  $('insightEditId').value=ins.id;
  $('insightTitle').value=ins.title||'';
  $('insightCategory').value=ins.category||'AI';
  $('insightSummary').value=ins.summary||'';
  $('insightBody').value=ins.body||'';
  $('insightPublished').checked=ins.published!==false;
  $('insightSubmitBtn').textContent='Update';
  $('insightCancelEdit').style.display='inline-flex';
  $('insightDetails').open=true;
  $('insightDetails').scrollIntoView({behavior:'smooth'});
}
function resetInsightForm(){ const f=$('insightForm'); if(!f) return; f.reset(); $('insightEditId').value=''; $('insightSubmitBtn').textContent='Publish'; $('insightCancelEdit').style.display='none'; $('insightPublished').checked=true; }
on('insightCancelEdit','click',resetInsightForm);
async function togglePublish(id,cur){ await api('/admin/insights/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({published:!cur})}); loadInsights(); }
async function deleteInsight(id,title){ if(!confirm('Delete: '+title+'?')) return; await api('/admin/insights/'+id,{method:'DELETE'}); loadInsights(); }
on('insightForm','submit',async e=>{
  e.preventDefault();
  const msg=$('insightMsg');
  const editId=$('insightEditId').value;
  const payload={title:$('insightTitle').value,category:$('insightCategory').value,summary:$('insightSummary').value,body:$('insightBody').value,published:$('insightPublished').checked};
  try{
    if(editId) await api('/admin/insights/'+editId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    else await api('/admin/insights',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    setFormMsg(msg,editId?'Updated.':'Published.',true); resetInsightForm(); loadInsights();
  } catch(err){setFormMsg(msg,err.message,false);}
});

/* ────── ACTIVITY LOG ────── */
async function loadActivity(){
  const tbody=$('activityBody'); if(!tbody) return;
  const rows=await api('/admin/audit-log');
  tbody.innerHTML='';
  if(!rows.length){tbody.innerHTML='<tr><td colspan="7" style="color:var(--steel)">No login activity yet.</td></tr>';return;}
  rows.forEach(r=>{
    const tr=document.createElement('tr');
    tr.innerHTML='<td></td><td></td><td></td><td></td><td></td><td></td><td></td>';
    tr.cells[0].textContent=new Date(r.createdAt).toLocaleString();
    tr.cells[1].textContent=r.adminEmail||'—';
    const rb=document.createElement('span'); rb.className='badge role-'+(r.adminRole||'viewer'); rb.textContent=(r.adminRole||'—').replace('_',' ');
    tr.cells[2].appendChild(rb);
    tr.cells[3].textContent=r.action;
    tr.cells[4].textContent=r.detail||'—';
    tr.cells[5].textContent=r.ip||'—';
    const deleteButton=document.createElement('button');
    deleteButton.type='button'; deleteButton.className='small-btn danger'; deleteButton.textContent='Delete';
    deleteButton.addEventListener('click',()=>deleteActivityLog(r.id));
    tr.cells[6].appendChild(deleteButton);
    tbody.appendChild(tr);
  });
}
async function deleteActivityLog(id){
  if(!confirm('Delete this login log?')) return;
  try{ await api('/admin/audit-log/'+id,{method:'DELETE'}); loadActivity(); }
  catch(err){ alert(err.message); }
}
on('clearActivityBtn','click',async()=>{
  if(!confirm('Clear every login log? This cannot be undone.')) return;
  try{ await api('/admin/audit-log',{method:'DELETE'}); loadActivity(); }
  catch(err){ alert(err.message); }
});

/* ────── ADMIN USERS ────── */
async function loadUsers(){
  const tbody=$('usersBody'); if(!tbody) return;
  const users=await api('/admin/users');
  tbody.innerHTML='';
  if(!users.length){tbody.innerHTML='<tr><td colspan="6" style="color:var(--steel)">No users.</td></tr>';return;}
  users.forEach(u=>{
    const tr=document.createElement('tr');
    tr.innerHTML='<td></td><td></td><td></td><td></td><td></td><td style="white-space:nowrap;"></td>';
    tr.cells[0].textContent=u.name||'—';
    tr.cells[1].textContent=u.email||'—';
    const passwordStatus=document.createElement('span'); passwordStatus.className='badge'; passwordStatus.textContent=u.passwordSet?'Protected':'Not set';
    tr.cells[2].appendChild(passwordStatus);
    const rb=document.createElement('span'); rb.className='badge role-'+(u.role||'viewer'); rb.textContent=(u.role||'viewer').replace(/_/g,' ');
    tr.cells[3].appendChild(rb);
    tr.cells[4].textContent=u.createdAt?new Date(u.createdAt).toLocaleDateString():'—';
    const editBtn=document.createElement('button'); editBtn.className='small-btn'; editBtn.textContent='Edit';
    editBtn.addEventListener('click',()=>editUser(u));
    const delBtn=document.createElement('button'); delBtn.className='small-btn danger'; delBtn.textContent='Delete'; delBtn.style.marginLeft='4px';
    delBtn.addEventListener('click',()=>deleteUser(u.id,u.email));
    tr.cells[5].append(editBtn,delBtn);
    tbody.appendChild(tr);
  });
}
function editUser(u){
  $('userEditId').value=u.id;
  $('uName').value=u.name||'';
  $('uEmail').value=u.email||'';
  $('uPassword').value='';
  $('uRole').value=u.role||'viewer';
  $('uShift').value=u.shift||'morning';
  $('userSubmitBtn').textContent='Update user';
  $('userCancelBtn').style.display='inline-flex';
  $('userDetails').open=true;
  $('userDetails').scrollIntoView({behavior:'smooth'});
}
function resetUserForm(){ const f=$('userForm'); if(!f) return; f.reset(); $('userEditId').value=''; $('userSubmitBtn').textContent='Create user'; $('userCancelBtn').style.display='none'; }
on('userCancelBtn','click',resetUserForm);
async function deleteUser(id,email){ if(!confirm('Delete admin: '+email+'?')) return; try{await api('/admin/users/'+id,{method:'DELETE'});loadUsers();}catch(e){alert(e.message);}}
on('userForm','submit',async e=>{
  e.preventDefault();
  const msg=$('userMsg');
  const editId=$('userEditId').value;
  const payload={name:$('uName').value,email:$('uEmail').value,role:$('uRole').value,shift:$('uShift').value};
  const pw=$('uPassword').value;
  if(pw) payload.password=pw;
  if(!editId && !pw){setFormMsg(msg,'Password is required for new users.',false);return;}
  try{
    if(editId) await api('/admin/users/'+editId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    else await api('/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    setFormMsg(msg,editId?'User updated.':'User created.',true); resetUserForm(); loadUsers();
  } catch(err){setFormMsg(msg,err.message,false);}
});

/* ────── ATTENDANCE (self: check-in / check-out + my monthly calendar) ────── */
const MONTH_NAMES=['January','February','March','April','May','June','July','August','September','October','November','December'];
const _now0=new Date();
let myCalYear=_now0.getFullYear(), myCalMonth=_now0.getMonth()+1;

function fmtHours(sec){ if(sec==null) return '—'; const h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60); return h+'h '+m+'m'; }
function fmtTime(iso){ return iso ? new Date(iso).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) : '—'; }
function dayBadge(status){
  const b=document.createElement('span');
  b.className='punch-badge badge-day-'+status.replace(/\s+/g,'');
  b.textContent=status;
  return b;
}
function appendDayStatus(cell,row){
  if(row.dayStatus){
    const badge=dayBadge(row.dayStatus);
    if(row.holidayName) badge.title=row.holidayName+' ('+(row.holidayType||'holiday')+')';
    cell.appendChild(badge);
  } else cell.textContent='In progress';
}

async function loadMyAttendance(){
  if(!$('punchStatusLabel')) return;
  await refreshPunchStatus();
  await loadMyCalendar();
}
async function refreshPunchStatus(){
  try{
    const row=await api('/attendance/today');
    const label=$('punchStatusLabel');
    const time=$('punchTimeLabel');
    const inBtn=$('checkInBtn');
    const outBtn=$('checkOutBtn');
    if(!label) return;
    if(!row.checkIn){
      label.textContent="You haven't checked in today.";
      time.textContent='—';
      inBtn.style.display='inline-flex'; outBtn.style.display='none';
    } else if(!row.checkOut){
      label.textContent='Checked in at '+fmtTime(row.checkIn);
      time.textContent='On the clock';
      inBtn.style.display='none'; outBtn.style.display='inline-flex';
    } else {
      label.textContent='Checked in '+fmtTime(row.checkIn)+' · out '+fmtTime(row.checkOut);
      time.textContent=fmtHours(row.workedSeconds)+(row.dayStatus?' · '+row.dayStatus:'');
      inBtn.style.display='none'; outBtn.style.display='none';
    }
  } catch(e){console.error(e);}
}
on('checkInBtn','click',async()=>{
  const msg=$('punchMsg');
  try{ await api('/attendance/checkin',{method:'POST'}); setFormMsg(msg,'Checked in. Have a great day.',true); refreshPunchStatus(); loadMyCalendar(); }
  catch(e){ setFormMsg(msg,e.message,false); }
});
on('checkOutBtn','click',async()=>{
  const msg=$('punchMsg');
  try{ await api('/attendance/checkout',{method:'POST'}); setFormMsg(msg,'Checked out. Hours recorded.',true); refreshPunchStatus(); loadMyCalendar(); }
  catch(e){ setFormMsg(msg,e.message,false); }
});
async function loadMyCalendar(){
  const tbody=$('myCalBody'); if(!tbody) return;
  try{
    const d=await api('/attendance/calendar?year='+myCalYear+'&month='+myCalMonth);
    txt($('myCalLabel'), MONTH_NAMES[d.month-1]+' '+d.year);
    const s=d.summary||{};
    const cards=$('myCalSummary');
    if(cards){
      cards.innerHTML='';
      [[s.daysLogged||0,'Days logged'],[s.fullDays||0,'Full days'],[s.halfDays||0,'Half days'],[(s.totalHours||0)+'h','Total hours']]
        .forEach(([v,l])=>{
          const c=document.createElement('div'); c.className='stat-card glass-glow';
          const b=document.createElement('b'); b.textContent=v;
          const sp=document.createElement('span'); sp.textContent=l;
          c.append(b,sp); cards.appendChild(c);
        });
    }
    tbody.innerHTML='';
    if(!d.days.length){tbody.innerHTML='<tr><td colspan="5" style="color:var(--steel)">No attendance logged this month.</td></tr>';return;}
    d.days.forEach(r=>{
      const tr=document.createElement('tr');
      tr.innerHTML='<td></td><td></td><td></td><td></td><td></td>';
      tr.cells[0].textContent=r.date;
      tr.cells[1].textContent=fmtTime(r.checkIn);
      tr.cells[2].textContent=fmtTime(r.checkOut);
      tr.cells[3].textContent=fmtHours(r.workedSeconds);
      appendDayStatus(tr.cells[4],r);
      tbody.appendChild(tr);
    });
  } catch(e){console.error(e);}
}
on('myCalPrev','click',()=>{ myCalMonth--; if(myCalMonth<1){myCalMonth=12;myCalYear--;} loadMyCalendar(); });
on('myCalNext','click',()=>{ myCalMonth++; if(myCalMonth>12){myCalMonth=1;myCalYear++;} loadMyCalendar(); });

/* ────── ATTENDANCE REGISTER (HR Manager + Super Admin: everyone's attendance) ────── */
let regCalYear=_now0.getFullYear(), regCalMonth=_now0.getMonth()+1, regEmployeesLoaded=false;
async function loadAttendanceRegister(){
  if(!$('regBody')) return;
  if(!regEmployeesLoaded){
    try{
      const emps=await api('/admin/attendance/employees');
      const sel=$('regEmployeeFilter');
      if(sel) emps.forEach(u=>{
        const o=document.createElement('option');
        o.value=u.id; o.textContent=(u.name||'—')+' ('+(u.role||'').replace(/_/g,' ')+')';
        sel.appendChild(o);
      });
      regEmployeesLoaded=true;
    } catch(e){console.error(e);}
  }
  await loadRegisterRows();
}
async function loadRegisterRows(){
  const tbody=$('regBody'); if(!tbody) return;
  try{
    const uidEl=$('regEmployeeFilter');
    const uid=uidEl?uidEl.value:'';
    let path='/admin/attendance?year='+regCalYear+'&month='+regCalMonth;
    if(uid) path+='&userId='+uid;
    const d=await api(path);
    txt($('regCalLabel'), MONTH_NAMES[d.month-1]+' '+d.year);
    tbody.innerHTML='';
    if(!d.rows.length){tbody.innerHTML='<tr><td colspan="7" style="color:var(--steel)">No attendance logged this month.</td></tr>';return;}
    d.rows.forEach(r=>{
      const tr=document.createElement('tr');
      tr.innerHTML='<td></td><td></td><td></td><td></td><td></td><td></td><td></td>';
      tr.cells[0].textContent=r.date;
      tr.cells[1].textContent=r.adminName||'—';
      const rb=document.createElement('span'); rb.className='badge role-'+(r.adminRole||'viewer'); rb.textContent=(r.adminRole||'—').replace(/_/g,' ');
      tr.cells[2].appendChild(rb);
      tr.cells[3].textContent=fmtTime(r.checkIn);
      tr.cells[4].textContent=fmtTime(r.checkOut);
      tr.cells[5].textContent=fmtHours(r.workedSeconds);
      appendDayStatus(tr.cells[6],r);
      tbody.appendChild(tr);
    });
  } catch(e){console.error(e);}
}
on('regCalPrev','click',()=>{ regCalMonth--; if(regCalMonth<1){regCalMonth=12;regCalYear--;} loadRegisterRows(); });
on('regCalNext','click',()=>{ regCalMonth++; if(regCalMonth>12){regCalMonth=1;regCalYear++;} loadRegisterRows(); });
on('regEmployeeFilter','change',loadRegisterRows);

/* ────── DAILY REPORT (self: submit today's report + own history) ────── */
const MOOD_EMOJI={exhausted:'😫',tired:'😔',okay:'😐',good:'🙂',great:'😄'};
let selectedMood='';
let repHistYear=_now0.getFullYear(), repHistMonth=_now0.getMonth()+1;

async function loadMyDailyReport(){
  if(!$('reportSummary')) return;
  await prefillTodayReport();
  await loadMyReportHistory();
}

async function prefillTodayReport(){
  try{
    const r=await api('/daily-report/today');
    selectedMood='';
    document.querySelectorAll('#reportMoodPicker button').forEach(b=>b.classList.remove('active'));
    if(r){
      $('reportSummary').value=r.workSummary||'';
      $('reportTasks').value=r.tasksCompleted||'';
      $('reportBlockers').value=r.blockers||'';
      $('reportHours').value=r.hoursWorked??'';
      if(r.mood){
        selectedMood=r.mood;
        const b=document.querySelector('#reportMoodPicker button[data-mood="'+r.mood+'"]');
        if(b) b.classList.add('active');
      }
      $('reportSubmitBtn').textContent='Update today\u2019s report';
      if(r.reviewed) setFormMsg($('reportMsg'),'Already reviewed'+(r.reviewedBy?' by '+r.reviewedBy:'')+(r.comment?': "'+r.comment+'"':'.'),true);
    } else {
      $('reportSubmitBtn').textContent='Submit report';
    }
    updateCharCounter();
  } catch(e){console.error(e);}
}

function updateCharCounter(){
  const el=$('reportSummary'), counter=$('reportCharCounter'); if(!el||!counter) return;
  const len=el.value.length;
  counter.textContent=len+' / 2000';
  counter.classList.toggle('warn', len<20);
}
on('reportSummary','input',updateCharCounter);

document.addEventListener('click',e=>{
  const btn=e.target.closest('#reportMoodPicker button');
  if(!btn) return;
  document.querySelectorAll('#reportMoodPicker button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  selectedMood=btn.dataset.mood;
});

on('reportForm','submit',async e=>{
  e.preventDefault();
  const msg=$('reportMsg');
  const summary=$('reportSummary').value.trim();
  if(summary.length<20){ setFormMsg(msg,'Work summary must be at least 20 characters.',false); return; }
  const payload={
    workSummary:summary,
    tasksCompleted:$('reportTasks').value.trim(),
    blockers:$('reportBlockers').value.trim(),
    hoursWorked:$('reportHours').value?Number($('reportHours').value):null,
    mood:selectedMood,
  };
  try{
    await api('/daily-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    setFormMsg(msg,'Report saved. Thanks!',true);
    $('reportSubmitBtn').textContent='Update today\u2019s report';
    loadMyReportHistory();
  } catch(err){ setFormMsg(msg,err.message,false); }
});

function reportMoodBadge(mood){
  const s=document.createElement('span');
  s.textContent=MOOD_EMOJI[mood]||'—';
  s.title=mood||'';
  return s;
}
function reviewStatusBadge(reviewed){
  const s=document.createElement('span');
  s.className='badge '+(reviewed?'badge-hired':'badge-reviewing');
  s.textContent=reviewed?'Reviewed':'Pending';
  return s;
}

async function loadMyReportHistory(){
  const tbody=$('reportHistBody'); if(!tbody) return;
  try{
    const d=await api('/daily-report/history?year='+repHistYear+'&month='+repHistMonth);
    txt($('reportHistLabel'), MONTH_NAMES[d.month-1]+' '+d.year);
    tbody.innerHTML='';
    if(!d.reports.length){tbody.innerHTML='<tr><td colspan="5" style="color:var(--steel)">No reports filed this month.</td></tr>';return;}
    d.reports.forEach(r=>{
      const tr=document.createElement('tr');
      tr.innerHTML='<td></td><td></td><td></td><td></td><td></td>';
      tr.cells[0].textContent=r.date;
      tr.cells[1].textContent=(r.workSummary||'').slice(0,90)+((r.workSummary||'').length>90?'\u2026':'');
      tr.cells[2].textContent=r.hoursWorked!=null?r.hoursWorked+'h':'—';
      tr.cells[3].appendChild(reportMoodBadge(r.mood));
      tr.cells[4].appendChild(reviewStatusBadge(r.reviewed));
      tbody.appendChild(tr);
    });
  } catch(e){console.error(e);}
}
async function loadReportHistory(){
  const source=$('reportHistBody'), target=$('reportHistoryBody');
  if(!target || !source){ return; }
  await loadMyReportHistory();
  target.innerHTML=source.innerHTML;
}
on('reportHistPrev','click',()=>{ repHistMonth--; if(repHistMonth<1){repHistMonth=12;repHistYear--;} loadMyReportHistory(); });
on('reportHistNext','click',()=>{ repHistMonth++; if(repHistMonth>12){repHistMonth=1;repHistYear++;} loadMyReportHistory(); });
on('reportHistoryPrev','click',()=>{ repHistMonth--; if(repHistMonth<1){repHistMonth=12;repHistYear--;} loadReportHistory(); });
on('reportHistoryNext','click',()=>{ repHistMonth++; if(repHistMonth>12){repHistMonth=1;repHistYear++;} loadReportHistory(); });

/* ────── REPORTS REVIEW (HR Manager + Super Admin: everyone's reports) ────── */
let selectedReportId=null;

async function loadReportsReview(){
  if(!$('reviewBody')) return;
  if(!$('reviewDateFilter').value) $('reviewDateFilter').value=new Date().toISOString().slice(0,10);
  await loadReviewRows();
}

async function loadReviewRows(){
  const tbody=$('reviewBody'); if(!tbody) return;
  try{
    const date=$('reviewDateFilter').value;
    const reviewed=$('reviewReviewedFilter')?$('reviewReviewedFilter').value:'';
    let path='/admin/daily-reports?date='+encodeURIComponent(date);
    if(reviewed) path+='&reviewed='+reviewed;
    const d=await api(path);
    tbody.innerHTML='';
    if(!d.reports.length){tbody.innerHTML='<tr><td colspan="7" style="color:var(--steel)">No reports for this date.</td></tr>';}
    d.reports.forEach(r=>{
      const tr=document.createElement('tr');
      tr.innerHTML='<td></td><td></td><td></td><td></td><td></td><td></td><td></td>';
      tr.cells[0].textContent=r.date;
      tr.cells[1].textContent=r.adminName||'—';
      const rb=document.createElement('span'); rb.className='badge role-'+(r.adminRole||'viewer'); rb.textContent=(r.adminRole||'—').replace(/_/g,' ');
      tr.cells[2].appendChild(rb);
      tr.cells[3].textContent=(r.workSummary||'').slice(0,70)+((r.workSummary||'').length>70?'\u2026':'');
      tr.cells[4].textContent=r.hoursWorked!=null?r.hoursWorked+'h':'—';
      tr.cells[5].appendChild(reviewStatusBadge(r.reviewed));
      const btn=document.createElement('button'); btn.className='small-btn'; btn.textContent='Review';
      btn.addEventListener('click',()=>openReportDetail(r));
      tr.cells[6].appendChild(btn);
      tbody.appendChild(tr);
    });
    const missBox=$('reviewMissingBox');
    if(missBox){
      if(!d.missing.length){ missBox.innerHTML='<span style="color:var(--steel-light)">Everyone eligible has filed a report for '+d.missingDate+'.</span>'; }
      else{
        missBox.innerHTML='<b>'+d.missing.length+' '+(d.missing.length===1?'person hasn\u2019t':'people haven\u2019t')+' filed a report for '+d.missingDate+':</b> '
          +d.missing.map(u=>esc(u.name||'—')).join(', ');
      }
    }
  } catch(e){console.error(e);}
}
on('reviewApplyBtn','click',loadReviewRows);
on('reviewTodayBtn','click',()=>{ $('reviewDateFilter').value=new Date().toISOString().slice(0,10); loadReviewRows(); });
on('reviewReviewedFilter','change',loadReviewRows);

function openReportDetail(r){
  selectedReportId=r.id;
  const card=$('reviewDetailCard'); if(!card) return;
  card.style.display='block';
  txt($('reviewDetailMeta'), (r.adminName||'—')+' \u00b7 '+(r.adminRole||'').replace(/_/g,' ')+' \u00b7 '+r.date);
  txt($('reviewDetailSummary'), r.workSummary||'—');
  txt($('reviewDetailTasks'), r.tasksCompleted||'—');
  txt($('reviewDetailBlockers'), r.blockers||'—');
  txt($('reviewDetailHours'), r.hoursWorked!=null?(r.hoursWorked+'h logged'):'Not logged');
  $('reviewCommentInput').value=r.comment||'';
  $('reviewReviewedCheckbox').checked=!!r.reviewed;
  card.scrollIntoView({behavior:'smooth',block:'nearest'});
}
on('reviewSaveBtn','click',async()=>{
  if(!selectedReportId) return;
  const msg=$('reviewMsg');
  try{
    await api('/admin/daily-reports/'+selectedReportId+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      comment:$('reviewCommentInput').value.trim(),
      reviewed:$('reviewReviewedCheckbox').checked,
    })});
    setFormMsg(msg,'Saved.',true);
    loadReviewRows();
  } catch(e){ setFormMsg(msg,e.message,false); }
});

/* ────── WORKPULSE DIRECTORY / PERFORMANCE / SETTINGS / PROFILE ────── */
async function loadEmployees(){
  const tbody=$('employeesBody'); if(!tbody) return;
  try{
    const q=encodeURIComponent($('employeeSearch')?.value||'');
    const rows=await api('/admin/employees?q='+q);
    tbody.innerHTML='';
    if(!rows.length){tbody.innerHTML='<tr><td colspan="5">No employees found.</td></tr>';return;}
    rows.forEach(u=>{
      const tr=document.createElement('tr'); tr.innerHTML='<td></td><td></td><td></td><td></td><td></td>';
      tr.cells[0].textContent=u.name||'—'; tr.cells[1].textContent=u.email||'—';
      tr.cells[2].textContent=(u.role||'').replace(/_/g,' '); tr.cells[3].textContent=u.department||'—';
      tr.cells[4].textContent=u.status||'active'; tbody.appendChild(tr);
    });
  }catch(e){console.error(e);}
}
on('employeeRefresh','click',loadEmployees); on('employeeSearch','keydown',e=>e.key==='Enter'&&loadEmployees());

async function loadPerformance(){
  const tbody=$('performanceBody'); if(!tbody) return;
  try{
    const month=$('performanceMonth')?.value||''; const d=await api('/admin/performance?month='+encodeURIComponent(month));
    tbody.innerHTML='';
    if(!d.rows.length){tbody.innerHTML='<tr><td colspan="5">No performance data.</td></tr>';return;}
    d.rows.forEach(r=>{
      const tr=document.createElement('tr'); tr.innerHTML='<td></td><td></td><td></td><td></td><td></td>';
      tr.cells[0].textContent=r.name||'—'; tr.cells[1].textContent=r.department||'—';
      tr.cells[2].textContent=r.totalReports; tr.cells[3].textContent=r.submissionRate+'%';
      const badge=document.createElement('span'); badge.className='badge '+(r.attention?'badge-rejected':'badge-hired'); badge.textContent=r.attention?'Needs attention':'On track';
      tr.cells[4].appendChild(badge); tbody.appendChild(tr);
    });
  }catch(e){console.error(e);}
}
on('performanceRefresh','click',loadPerformance);

async function loadSettings(){
  const form=$('settingsForm'); if(!form) return;
  try{
    const d=await api('/admin/settings'); $('settingsDeadline').value=d.reportDeadline||'18:00';
    $('settingsDepartments').value=(d.departments||[]).join(', '); $('settingsNotifications').checked=d.missedReportNotifications!==false;
    $('settingsWorkingDays').value=(d.workingDays||[0,1,2,3,4]).join(',');
  }catch(e){setFormMsg($('settingsMsg'),e.message,false);}
}
on('settingsForm','submit',async e=>{
  e.preventDefault();
  try{
    await api('/admin/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      reportDeadline:$('settingsDeadline').value, departments:$('settingsDepartments').value.split(',').map(v=>v.trim()).filter(Boolean),
      missedReportNotifications:$('settingsNotifications').checked, workingDays:$('settingsWorkingDays').value.split(',').map(v=>Number(v.trim())).filter(Number.isInteger),
    })}); setFormMsg($('settingsMsg'),'Settings saved.',true);
  }catch(e){setFormMsg($('settingsMsg'),e.message,false);}
});

async function loadMyProfile(){
  const form=$('profileForm'); if(!form) return;
  try{
    const d=await api('/profile'); $('profileName').value=d.name||''; $('profileEmail').value=d.email||''; $('profileRole').value=(d.role||'').replace(/_/g,' '); $('profilePhone').value=d.phone||'';
    const cards=$('profileStats'); cards.innerHTML=''; [[d.totalReports||0,'Total reports'],[d.reportsThisMonth||0,'This month']].forEach(([v,l])=>{const c=document.createElement('div');c.className='stat-card glass-glow';c.innerHTML='<b></b><span></span>';c.firstChild.textContent=v;c.lastChild.textContent=l;cards.appendChild(c);});
  }catch(e){setFormMsg($('profileMsg'),e.message,false);}
}
on('profileForm','submit',async e=>{
  e.preventDefault(); const payload={name:$('profileName').value,phone:$('profilePhone').value}; if($('profilePassword').value) payload.password=$('profilePassword').value;
  try{await api('/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$('profilePassword').value='';setFormMsg($('profileMsg'),'Profile saved.',true);}catch(err){setFormMsg($('profileMsg'),err.message,false);}
});
