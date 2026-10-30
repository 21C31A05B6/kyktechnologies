if (!document.querySelector('script[src^="/js/pwa.js"]')) {
  const pwaScript = document.createElement("script");
  pwaScript.src = "/js/pwa.js?v=20261001-logo-2";
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

const urlToken = new URLSearchParams(window.location.search).get('token') || '';
let parentToken = '';
try {
  if (window.parent && window.parent !== window && window.parent.gToken) {
    parentToken = window.parent.gToken;
  }
} catch(e) {}
let openerToken = '';
try {
  if (window.opener && window.opener.gToken) {
    openerToken = window.opener.gToken;
  }
} catch(e) {}

let gToken = urlToken || localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LOGIN_USER_TOKEN_KEY) || parentToken || openerToken || '';
if (gToken) {
  try {
    localStorage.setItem(TOKEN_KEY, gToken);
    localStorage.setItem(LOGIN_USER_TOKEN_KEY, gToken);
  } catch(e) {}
}
let gAdmin=null;

function currentPage(){ return location.pathname.split('/').pop() || 'index.html'; }
function goToLogin(){
  if(currentPage()!==LOGIN_PAGE) {
    if(window.self !== window.top) return;
    location.replace('/'+LOGIN_PAGE);
  }
}

async function api(path,opts={}){
  const res=await fetch('/api'+path,{...opts,headers:{...(opts.headers||{}),Authorization:'Bearer '+gToken}});
  let d;
  try { d = await res.json(); } catch(e) { d = {}; }
  if(!res.ok){
    if(res.status === 401 && gToken){
      if(window.self === window.top) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(LOGIN_USER_TOKEN_KEY);
        sessionStorage.setItem('kyk_session_notice', d.error || 'Your session expired or you were logged in from another device.');
        goToLogin();
      }
    }
    throw new Error(d.error||'Request failed');
  }
  return d;
}
function setFormMsg(el,msg,ok){ if(!el) return; el.textContent=msg; el.className='form-msg show '+(ok?'ok':'err'); }

on('loginBtn','click',async()=>{
  const msg=$('loginMsg');
  const loginButton=$('loginBtn');
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
    gToken=d.token;
    localStorage.setItem(TOKEN_KEY,gToken);
    localStorage.setItem(LOGIN_USER_TOKEN_KEY,gToken);
    if (isAdminLogin || d.role && ROLE_HOME[d.role]) {
      const adminHome = ROLE_HOME[d.role] || 'admin.html';
      const redirectUrl = loginButton.dataset.redirect || `/${adminHome}`;
      location.replace(redirectUrl + (redirectUrl.indexOf('?') === -1 ? `?token=${encodeURIComponent(gToken)}` : `&token=${encodeURIComponent(gToken)}`));
    } else {
      const redirectUrl = loginButton.dataset.redirect || '/user-dashboard.html';
      location.replace(redirectUrl + (redirectUrl.indexOf('?') === -1 ? `?token=${encodeURIComponent(gToken)}` : `&token=${encodeURIComponent(gToken)}`));
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
  localStorage.removeItem(LOGIN_USER_TOKEN_KEY);
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
  overview:        {icon:'📊', label:'Command Centre'},
  jobs:            {icon:'💼', label:'Job Requisitions'},
  applications:    {icon:'📋', label:'Candidate Applications'},
  pipeline:        {icon:'🔄', label:'Recruitment Pipeline'},
  talent:          {icon:'👥', label:'Talent Pool'},
  contacts:        {icon:'✉️',  label:'Inquiries & Contacts'},
  newsletter:      {icon:'📧', label:'Newsletter'},
  insights:        {icon:'📝', label:'Insights & Articles'},
  activity:        {icon:'🔍', label:'Activity Stream'},
  admin_users:     {icon:'🔑', label:'System User Accounts'},
  my_attendance:   {icon:'⏱️', label:'My Attendance'},
  attendance:      {icon:'🗓️', label:'Attendance Register'},
  daily_report:    {icon:'📓', label:'Daily Report'},
  report_history:  {icon:'🗓️', label:'Report History'},
  reports_review:  {icon:'✅', label:'Reports Review'},
  employees:       {icon:'👤', label:'Employee Directory'},
  departments:     {icon:'🏢', label:'Departments & Shifts'},
  branches:        {icon:'📍', label:'Branches & Offices'},
  leave_mgmt:      {icon:'🌴', label:'Leave Management'},
  my_leaves:       {icon:'🏖️', label:'My Leaves'},
  payroll:         {icon:'💰', label:'Payroll & Salaries'},
  my_payslips:     {icon:'🧾', label:'My Payslips'},
  timesheets:      {icon:'⏱️', label:'Timesheet Approvals'},
  my_timesheets:   {icon:'📝', label:'My Timesheets'},
  recruitment:     {icon:'🎯', label:'Recruitment & ATS'},
  onboarding:      {icon:'🚀', label:'New Hire Onboarding'},
  documents:       {icon:'📁', label:'Document Vault'},
  my_documents:    {icon:'📂', label:'My Documents & Policies'},
  lifecycle:       {icon:'🔄', label:'Exit & Offboarding'},
  reports:         {icon:'📈', label:'HRMS Analytics & Reports'},
  audit_log:       {icon:'🛡️', label:'Security & Audit Log'},
  team:            {icon:'👥', label:'My Team'},
  team_attendance: {icon:'📅', label:'Team Attendance'},
  team_leaves:     {icon:'🌴', label:'Team Leaves'},
  team_goals:      {icon:'🎯', label:'Team Goals & KPIs'},
  team_reviews:    {icon:'⭐', label:'Team Reviews'},
  team_calendar:   {icon:'🗓️', label:'Team Calendar'},
  my_goals:        {icon:'🎯', label:'My Goals & KPIs'},
  performance:     {icon:'📈', label:'Performance'},
  settings:        {icon:'⚙️', label:'Settings'},
  my_profile:      {icon:'🪪', label:'My Profile'},
  communication:   {icon:'💬', label:'Chat & Meetings'},
};

/* Every role's dedicated home page. */
const ROLE_HOME={
  super_admin:     'admin.html',
  admin:           'admin.html',
  hr_manager:      'hr-dashboard.html',
  hr:              'hr-dashboard.html',
  recruiter:       'recruiter-dashboard.html',
  content_manager: 'content-dashboard.html',
  client:          'client-portal.html',
  team_lead:       'team-lead-dashboard.html',
  manager:         'team-lead-dashboard.html',
  employee:        'employee-dashboard.html',
  viewer:          'viewer-dashboard.html',
};

const HRMS_MODULE_TABS = new Set([
  'overview',
  'my_attendance',
  'attendance',
  'my_leaves',
  'leave_mgmt',
  'my_payslips',
  'payroll',
  'my_timesheets',
  'timesheets',
  'my_goals',
  'team_goals',
  'team_reviews',
  'team',
  'team_attendance',
  'team_leaves',
  'team_calendar',
  'employees',
  'departments',
  'branches',
  'recruitment',
  'onboarding',
  'my_documents',
  'documents',
  'lifecycle',
  'reports',
  'audit_log',
  'communication'
]);

window.HRMS_ALLOWED_ROLES = window.HRMS_ALLOWED_ROLES || new Set([
  'super_admin',
  'admin',
  'hr_manager',
  'hr',
  'team_lead',
  'manager',
  'employee',
  'recruiter',
  'content_manager'
]);
var HRMS_ALLOWED_ROLES = window.HRMS_ALLOWED_ROLES;

function isHrmsRole(role){
  return Boolean(role && HRMS_ALLOWED_ROLES.has(role));
}

const WORK_DASHBOARD_TABS = new Set([
  'overview',
  'daily_report',
  'report_history',
  'reports_review',
  'performance',
  'jobs',
  'applications',
  'pipeline',
  'talent',
  'contacts',
  'newsletter',
  'insights',
  'activity',
  'admin_users',
  'my_profile',
  'settings',
  'communication'
]);

let currentTab='overview';

function showDashboard(d){
  const home    = ROLE_HOME[d.role] || 'admin.html';
  const current = currentPage();
  const isHrms  = current === 'hrms-portal.html';

  // Only allowed HRMS roles (admin, hr, teamlead, employee, recruiter, content_manager) can access HRMS portal.
  // Clients and viewers are forbidden and redirected immediately to their home page.
  if(isHrms && !isHrmsRole(d.role)){
    location.replace('/' + home + (gToken ? '?token=' + encodeURIComponent(gToken) : ''));
    return;
  }

  if(!isHrms && current !== home && current !== 'communication.html'){
    location.replace('/' + home + (gToken ? '?token=' + encodeURIComponent(gToken) : ''));
    return;
  }
  if(current === LOGIN_PAGE) return; // safety net

  const ls = $('loginScreen'); if(ls) ls.style.display = 'none';
  const shell = $('dashShell'); if(!shell) return;
  shell.style.display = 'flex';
  ensureTopBarAndModals(isHrms, d.role);

  // Wire switcher back button if on HRMS page
  const backBtn = $('backToDashBtn');
  if(backBtn) backBtn.href = '/' + home + (gToken ? '?token=' + encodeURIComponent(gToken) : '');

  txt($('adminName'), d.name||'Admin');
  txt($('adminEmail'), d.email||'');
  const roleLabel = d.role || 'viewer';
  txt($('roleLabel'), roleLabel.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()));

  const userTabs = d.tabs || ['overview'];
  const allowedSet = isHrms ? HRMS_MODULE_TABS : WORK_DASHBOARD_TABS;
  let activeTabs = userTabs.filter(t => allowedSet.has(t));
  if(d.role === 'viewer' || d.role === 'user'){
    activeTabs = activeTabs.filter(t => t !== 'communication');
  }
  if(isHrms && isHrmsRole(d.role)){
    if(!activeTabs.includes('my_documents')) activeTabs.push('my_documents');
    if(['super_admin', 'admin', 'hr_manager', 'hr', 'team_lead', 'manager'].includes(d.role)){
      if(!activeTabs.includes('documents')) activeTabs.push('documents');
    }
  }
  if(!activeTabs.includes('overview') && userTabs.includes('overview')){
    activeTabs.unshift('overview');
  }
  if(!activeTabs.length) activeTabs = ['overview'];

  // Strict role privacy: strip any panels in the DOM that the user is not authorized to see
  document.querySelectorAll('.panel').forEach(p => {
    const tabName = p.id.replace('panel-', '');
    if(tabName && tabName !== 'overview' && !activeTabs.includes(tabName)){
      p.remove();
    }
  });

  ensureRolePanels(activeTabs);
  buildSidebar(activeTabs, isHrms, home, d.role);
  if(!isHrmsRole(d.role)){
    document.querySelectorAll('a[href*="hrms-portal"], .hrms-portal-link, .hrms-portal-btn, .hrms-sidebar-btn-box').forEach(el => el.remove());
  }
  const firstTab = activeTabs[0] || 'overview';
  switchTab(firstTab);
  loadNotifications();
  startTopbarClock();
}

function ensureTopBarAndModals(isHrms = false, role = ''){
  const userRole = role || (gAdmin && gAdmin.role) || '';
  const canAccessChat = !['viewer', 'user'].includes(userRole);
  const main=document.querySelector('.main-content');
  if(main && !$('hrmsTopbar')){
    const topbar=document.createElement('header');
    topbar.id='hrmsTopbar';
    topbar.className='topbar';
    topbar.style.cssText='display:flex;justify-content:space-between;align-items:center;padding:12px 20px;margin-bottom:24px;background:rgba(255,255,255,0.02);border:1px solid var(--glass-border);border-radius:14px;';
    const topTitle = isHrms ? 'KYK Enterprise HRMS' : 'KYK Work Dashboard';
    const topIcon = isHrms ? '🏢' : '💼';
    const chatBtnHtml = canAccessChat ? `
        <a href="/communication.html?token=${encodeURIComponent(gToken)}" target="_blank" rel="noopener" class="notif-btn" id="topbarChatBtn" title="Launch Chat & Video Meetings" style="background:rgba(232,98,44,0.12);border:1px solid var(--orange);border-radius:10px;padding:8px 12px;color:var(--orange);cursor:pointer;display:flex;align-items:center;gap:6px;text-decoration:none;font-weight:600;font-size:0.82rem;">
          💬 <span>Connect</span>
        </a>` : '';
    topbar.innerHTML=`
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:1.4rem;">${topIcon}</span>
        <div>
          <h2 id="topbarTitle" style="margin:0;font-family:var(--font-display);font-size:1.15rem;color:var(--ink);">${topTitle}</h2>
          <span style="font-size:0.75rem;color:var(--steel-light);">Warangal &bull; Hyderabad &bull; Remote Hub</span>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:14px;">
        <span id="topbarClock" style="font-family:monospace;font-size:0.84rem;color:var(--steel-light);"></span>
        ${chatBtnHtml}
        <div style="position:relative;">
          <button type="button" class="notif-btn" id="topbarNotifBtn" title="Announcements & Alerts" style="background:rgba(255,255,255,0.06);border:1px solid var(--glass-border);border-radius:10px;padding:8px 12px;color:var(--ink);cursor:pointer;display:flex;align-items:center;gap:6px;">
            🔔 <span id="topbarNotifBadge" class="notif-badge" style="display:none;background:var(--orange);color:#fff;border-radius:999px;padding:2px 7px;font-size:0.7rem;font-weight:700;">0</span>
          </button>
          <div id="topbarNotifDrawer" class="notif-drawer" style="display:none;position:absolute;top:calc(100% + 8px);right:0;width:340px;background:#0f121a;border:1px solid var(--glass-border);border-radius:14px;box-shadow:0 18px 40px rgba(0,0,0,0.8);z-index:999;padding:16px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
              <b style="font-size:0.88rem;">Announcements &amp; Alerts</b>
              <button class="small-btn" id="topbarMarkAllRead">Mark all read</button>
            </div>
            <div id="topbarNotifItems" style="max-height:280px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;"></div>
          </div>
        </div>
      </div>
    `;
    main.insertBefore(topbar,main.firstChild);
    on('topbarNotifBtn','click',()=>{
      const d=$('topbarNotifDrawer');
      if(d) d.style.display=d.style.display==='none'?'block':'none';
    });
    on('topbarMarkAllRead','click',async()=>{
      try{ await api('/notifications/mark-read',{method:'POST'}); loadNotifications(); }catch(e){}
    });
    document.addEventListener('click',e=>{
      const d=$('topbarNotifDrawer'), b=$('topbarNotifBtn');
      if(d&&b&&!d.contains(e.target)&&!b.contains(e.target)){ d.style.display='none'; }
    });
  }

  if(!$('hrmsModalOverlay')){
    const modal=document.createElement('div');
    modal.id='hrmsModalOverlay';
    modal.className='modal-overlay';
    modal.innerHTML=`
      <div class="modal-box" id="hrmsModalBox">
        <button class="modal-close" id="hrmsModalClose">&times;</button>
        <div id="hrmsModalBody"></div>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('#hrmsModalClose').addEventListener('click',closeHrmsModal);
    modal.addEventListener('click',e=>{ if(e.target===modal) closeHrmsModal(); });
  }
}

function openHrmsModal(titleHtml,bodyHtml,isLarge=false){
  const overlay=$('hrmsModalOverlay'), box=$('hrmsModalBox'), body=$('hrmsModalBody');
  if(!overlay||!box||!body) return;
  box.className='modal-box'+(isLarge?' modal-lg':'');
  body.innerHTML=`<h3 style="margin-block-end:16px;font-family:var(--font-display);">${titleHtml}</h3>${bodyHtml}`;
  overlay.classList.add('active');
}
function closeHrmsModal(){
  const overlay=$('hrmsModalOverlay');
  if(overlay) overlay.classList.remove('active');
}

function ensureRolePanels(tabs){
  const main=document.querySelector('.main-content'); if(!main) return;
  const panels={
    employees:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Employee Directory</h3>
        <div style="display:flex;gap:8px;">
          <a href="/api/reports/export/employees" class="btn btn-outline btn-sm" download>📥 Export CSV</a>
        </div>
      </div>
      <div class="toolbar"><input id="employeeSearch" placeholder="Search name, email, department, code…"/><button class="btn btn-outline" id="employeeRefresh">Refresh</button></div>
      <table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Department</th><th>Status</th></tr></thead><tbody id="employeesBody"></tbody></table>`,
    departments:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Departments, Designations &amp; Shifts</h3>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary btn-sm" id="addDeptBtn">+ Add Department</button>
          <button class="btn btn-outline btn-sm" id="addDesigBtn">+ Add Designation</button>
          <button class="btn btn-outline btn-sm" id="addShiftBtn">+ Add Shift</button>
        </div>
      </div>
      <div class="hrms-section">
        <h4>Departments</h4>
        <table><thead><tr><th>Code</th><th>Name</th><th>Branch</th><th>Active</th></tr></thead><tbody id="deptsBody"></tbody></table>
      </div>
      <div class="hrms-section" style="margin-top:24px;">
        <h4>Designations</h4>
        <table><thead><tr><th>Title</th><th>Department</th><th>Active</th></tr></thead><tbody id="desigsBody"></tbody></table>
      </div>
      <div class="hrms-section" style="margin-top:24px;">
        <h4>Work Shifts &amp; Grace Periods</h4>
        <table><thead><tr><th>Shift Name</th><th>Timing</th><th>Grace Period</th><th>Half-Day Hours</th><th>Status</th></tr></thead><tbody id="shiftsBody"></tbody></table>
      </div>`,
    branches:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Company &amp; Branch Locations</h3>
        <button class="btn btn-primary btn-sm" id="addBranchBtn">+ Add Branch</button>
      </div>
      <div class="form-card" id="companyOverviewCard" style="margin-bottom:20px;"></div>
      <h4>Offices &amp; Work Locations</h4>
      <table><thead><tr><th>Code</th><th>Branch Name</th><th>City / Region</th><th>Country</th><th>Phone</th><th>GSTIN / Tax ID</th><th>Status</th></tr></thead><tbody id="branchesBody"></tbody></table>`,
    leave_mgmt:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Leave Management</h3>
        <button class="btn btn-outline btn-sm" id="refreshLeaveMgmt">Refresh</button>
      </div>
      <div class="stat-cards" id="leaveMgmtStats"></div>
      <div class="filter-bar" style="margin-top:16px;">
        <select id="leaveStatusFilter"><option value="">All Statuses</option><option value="pending" selected>Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>
      </div>
      <h4>Leave Requests</h4>
      <table><thead><tr><th>Employee</th><th>Leave Type</th><th>Duration</th><th>Days</th><th>Reason</th><th>Status</th><th>Actions</th></tr></thead><tbody id="leaveMgmtBody"></tbody></table>
      <div class="hrms-section" style="margin-top:28px;">
        <h4>Company Leave Types &amp; Annual Quotas</h4>
        <table><thead><tr><th>Leave Type</th><th>Code</th><th>Annual Quota</th><th>Carry Forward</th><th>Paid</th></tr></thead><tbody id="leaveTypesBody"></tbody></table>
      </div>`,
    my_leaves:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>My Leaves &amp; Time Off</h3>
        <button class="btn btn-primary" id="applyLeaveBtn">+ Apply for Leave</button>
      </div>
      <div class="leave-balances-grid" id="myLeaveBalances"></div>
      <h4>My Leave Applications</h4>
      <table><thead><tr><th>Type</th><th>Duration</th><th>Days</th><th>Reason</th><th>Status</th><th>Applied On</th><th>Action</th></tr></thead><tbody id="myLeavesBody"></tbody></table>`,
    payroll:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Payroll &amp; Salary Operations</h3>
        <button class="btn btn-primary" id="generatePayrollBtn">+ Run Monthly Payroll</button>
      </div>
      <div class="stat-cards" id="payrollStats"></div>
      <h4 style="margin-top:20px;">Monthly Payroll Runs</h4>
      <table><thead><tr><th>Month / Year</th><th>Employees</th><th>Gross Total</th><th>Deductions</th><th>Net Payout</th><th>Status</th><th>Actions</th></tr></thead><tbody id="payrollRunsBody"></tbody></table>
      <div class="hrms-section" style="margin-top:28px;">
        <h4>Employee Salary Structures</h4>
        <table><thead><tr><th>Employee</th><th>CTC (Annual)</th><th>Basic (Monthly)</th><th>HRA</th><th>Allowances</th><th>PF</th><th>Tax</th><th>Net Take-Home</th></tr></thead><tbody id="salaryStructuresBody"></tbody></table>
      </div>`,
    my_payslips:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>My Payslips</h3>
      </div>
      <table><thead><tr><th>Pay Period</th><th>Basic</th><th>Allowances</th><th>Deductions</th><th>Net Salary</th><th>Status</th><th>Action</th></tr></thead><tbody id="myPayslipsBody"></tbody></table>`,
    timesheets:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Timesheet Approvals</h3>
        <button class="btn btn-outline btn-sm" id="refreshTimesheetsBtn">Refresh</button>
      </div>
      <div class="stat-cards" id="timesheetStats"></div>
      <h4 style="margin-top:20px;">Timesheet Submissions</h4>
      <table><thead><tr><th>Employee</th><th>Week Ending</th><th>Client / Project</th><th>Hours</th><th>Status</th><th>Actions</th></tr></thead><tbody id="timesheetsBody"></tbody></table>`,
    my_timesheets:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>My Weekly Timesheet</h3>
      </div>
      <form id="timesheetSubmitForm" class="form-card" style="margin-bottom:24px;">
        <div class="filter-bar">
          <div class="field"><label>Week Starting Date *</label><input type="date" id="tsWeekStart" required/></div>
          <div class="field"><label>Project / Client Name *</label><input id="tsProject" placeholder="e.g. Enterprise HRMS" required/></div>
        </div>
        <label style="font-weight:600;margin-top:10px;display:block;">Daily Hours Breakdown (Mon – Fri)</label>
        <div style="display:flex;gap:12px;margin:10px 0;flex-wrap:wrap;">
          <div><small style="color:var(--steel-light);">Mon</small><br/><input type="number" id="tsMon" min="0" max="16" step="0.5" value="8" style="width:70px;"/></div>
          <div><small style="color:var(--steel-light);">Tue</small><br/><input type="number" id="tsTue" min="0" max="16" step="0.5" value="8" style="width:70px;"/></div>
          <div><small style="color:var(--steel-light);">Wed</small><br/><input type="number" id="tsWed" min="0" max="16" step="0.5" value="8" style="width:70px;"/></div>
          <div><small style="color:var(--steel-light);">Thu</small><br/><input type="number" id="tsThu" min="0" max="16" step="0.5" value="8" style="width:70px;"/></div>
          <div><small style="color:var(--steel-light);">Fri</small><br/><input type="number" id="tsFri" min="0" max="16" step="0.5" value="8" style="width:70px;"/></div>
        </div>
        <div class="field"><label>Work Summary / Deliverables</label><textarea id="tsTasks" rows="2" placeholder="Summary of sprint tasks completed"></textarea></div>
        <button type="submit" class="btn btn-primary">Submit Timesheet for Review</button>
        <div class="form-msg" id="tsMsg"></div>
      </form>
      <h4>Submitted Timesheet History</h4>
      <table><thead><tr><th>Week Starting</th><th>Project</th><th>Hours</th><th>Status</th><th>Submitted On</th><th>Manager Notes</th></tr></thead><tbody id="myTimesheetsBody"></tbody></table>`,
    recruitment:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Recruitment &amp; Applicant Pipeline</h3>
        <button class="btn btn-primary btn-sm" id="recruitmentRefresh">Refresh</button>
      </div>
      <div class="stat-cards" id="recruitmentStats"></div>
      <h4 style="margin-top:20px;">Candidate Applications</h4>
      <table><thead><tr><th>Candidate</th><th>Job Applied</th><th>Status</th><th>Resume</th><th>Actions</th></tr></thead><tbody id="recruitmentAppsBody"></tbody></table>`,
    onboarding:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>New Hire Onboarding Checklists</h3>
      </div>
      <div id="onboardingList"></div>`,
    documents:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px;">
        <div>
          <h3 style="margin:0;">Document Vault &amp; Employee Verification</h3>
          <p style="margin:4px 0 0;font-size:0.84rem;color:var(--steel-light);">Manager &amp; Admin verification desk: Review, approve, or reject employee credentials and compliance files.</p>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary btn-sm" id="addDocBtn">+ Upload Corporate Record</button>
          <button class="btn btn-outline btn-sm" id="refreshDocsBtn">Refresh</button>
        </div>
      </div>
      <div class="stat-cards" id="docsReviewStats" style="margin-bottom:20px;"></div>
      <div class="filter-bar" style="margin-bottom:16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
        <select id="docStatusFilter">
          <option value="">All Verification Statuses</option>
          <option value="pending" selected>⏳ Pending Review Only</option>
          <option value="approved">✓ Approved / Verified</option>
          <option value="rejected">✗ Rejected</option>
        </select>
        <select id="docCategoryFilter">
          <option value="">All Categories</option>
          <option value="career">Career / Resume</option>
          <option value="identity">Identity (Aadhaar / PAN / Passport)</option>
          <option value="joining">Joining &amp; Offer Letters</option>
          <option value="contract">Employment Agreement</option>
          <option value="educational">Educational Certificates</option>
          <option value="experience">Experience &amp; Relieving</option>
          <option value="financial">Salary &amp; Bank Details</option>
          <option value="policy">Company Policy</option>
        </select>
        <input id="docSearchQuery" placeholder="Search employee name, code, title…" style="max-width:240px;"/>
        <button class="btn btn-outline btn-sm" id="applyDocsFilterBtn">Filter</button>
      </div>
      <div id="docExpiryAlert" style="display:none;background:rgba(229,169,59,.15);border:1px solid #e5a93b;border-radius:8px;padding:12px;margin-bottom:16px;color:#e5a93b;"></div>
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Document Type / Title</th>
            <th>Category</th>
            <th>Version</th>
            <th>Uploaded Date</th>
            <th>Status</th>
            <th>File</th>
            <th>Manager Review &amp; Actions</th>
          </tr>
        </thead>
        <tbody id="docsBody"></tbody>
      </table>`,
    my_documents:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px;">
        <div>
          <h3 style="margin:0;">My Documents &amp; Policy Acknowledgment</h3>
          <p style="margin:4px 0 0;font-size:0.84rem;color:var(--steel-light);">Upload your mandatory credentials (Resume, ID Proof, Aadhaar, PAN, Certificates, Slips, etc.) for manager/admin verification.</p>
        </div>
        <button class="btn btn-primary btn-sm" id="myDocUploadBtn" style="display:flex;align-items:center;gap:6px;">
          <span>📤</span> <span>Upload Document</span>
        </button>
      </div>
      <div class="stat-cards" id="myDocsStats" style="margin-bottom:20px;"></div>
      <div id="myDocRejectionBanner" style="display:none;background:rgba(226,92,92,0.12);border:1px solid #e25c5c;border-radius:12px;padding:16px;margin-bottom:22px;">
        <div style="display:flex;align-items:flex-start;gap:12px;">
          <span style="font-size:1.6rem;line-height:1;">⚠️</span>
          <div>
            <h4 style="margin:0 0 6px;color:#e25c5c;font-size:1rem;">Document(s) Rejected — Action Required</h4>
            <div id="myDocRejectionList" style="font-size:0.86rem;color:var(--steel-light);"></div>
          </div>
        </div>
      </div>
      <div class="hrms-section" style="margin-bottom:28px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
          <h4 style="margin:0;font-size:1.05rem;">Employment Verification Credentials (16 Official Slots)</h4>
          <span id="checklistCompletionBadge" class="badge badge-pending">Loading…</span>
        </div>
        <p style="font-size:0.8rem;color:var(--steel-light);margin-top:0;margin-bottom:14px;">Review all 16 required documents. If any document is marked "Rejected" by your manager or admin, click "Re-upload" to submit an updated copy.</p>
        <div id="mandatoryDocsGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;"></div>
      </div>
      <div class="hrms-section" style="margin-bottom:28px;">
        <h4 style="margin-bottom:12px;font-size:1.05rem;">All Uploaded Documents &amp; Version History</h4>
        <table>
          <thead>
            <tr>
              <th>Document</th>
              <th>Category</th>
              <th>Version</th>
              <th>Uploaded On</th>
              <th>Status</th>
              <th>Reviewer Notes / Feedback</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="myDocsBody"></tbody>
        </table>
      </div>
      <div class="hrms-section">
        <h4 style="margin-bottom:12px;font-size:1.05rem;">Company Policies &amp; Agreements</h4>
        <div id="policiesList"></div>
      </div>`,
    lifecycle:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Employee Offboarding &amp; Exit Management</h3>
      </div>
      <div class="stat-cards" id="lifecycleStats"></div>
      <h4 style="margin-top:20px;">Resignation &amp; Exit Records</h4>
      <table><thead><tr><th>Employee</th><th>Notice Date</th><th>Last Working Day</th><th>Notice Days</th><th>Knowledge Transfer</th><th>Asset Return</th><th>Settlement</th><th>Account Status</th><th>Action</th></tr></thead><tbody id="lifecycleBody"></tbody></table>`,
    reports:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>HRMS Analytics &amp; Reports</h3>
      </div>
      <div class="stat-cards" id="reportsStats"></div>
      <div class="hrms-section" style="margin-top:20px;">
        <h4>Department Headcount Breakdown</h4>
        <div id="deptHeadcountBars"></div>
      </div>
      <div class="hrms-section" style="margin-top:24px;">
        <h4>Download Data Reports (CSV)</h4>
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;">
          <a href="/api/reports/export/employees" class="btn btn-outline btn-sm" download>📥 Export Employees Directory</a>
          <a href="/api/reports/export/attendance" class="btn btn-outline btn-sm" download>📥 Export Attendance Register</a>
          <a href="/api/reports/export/leaves" class="btn btn-outline btn-sm" download>📥 Export Leave Utilization</a>
          <a href="/api/reports/export/payroll" class="btn btn-outline btn-sm" download>📥 Export Payroll Summary</a>
        </div>
      </div>`,
    audit_log:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Security Audit &amp; Activity Log</h3>
        <a href="/api/admin/export-backup" class="btn btn-outline btn-sm" download>💾 Export Full JSON Database Backup</a>
      </div>
      <table><thead><tr><th>Timestamp</th><th>Actor</th><th>Role</th><th>Action</th><th>IP Address</th><th>Details</th></tr></thead><tbody id="auditLogBody"></tbody></table>`,
    team:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>My Team Directory</h3>
      </div>
      <div class="stat-cards" id="teamStats"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:18px;" id="teamGrid"></div>`,
    team_attendance:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Team Attendance &amp; Shift Register</h3>
        <div class="filter-bar" style="margin-bottom:0;">
          <input type="date" id="teamAttDate"/>
          <button class="btn btn-primary btn-sm" id="refreshTeamAttBtn">View</button>
        </div>
      </div>
      <div class="stat-cards" id="teamAttStats" style="margin-top:16px;"></div>
      <table><thead><tr><th>Employee</th><th>Shift</th><th>Punch In</th><th>Punch Out</th><th>Total Hours</th><th>Status</th></tr></thead><tbody id="teamAttBody"></tbody></table>`,
    team_leaves:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Team Leave Requests</h3>
      </div>
      <table><thead><tr><th>Team Member</th><th>Leave Type</th><th>Duration</th><th>Days</th><th>Reason</th><th>Status</th><th>Actions</th></tr></thead><tbody id="teamLeavesBody"></tbody></table>`,
    team_goals:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Team Performance Goals &amp; KPIs</h3>
        <button class="btn btn-primary btn-sm" id="addTeamGoalBtn">+ Assign Goal</button>
      </div>
      <div id="teamGoalsList"></div>`,
    team_reviews:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Appraisal Reviews &amp; Ratings</h3>
      </div>
      <div id="teamReviewsList"></div>`,
    team_calendar:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>Team Schedule &amp; Leave Calendar</h3>
      </div>
      <div id="teamCalendarView" class="form-card"></div>`,
    my_goals:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>My Goals &amp; Performance Review</h3>
      </div>
      <div id="myGoalsList"></div>
      <div class="hrms-section" style="margin-top:28px;">
        <h4>Annual / Periodic Appraisal Review</h4>
        <div id="myReviewContainer"></div>
      </div>`,
    performance:`<h3>Performance Summary</h3><div class="toolbar"><input type="month" id="performanceMonth"/><button class="btn btn-primary" id="performanceRefresh">Refresh</button></div><table><thead><tr><th>Employee</th><th>Department</th><th>Reports</th><th>Submission rate</th><th>Status</th></tr></thead><tbody id="performanceBody"></tbody></table>`,
    settings:`<h3>Portal Settings</h3><form id="settingsForm" class="form-card" style="max-inline-size:660px"><div class="field"><label>Daily report deadline</label><input type="time" id="settingsDeadline"/></div><div class="field"><label>Departments (comma separated)</label><input id="settingsDepartments"/></div><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="settingsNotifications"/> Email alert for missed reports</label><div class="field"><label>Working days</label><input id="settingsWorkingDays" placeholder="0,1,2,3,4"/></div><button class="btn btn-primary" type="submit">Save settings</button><div class="form-msg" id="settingsMsg"></div></form>`,
    my_profile:`<h3>My Profile</h3><form id="profileForm" class="form-card" style="max-inline-size:660px"><div class="field"><label>Full name</label><input id="profileName" required/></div><div class="field"><label>Email</label><input id="profileEmail" disabled/></div><div class="field"><label>Role</label><input id="profileRole" disabled/></div><div class="field"><label>Phone</label><input id="profilePhone"/></div><div class="field"><label>New password</label><input id="profilePassword" type="password" minlength="8" autocomplete="new-password"/></div><div id="profileStats" class="stat-cards"></div><button class="btn btn-primary" type="submit">Save profile</button><div class="form-msg" id="profileMsg"></div></form>`,
    communication:`
      <div class="panel-header-row" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h3>KYK Connect — Enterprise Chat &amp; Video Meetings</h3>
        <div style="display:flex;gap:8px;">
          <a href="/communication.html?token=${encodeURIComponent(gToken)}" class="btn btn-primary btn-sm" target="_blank" rel="noopener">⛶ Open Fullscreen App</a>
        </div>
      </div>
      <div style="height:calc(100vh - 220px);border-radius:14px;overflow:hidden;border:1px solid var(--glass-border);background:var(--bg);">
        <iframe src="/communication.html?token=${encodeURIComponent(gToken)}" style="width:100%;height:100%;border:none;display:block;" title="KYK Communication Platform"></iframe>
      </div>`,
  };
  tabs.forEach(tab=>{
    if(!panels[tab] || $('panel-'+tab)) return;
    const panel=document.createElement('div'); panel.className='panel'; panel.id='panel-'+tab; panel.innerHTML=panels[tab]; main.appendChild(panel);
  });
}

function buildSidebar(tabs, isHrms = false, home = 'admin.html', role = ''){
  const nav=$('sidebarNav'); if(!nav) return;
  nav.innerHTML='';

  // In Work Dashboard, add a top button to jump directly to HRMS Portal only for HRMS-allowed roles
  const userRole = role || (gAdmin && gAdmin.role) || '';
  if(!isHrms && isHrmsRole(userRole)){
    const hrmsBox = document.createElement('div');
    hrmsBox.className = 'hrms-sidebar-btn-box';
    hrmsBox.style.cssText = 'padding:0 8px 12px;margin-bottom:8px;border-bottom:1px solid var(--glass-border);';
    hrmsBox.innerHTML = `
      <a href="/hrms-portal.html${gToken ? '?token=' + encodeURIComponent(gToken) : ''}" class="hrms-portal-btn" style="display:flex;align-items:center;justify-content:center;gap:8px;padding:9px 12px;background:rgba(232,98,44,0.12);border:1px solid var(--orange);border-radius:10px;color:var(--orange);font-size:0.8rem;text-decoration:none;font-weight:700;">
        <span>🏢</span> <span>HRMS Portal →</span>
      </a>
    `;
    nav.appendChild(hrmsBox);
  } else {
    document.querySelectorAll('a[href*="hrms-portal"], .hrms-portal-link, .hrms-portal-btn, .hrms-sidebar-btn-box').forEach(el => el.remove());
  }

  tabs.forEach(t=>{
    const m=TAB_META[t]; if(!m) return;
    if(!$('panel-'+t)) return;
    const btn=document.createElement('button');
    btn.dataset.tab=t;
    btn.innerHTML=`<span class="tab-icon">${m.icon}</span><span>${m.label}</span>`;
    btn.addEventListener('click',()=>switchTab(t));
    nav.appendChild(btn);
  });
}

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
    departments:loadDepartments, branches:loadBranches,
    leave_mgmt:loadLeaveMgmt, my_leaves:loadMyLeaves,
    payroll:loadPayroll, my_payslips:loadMyPayslips,
    timesheets:loadTimesheets, my_timesheets:loadMyTimesheets,
    recruitment:loadRecruitment, onboarding:loadOnboarding,
    documents:loadDocuments, my_documents:loadMyDocuments,
    lifecycle:loadLifecycle, reports:loadReports,
    audit_log:loadAuditLog, team:loadTeam,
    team_attendance:loadTeamAttendance, team_leaves:loadTeamLeaves,
    team_goals:loadTeamGoals, team_reviews:loadTeamReviews,
    team_calendar:loadTeamCalendar, my_goals:loadMyGoals,
  };
  return Object.assign(defaults, window.TAB_LOADER_OVERRIDES||{});
}

function switchTab(tab){
  currentTab=tab;
  document.querySelectorAll('.sidebar nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  const panel=$('panel-'+tab);
  if(panel) panel.classList.add('active');
  if(tab === 'communication' && panel && gToken){
    const iframe = panel.querySelector('iframe');
    if(iframe && (!iframe.src || iframe.src.indexOf('token=') === -1)){
      iframe.src = '/communication.html?token=' + encodeURIComponent(gToken);
    }
  }
  const m=TAB_META[tab];
  if(m && $('topbarTitle')) $('topbarTitle').textContent=m.label;
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
  const role = (gAdmin && gAdmin.role) || '';

  const isHrms = currentPage() === 'hrms-portal.html';

  if(isHrms){
    // ────────────── PURE HRMS OVERVIEW ──────────────
    if(role === 'employee' || role === 'content_manager' || role === 'recruiter'){
      try{
        const [att, balData, timesheets, goals] = await Promise.all([
          api('/attendance/today').catch(()=>({})),
          api('/leave/balances').catch(()=>({})),
          api('/timesheets/my').catch(()=>([])),
          api('/performance/my-goals').catch(()=>([])),
        ]);

        const bals = balData.balances || {};
        const totalAvailLeaves = Object.values(bals).reduce((acc, v)=> acc + (v.available ?? v.quota ?? 0), 0);
        const pendingTs = (timesheets||[]).filter(t=>t.status==='submitted').length;
        const activeGoals = (goals||[]).filter(g=>g.status!=='completed').length;
        const isCheckedIn = att && att.checkIn;
        const isCheckedOut = att && att.checkOut;
        let checkInStr = 'Not Punched (Ready)';
        if(isCheckedOut){
          checkInStr = 'Completed (' + (att.workedFormatted || fmtExactDuration(att.workedSeconds)) + ')';
        } else if(isCheckedIn){
          checkInStr = 'Checked In (' + fmtTimeIST(att.checkIn) + ')';
        }

        cards.innerHTML = '';
        [
          [checkInStr, 'Today\'s Attendance'],
          [totalAvailLeaves + ' Days', 'Available Leaves'],
          [pendingTs + ' Pending', 'Weekly Timesheets'],
          [activeGoals + ' Active', 'Performance Goals'],
        ].forEach(([v,l])=>{
          const d=document.createElement('div');
          d.className='stat-card glass-glow';
          d.innerHTML=`<b>${v}</b><span>${l}</span>`;
          cards.appendChild(d);
        });

        const chartCard = document.querySelector('.chart-card');
        if(chartCard){
          const extraButtons = role === 'recruiter' ? `
            <button type="button" class="btn btn-outline" onclick="switchTab('recruitment')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">🎯</span>
              <div><b>Recruitment & ATS</b><br/><small style="color:var(--steel-light);">Candidate pipeline & hiring</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('onboarding')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">🚀</span>
              <div><b>New Hire Onboarding</b><br/><small style="color:var(--steel-light);">Onboarding tasks & checklists</small></div>
            </button>
          ` : `
            <button type="button" class="btn btn-outline" onclick="switchTab('my_goals')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">🎯</span>
              <div><b>Goals & Appraisal</b><br/><small style="color:var(--steel-light);">Update progress & self review</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('my_documents')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">📂</span>
              <div><b>Documents & Policies</b><br/><small style="color:var(--steel-light);">View policies & credentials</small></div>
            </button>
          `;
          chartCard.innerHTML = `
            <h4 style="font-family:var(--font-display);margin-bottom:14px;color:var(--ink);">⚡ Quick HRMS Actions</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin-bottom:20px;">
              <button type="button" class="btn btn-outline" onclick="switchTab('my_attendance')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">⏱️</span>
                <div><b>My Attendance</b><br/><small style="color:var(--steel-light);">Punch in / Check history</small></div>
              </button>
              <button type="button" class="btn btn-outline" onclick="switchTab('my_leaves')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">🏖️</span>
                <div><b>Leave Management</b><br/><small style="color:var(--steel-light);">Apply for leave & check balance</small></div>
              </button>
              <button type="button" class="btn btn-outline" onclick="switchTab('my_payslips')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">🧾</span>
                <div><b>My Payslips</b><br/><small style="color:var(--steel-light);">View & print salary slips</small></div>
              </button>
              <button type="button" class="btn btn-outline" onclick="switchTab('my_timesheets')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">📝</span>
                <div><b>Weekly Timesheet</b><br/><small style="color:var(--steel-light);">Log work hours & submit</small></div>
              </button>
              ${extraButtons}
            </div>
          `;
        }
      }catch(e){console.error('HRMS employee overview error', e);}
      return;
    }

    if(role === 'team_lead' || role === 'manager'){
      try{
        const [team, teamAtt, timesheets, leaves] = await Promise.all([
          api('/manager/team').catch(()=>([])),
          api('/manager/team-attendance').catch(()=>({})),
          api('/manager/timesheets').catch(()=>([])),
          api('/manager/leave').catch(()=>([])),
        ]);

        const teamCount = (team||[]).length;
        const presentCount = (teamAtt && teamAtt.present) || 0;
        const pendingTs = (timesheets||[]).filter(t=>t.status==='submitted').length;
        const pendingLeaves = (leaves||[]).filter(l=>l.status==='pending').length;

        cards.innerHTML = '';
        [
          [teamCount + ' Members', 'Team Size'],
          [presentCount + ' / ' + teamCount, 'Present Today'],
          [pendingTs + ' Pending', 'Timesheets to Review'],
          [pendingLeaves + ' Pending', 'Leave Requests'],
        ].forEach(([v,l])=>{
          const d=document.createElement('div');
          d.className='stat-card glass-glow';
          d.innerHTML=`<b>${v}</b><span>${l}</span>`;
          cards.appendChild(d);
        });

        const chartCard = document.querySelector('.chart-card');
        if(chartCard){
          chartCard.innerHTML = `
            <h4 style="font-family:var(--font-display);margin-bottom:14px;color:var(--ink);">⚡ Quick Team HRMS Actions</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;">
              <button type="button" class="btn btn-outline" onclick="switchTab('team_attendance')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">📅</span>
                <div><b>Team Attendance</b><br/><small style="color:var(--steel-light);">Shift register & punches</small></div>
              </button>
              <button type="button" class="btn btn-outline" onclick="switchTab('timesheets')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">⏱️</span>
                <div><b>Timesheet Approvals</b><br/><small style="color:var(--steel-light);">${pendingTs} pending submissions</small></div>
              </button>
              <button type="button" class="btn btn-outline" onclick="switchTab('team_leaves')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">🌴</span>
                <div><b>Leave Approvals</b><br/><small style="color:var(--steel-light);">${pendingLeaves} pending requests</small></div>
              </button>
              <button type="button" class="btn btn-outline" onclick="switchTab('team_goals')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.4rem;">🎯</span>
                <div><b>Team Goals & KPIs</b><br/><small style="color:var(--steel-light);">Assign goals & track progress</small></div>
              </button>
            </div>
          `;
        }
      }catch(e){console.error('HRMS manager overview error', e);}
      return;
    }

    // HR Manager / Admin HRMS Overview
    try{
      const summary = await api('/reports/analytics-summary').catch(()=>({}));
      cards.innerHTML = '';
      [
        [summary.totalEmployees ?? '12', 'Total Headcount'],
        ['₹' + (summary.totalMonthlyPayroll ? summary.totalMonthlyPayroll.toLocaleString('en-IN') : '7,20,000'), 'Monthly Payroll Cost'],
        [(summary.punctualityRate ?? '94.2') + '%', 'Punctuality Rate'],
        [(summary.pendingLeaves ?? '2') + ' Requests', 'Pending Leaves'],
      ].forEach(([v,l])=>{
        const d=document.createElement('div');
        d.className='stat-card glass-glow';
        d.innerHTML=`<b>${v}</b><span>${l}</span>`;
        cards.appendChild(d);
      });

      const chartCard = document.querySelector('.chart-card');
      if(chartCard){
        chartCard.innerHTML = `
          <h4 style="font-family:var(--font-display);margin-bottom:14px;color:var(--ink);">⚡ HR Operations Hub</h4>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin-bottom:20px;">
            <button type="button" class="btn btn-outline" onclick="switchTab('employees')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">👤</span>
              <div><b>Employee Directory</b><br/><small style="color:var(--steel-light);">Add & manage staff</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('leave_mgmt')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">🌴</span>
              <div><b>Leave Approvals</b><br/><small style="color:var(--steel-light);">Approve time-off & quotas</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('payroll')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">💰</span>
              <div><b>Payroll & Salaries</b><br/><small style="color:var(--steel-light);">Run monthly pay slips</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('documents')" style="text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
              <span style="font-size:1.4rem;">📁</span>
              <div><b>Document Vault</b><br/><small style="color:var(--steel-light);">Corporate policies & credentials</small></div>
            </button>
          </div>
        `;
      }
    }catch(e){console.error('HRMS admin overview error', e);}
    return;
  }

  // ────────────── PURE WORK / OPERATIONS DASHBOARD OVERVIEW ──────────────
  if(role === 'employee'){
    try{
      const history = await api('/reports/my-history').catch(()=>[]);
      const todayIso = new Date().toISOString().slice(0,10);
      const todayReport = (history||[]).find(r=>r.date===todayIso);
      const totalSubmitted = (history||[]).length;

      cards.innerHTML = '';
      [
        [todayReport ? '✓ Submitted' : 'Pending Today', 'Daily Work Report'],
        [todayReport ? (todayReport.hours ?? '8') + ' Hours' : '—', 'Hours Logged Today'],
        [totalSubmitted + ' Reports', 'Total Reports Submitted'],
        [todayReport ? (todayReport.mood || 'Good').toUpperCase() : 'Ready', 'Current Work Pulse'],
      ].forEach(([v,l])=>{
        const d=document.createElement('div');
        d.className='stat-card glass-glow';
        d.innerHTML=`<b>${v}</b><span>${l}</span>`;
        cards.appendChild(d);
      });

      const chartCard = document.querySelector('.chart-card');
      if(chartCard){
        chartCard.innerHTML = `
          <div style="background:rgba(232,98,44,0.08);border:1px solid rgba(232,98,44,0.25);border-radius:12px;padding:18px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
            <div>
              <h4 style="margin:0 0 6px;color:var(--orange);font-family:var(--font-display);">🏢 Enterprise HRMS Portal</h4>
              <p style="margin:0;font-size:0.85rem;color:var(--steel-light);">Manage your daily attendance check-in/out, leave requests, monthly payslips, and weekly timesheets in the dedicated HRMS Portal.</p>
            </div>
            <a href="/hrms-portal.html${gToken ? '?token=' + encodeURIComponent(gToken) : ''}" class="btn btn-primary" style="font-size:0.85rem;padding:9px 18px;white-space:nowrap;">Open HRMS Portal →</a>
          </div>
          <div style="display:flex;gap:12px;flex-wrap:wrap;">
            <button type="button" class="btn btn-outline" onclick="switchTab('daily_report')" style="flex:1;min-width:200px;text-align:left;padding:14px;display:flex;align-items:center;gap:12px;">
              <span style="font-size:1.5rem;">📓</span>
              <div><b>Submit Daily Report</b><br/><small style="color:var(--steel-light);">Log today's completed work & blockers</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('report_history')" style="flex:1;min-width:200px;text-align:left;padding:14px;display:flex;align-items:center;gap:12px;">
              <span style="font-size:1.5rem;">🗓️</span>
              <div><b>View Report History</b><br/><small style="color:var(--steel-light);">Review past work submissions</small></div>
            </button>
          </div>
        `;
      }
    }catch(e){console.error('Work employee overview error', e);}
    return;
  }

  if(role === 'team_lead' || role === 'manager'){
    try{
      const [reviewData, myHistory] = await Promise.all([
        api('/reports/review').catch(()=>([])),
        api('/reports/my-history').catch(()=>([])),
      ]);
      const pendingReviews = (reviewData||[]).length;
      cards.innerHTML = '';
      [
        [pendingReviews + ' Reports', 'Team Reports to Review'],
        [(myHistory||[]).length + ' Submitted', 'My Reports Submitted'],
        ['Active', 'Sprint Deliverables'],
        ['Normal', 'Team Velocity'],
      ].forEach(([v,l])=>{
        const d=document.createElement('div');
        d.className='stat-card glass-glow';
        d.innerHTML=`<b>${v}</b><span>${l}</span>`;
        cards.appendChild(d);
      });

      const chartCard = document.querySelector('.chart-card');
      if(chartCard){
        chartCard.innerHTML = `
          <div style="background:rgba(232,98,44,0.08);border:1px solid rgba(232,98,44,0.25);border-radius:12px;padding:18px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
            <div>
              <h4 style="margin:0 0 6px;color:var(--orange);font-family:var(--font-display);">🏢 Enterprise HRMS Portal</h4>
              <p style="margin:0;font-size:0.85rem;color:var(--steel-light);">Access Team Attendance, Timesheet Approvals, Leave Management, and Team Performance KPIs.</p>
            </div>
            <a href="/hrms-portal.html${gToken ? '?token=' + encodeURIComponent(gToken) : ''}" class="btn btn-primary" style="font-size:0.85rem;padding:9px 18px;white-space:nowrap;">Open HRMS Portal →</a>
          </div>
          <button type="button" class="btn btn-outline" onclick="switchTab('reports_review')" style="text-align:left;padding:14px;display:flex;align-items:center;gap:12px;width:100%;">
            <span style="font-size:1.5rem;">✅</span>
            <div><b>Review Team Daily Reports</b><br/><small style="color:var(--steel-light);">${pendingReviews} employee reports submitted for review</small></div>
          </button>
        `;
      }
    }catch(e){console.error('Work manager overview error', e);}
    return;
  }

  if(role === 'content_manager'){
    try{
      const [history, insights] = await Promise.all([
        api('/reports/my-history').catch(()=>[]),
        api('/admin/insights').catch(()=>([])),
      ]);
      const todayIso = new Date().toISOString().slice(0,10);
      const todayReport = (history||[]).find(r=>r.date===todayIso);
      cards.innerHTML = '';
      [
        [(insights||[]).length, 'Published Insights'],
        [todayReport ? '✓ Submitted' : 'Pending Today', 'Daily Work Report'],
        [(history||[]).length + ' Reports', 'Reports Submitted'],
        ['Content Hub', 'Active Focus'],
      ].forEach(([v,l])=>{
        const d=document.createElement('div');
        d.className='stat-card glass-glow';
        d.innerHTML=`<b>${v}</b><span>${l}</span>`;
        cards.appendChild(d);
      });
      const chartCard = document.querySelector('.chart-card');
      if(chartCard){
        chartCard.innerHTML = `
          <div style="background:rgba(232,98,44,0.08);border:1px solid rgba(232,98,44,0.25);border-radius:12px;padding:18px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
            <div>
              <h4 style="margin:0 0 6px;color:var(--orange);font-family:var(--font-display);">🏢 Enterprise HRMS Portal</h4>
              <p style="margin:0;font-size:0.85rem;color:var(--steel-light);">Manage your daily attendance, leave requests, monthly payslips, and timesheets.</p>
            </div>
            <a href="/hrms-portal.html${gToken ? '?token=' + encodeURIComponent(gToken) : ''}" class="btn btn-primary" style="font-size:0.85rem;padding:9px 18px;white-space:nowrap;">Open HRMS Portal →</a>
          </div>
          <div style="display:flex;gap:12px;flex-wrap:wrap;">
            <button type="button" class="btn btn-outline" onclick="switchTab('insights')" style="flex:1;min-width:200px;text-align:left;padding:14px;display:flex;align-items:center;gap:12px;">
              <span style="font-size:1.5rem;">📝</span>
              <div><b>Manage Insights</b><br/><small style="color:var(--steel-light);">Create & publish articles</small></div>
            </button>
            <button type="button" class="btn btn-outline" onclick="switchTab('daily_report')" style="flex:1;min-width:200px;text-align:left;padding:14px;display:flex;align-items:center;gap:12px;">
              <span style="font-size:1.5rem;">📓</span>
              <div><b>Submit Daily Report</b><br/><small style="color:var(--steel-light);">Log today's completed work</small></div>
            </button>
          </div>
        `;
      }
    }catch(e){console.error('Work content manager overview error', e);}
    return;
  }

  if(role === 'viewer'){
    try{
      const overviewData = await api('/admin/overview').catch(()=>({}));
      cards.innerHTML = '';
      [
        [overviewData.jobs_count ?? '0', 'Active Projects'],
        [overviewData.contacts_count ?? '0', 'Client Inquiries'],
        [overviewData.newsletter_count ?? '0', 'Newsletter Subscribers'],
        ['Read-Only', 'Viewer Access'],
      ].forEach(([v,l])=>{
        const d=document.createElement('div');
        d.className='stat-card glass-glow';
        d.innerHTML=`<b>${v}</b><span>${l}</span>`;
        cards.appendChild(d);
      });
      loadOverviewChart();
      document.querySelectorAll('a[href*="hrms-portal"], .hrms-portal-link, .hrms-portal-btn, .hrms-sidebar-btn-box').forEach(el => el.remove());
    }catch(e){console.error('Viewer overview error', e);}
    return;
  }

  // Admin / HR Manager Work Dashboard (Business & Operations Overview)
  try{
    const [overviewData, appCounts] = await Promise.all([
      api('/admin/overview').catch(()=>({})),
      api('/admin/applications').catch(()=>([])),
    ]);
    cards.innerHTML = '';
    [
      [(appCounts||[]).length, 'Total Applications'],
      [overviewData.jobs_count ?? '5', 'Active Job Requisitions'],
      [overviewData.contacts_count ?? '8', 'Client Inquiries'],
      [overviewData.newsletter_count ?? '24', 'Newsletter Subscribers'],
    ].forEach(([v,l])=>{
      const d=document.createElement('div');
      d.className='stat-card glass-glow';
      d.innerHTML=`<b>${v}</b><span>${l}</span>`;
      cards.appendChild(d);
    });

    const chartCard = document.querySelector('.chart-card');
    if(chartCard){
      const hrmsBanner = isHrmsRole(role) ? `
        <div style="background:rgba(232,98,44,0.08);border:1px solid rgba(232,98,44,0.25);border-radius:12px;padding:18px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;">
          <div>
            <h4 style="margin:0 0 6px;color:var(--orange);font-family:var(--font-display);">🏢 Enterprise HRMS Portal</h4>
            <p style="margin:0;font-size:0.85rem;color:var(--steel-light);">Access complete HR management: Employee Directory, Attendance Register, Payroll & Salaries, Leave Quotas, Onboarding/Offboarding, and Security Audit Logs.</p>
          </div>
          <a href="/hrms-portal.html${gToken ? '?token=' + encodeURIComponent(gToken) : ''}" class="btn btn-primary" style="font-size:0.85rem;padding:9px 18px;white-space:nowrap;">Open HRMS Portal →</a>
        </div>` : '';
      chartCard.innerHTML = `
        ${hrmsBanner}
        <div style="display:flex;gap:12px;flex-wrap:wrap;">
          <button type="button" class="btn btn-outline" onclick="switchTab('jobs')" style="flex:1;min-width:200px;text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.4rem;">💼</span>
            <div><b>Job Requisitions</b><br/><small style="color:var(--steel-light);">Manage open roles</small></div>
          </button>
          <button type="button" class="btn btn-outline" onclick="switchTab('applications')" style="flex:1;min-width:200px;text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.4rem;">📋</span>
            <div><b>Applications</b><br/><small style="color:var(--steel-light);">Candidate hiring pipeline</small></div>
          </button>
          <button type="button" class="btn btn-outline" onclick="switchTab('contacts')" style="flex:1;min-width:200px;text-align:left;padding:12px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:1.4rem;">✉️</span>
            <div><b>Inquiries</b><br/><small style="color:var(--steel-light);">Client messages</small></div>
          </button>
        </div>
      `;
    }
  }catch(e){
    console.error('Admin overview error', e);
  }
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
      const viewLink=document.createElement('a'); viewLink.href=filePath; viewLink.textContent='View'; viewLink.target='_blank'; viewLink.rel='noopener'; viewLink.style.cssText='color:var(--orange);font-size:.8rem;margin-inline-end:10px;';
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
  if(!rows.length){tbody.innerHTML='<tr><td colspan="7" style="color:var(--steel)">No activity logs yet.</td></tr>';return;}
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
  if(!confirm('Delete this activity log?')) return;
  try{ await api('/admin/audit-log/'+id,{method:'DELETE'}); loadActivity(); }
  catch(err){ alert(err.message); }
}
on('clearActivityBtn','click',async()=>{
  if(!confirm('Clear all activity logs? This cannot be undone.')) return;
  try{ await api('/admin/audit-log',{method:'DELETE'}); loadActivity(); }
  catch(err){ alert(err.message); }
});

/* ────── ADMIN USERS ────── */
const ADMIN_ONLY_ROLES = [
  { value: 'super_admin', label: 'Super Admin' },
  { value: 'admin',       label: 'Admin' }
];

const OTHER_STAFF_ROLES = [
  { value: 'employee',        label: 'Employee' },
  { value: 'hr_manager',      label: 'HR Manager' },
  { value: 'hr',              label: 'HR Specialist' },
  { value: 'team_lead',       label: 'Team Lead' },
  { value: 'manager',         label: 'Manager' },
  { value: 'recruiter',       label: 'Recruiter' },
  { value: 'content_manager', label: 'Content Manager' },
  { value: 'client',          label: 'Client' },
  { value: 'viewer',          label: 'Viewer' }
];

let userFormMode = null; // 'admin' | 'employee' | 'edit'

function populateUserRoles(mode, selectedValue){
  const select = $('uRole');
  if(!select) return;
  select.innerHTML = '';
  if(mode === 'admin'){
    ADMIN_ONLY_ROLES.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.value;
      opt.textContent = r.label;
      if(selectedValue ? r.value === selectedValue : r.value === 'super_admin') opt.selected = true;
      select.appendChild(opt);
    });
  } else if(mode === 'employee'){
    OTHER_STAFF_ROLES.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.value;
      opt.textContent = r.label;
      if(selectedValue ? r.value === selectedValue : r.value === 'employee') opt.selected = true;
      select.appendChild(opt);
    });
  } else {
    const adminGrp = document.createElement('optgroup');
    adminGrp.label = 'Admin Roles';
    ADMIN_ONLY_ROLES.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.value;
      opt.textContent = r.label;
      if(r.value === selectedValue) opt.selected = true;
      adminGrp.appendChild(opt);
    });
    select.appendChild(adminGrp);

    const staffGrp = document.createElement('optgroup');
    staffGrp.label = 'Employees & Other Roles';
    OTHER_STAFF_ROLES.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.value;
      opt.textContent = r.label;
      if(r.value === selectedValue) opt.selected = true;
      staffGrp.appendChild(opt);
    });
    select.appendChild(staffGrp);
    if(selectedValue) select.value = selectedValue;
  }
}

function openNewAdminModal(){
  const details = $('userDetails');
  if(details && details.open && userFormMode === 'admin'){
    resetUserForm();
    return;
  }
  resetUserForm();
  userFormMode = 'admin';
  populateUserRoles('admin');
  if($('userFormTitle')) $('userFormTitle').textContent = 'Create New Admin User';
  const badge = $('userFormTypeBadge');
  if(badge){
    badge.textContent = 'Admin Roles Only';
    badge.style.display = 'inline-flex';
    badge.style.background = 'rgba(255,107,0,.15)';
    badge.style.color = 'var(--orange)';
  }
  if($('userSubmitBtn')) $('userSubmitBtn').textContent = 'Create admin user';
  if($('userCancelBtn')) $('userCancelBtn').style.display = 'inline-flex';
  if(details){
    details.open = true;
    details.scrollIntoView({behavior:'smooth'});
  }
}
on('openNewAdminBtn', 'click', openNewAdminModal);

function openNewEmployeeModal(){
  const details = $('userDetails');
  if(details && details.open && userFormMode === 'employee'){
    resetUserForm();
    return;
  }
  resetUserForm();
  userFormMode = 'employee';
  populateUserRoles('employee');
  if($('userFormTitle')) $('userFormTitle').textContent = 'Add Employee';
  const badge = $('userFormTypeBadge');
  if(badge){
    badge.textContent = 'Employees';
    badge.style.display = 'inline-flex';
    badge.style.background = 'rgba(122,180,255,.15)';
    badge.style.color = '#7ab4ff';
  }
  if($('userSubmitBtn')) $('userSubmitBtn').textContent = 'Create employee';
  if($('userCancelBtn')) $('userCancelBtn').style.display = 'inline-flex';
  if(details){
    details.open = true;
    details.scrollIntoView({behavior:'smooth'});
  }
}
on('openNewEmployeeBtn', 'click', openNewEmployeeModal);

async function loadUsers(){
  const tbody=$('usersBody'); if(!tbody) return;
  const users=await api('/admin/users');
  tbody.innerHTML='';
  if(!users.length){tbody.innerHTML='<tr><td colspan="8" style="color:var(--steel)">No users.</td></tr>';return;}
  users.forEach(u=>{
    const tr=document.createElement('tr');
    tr.innerHTML='<td></td><td></td><td></td><td></td><td></td><td></td><td></td><td style="white-space:nowrap;"></td>';
    tr.cells[0].textContent=u.name||'—';
    tr.cells[1].textContent=u.email||'—';
    const rb=document.createElement('span'); rb.className='badge role-'+(u.role||'viewer'); rb.textContent=(u.role||'viewer').replace(/_/g,' ');
    tr.cells[2].appendChild(rb);
    const deptInfo = u.department ? (u.department + (u.designation ? ' · ' + u.designation : '')) : (u.designation || '—');
    tr.cells[3].textContent = deptInfo;
    tr.cells[4].textContent = u.phone || '—';
    const stBadge = document.createElement('span');
    stBadge.className = 'badge ' + (u.status === 'inactive' ? 'badge-inactive' : 'badge-active');
    stBadge.textContent = u.status || 'active';
    tr.cells[5].appendChild(stBadge);
    const passwordStatus=document.createElement('span'); passwordStatus.className='badge'; passwordStatus.textContent=u.passwordSet?'Protected':'Not set';
    tr.cells[6].appendChild(passwordStatus);
    const editBtn=document.createElement('button'); editBtn.className='small-btn'; editBtn.textContent='Edit';
    editBtn.addEventListener('click',()=>editUser(u));
    const delBtn=document.createElement('button'); delBtn.className='small-btn danger'; delBtn.textContent='Delete'; delBtn.style.marginLeft='4px';
    delBtn.addEventListener('click',()=>deleteUser(u.id,u.email));
    tr.cells[7].append(editBtn,delBtn);
    tbody.appendChild(tr);
  });
}
function editUser(u){
  userFormMode = 'edit';
  populateUserRoles('edit', u.role);
  $('userEditId').value=u.id;
  $('uName').value=u.name||'';
  $('uEmail').value=u.email||'';
  $('uPassword').value='';
  $('uRole').value=u.role||'viewer';
  if($('uPhone')) $('uPhone').value=u.phone||'';
  if($('uDept')) $('uDept').value=u.department||'';
  if($('uDesig')) $('uDesig').value=u.designation||'';
  if($('uJoinDate')) $('uJoinDate').value=u.joiningDate||'';
  if($('uShift')) $('uShift').value=u.shift||'morning';
  if($('uStatus')) $('uStatus').value=u.status||'active';
  if($('userFormTitle')) $('userFormTitle').textContent='Edit User: '+(u.name||u.email);
  const badge=$('userFormTypeBadge');
  if(badge){
    badge.textContent='Editing User';
    badge.style.display='inline-flex';
    badge.style.background='rgba(255,255,255,.1)';
    badge.style.color='var(--cream)';
  }
  $('userSubmitBtn').textContent='Update user';
  $('userCancelBtn').style.display='inline-flex';
  const details=$('userDetails');
  if(details){
    details.open=true;
    details.scrollIntoView({behavior:'smooth'});
  }
}
function resetUserForm(){
  const f=$('userForm'); if(!f) return;
  f.reset();
  $('userEditId').value='';
  if($('uPhone')) $('uPhone').value='';
  if($('uDept')) $('uDept').value='';
  if($('uDesig')) $('uDesig').value='';
  if($('uJoinDate')) $('uJoinDate').value='';
  if($('uShift')) $('uShift').value='morning';
  if($('uStatus')) $('uStatus').value='active';
  $('userSubmitBtn').textContent='Create user';
  $('userCancelBtn').style.display='none';
  const badge=$('userFormTypeBadge');
  if(badge) badge.style.display='none';
  if($('userFormTitle')) $('userFormTitle').textContent='Create User';
  const details=$('userDetails');
  if(details) details.open=false;
  userFormMode=null;
  const msg=$('userMsg');
  if(msg) msg.textContent='';
}
on('userCancelBtn','click',resetUserForm);
async function deleteUser(id,email){ if(!confirm('Delete user: '+email+'?')) return; try{await api('/admin/users/'+id,{method:'DELETE'});loadUsers();}catch(e){alert(e.message);}}
on('userForm','submit',async e=>{
  e.preventDefault();
  const msg=$('userMsg');
  const editId=$('userEditId').value;
  const payload={
    name:$('uName').value,
    email:$('uEmail').value,
    role:$('uRole').value,
    phone:$('uPhone')?$('uPhone').value:'',
    department:$('uDept')?$('uDept').value:'',
    designation:$('uDesig')?$('uDesig').value:'',
    joiningDate:$('uJoinDate')?$('uJoinDate').value:'',
    shift:$('uShift')?$('uShift').value:'morning',
    status:$('uStatus')?$('uStatus').value:'active'
  };
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

function fmtExactDuration(sec){
  if(sec == null || isNaN(sec)) return '—';
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const remSec = s % 60;
  return `${h}h ${m}m ${remSec}s`;
}

function fmtExactDurationFull(sec){
  if(sec == null || isNaN(sec)) return '—';
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const remSec = s % 60;
  return `${h} hrs ${m} mins ${remSec} secs`;
}

function fmtHours(sec){
  return fmtExactDuration(sec);
}

function fmtTimeIST(iso){
  if(!iso) return '—';
  try {
    const d = new Date(iso);
    if(isNaN(d.getTime())) return iso;
    return d.toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    }) + ' IST';
  } catch(e) {
    return new Date(iso).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }
}

function fmtTime(iso){
  return fmtTimeIST(iso);
}

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

let punchTimerInterval = null;

async function refreshPunchStatus(){
  if(punchTimerInterval){ clearInterval(punchTimerInterval); punchTimerInterval = null; }
  try{
    const row=await api('/attendance/today');
    const label=$('punchStatusLabel');
    const time=$('punchTimeLabel');
    const inBtn=$('checkInBtn');
    const outBtn=$('checkOutBtn');
    const msg=$('punchMsg');
    let lockedBanner=$('punchLockedBanner');
    if(!label) return;

    if(!lockedBanner && inBtn && inBtn.parentNode){
      lockedBanner=document.createElement('div');
      lockedBanner.id='punchLockedBanner';
      lockedBanner.style.cssText='display:none;padding:12px 16px;background:rgba(232,98,44,0.08);border:1px solid rgba(232,98,44,0.3);border-radius:10px;margin-top:12px;font-size:0.86rem;color:var(--steel-light);align-items:center;gap:10px;';
      inBtn.parentNode.insertBefore(lockedBanner, inBtn);
    }

    if(!row.checkIn){
      // State 1: Ready to check in for today
      if(lockedBanner) lockedBanner.style.display='none';
      label.textContent="You haven't checked in today.";
      time.textContent='Today\'s Shift: Ready (1 punch allowed per day in Indian Local Time)';
      if(inBtn){
        inBtn.style.display='inline-flex';
        inBtn.disabled=false;
        inBtn.textContent='⏱️ Check in (IST)';
      }
      if(outBtn) outBtn.style.display='none';
    } else if(!row.checkOut){
      // State 2: Checked in, on the clock
      if(lockedBanner) lockedBanner.style.display='none';
      if(inBtn) inBtn.style.display='none';
      if(outBtn){
        outBtn.style.display='inline-flex';
        outBtn.disabled=false;
        outBtn.textContent='⏹️ Check out (IST)';
      }

      const checkInDate=new Date(row.checkIn);
      const updateLiveClock=()=>{
        const now=new Date();
        const diffSec=Math.max(0, Math.floor((now.getTime() - checkInDate.getTime())/1000));
        label.textContent='Checked in at '+fmtTimeIST(row.checkIn);
        time.innerHTML=`<span style="color:var(--orange);font-weight:700;">⏱️ Active on Clock: ${fmtExactDurationFull(diffSec)}</span> <small style="color:var(--steel-light);">(Indian Local Time)</small>`;
      };
      updateLiveClock();
      punchTimerInterval=setInterval(updateLiveClock, 1000);
    } else {
      // State 3: Both check-in and check-out are done for today!
      // Once checked in and checked out, next day only it can work!
      if(inBtn) inBtn.style.display='none';
      if(outBtn) outBtn.style.display='none';

      const inStr=fmtTimeIST(row.checkIn);
      const outStr=fmtTimeIST(row.checkOut);
      const durationStr=row.workedFormattedFull || fmtExactDurationFull(row.workedSeconds);

      label.textContent='Shift Completed for Today · In: '+inStr+' · Out: '+outStr;
      time.innerHTML=`
        <div style="display:flex;flex-direction:column;gap:4px;">
          <span style="font-weight:700;color:var(--ink);">⏱️ Total Worked: ${durationStr} ${row.dayStatus?'('+row.dayStatus+')':''}</span>
          <span style="font-size:0.84rem;color:var(--steel-light);">Checked in: <b>${inStr}</b> &bull; Checked out: <b>${outStr}</b> (Indian Local Time)</span>
        </div>
      `;

      if(lockedBanner){
        lockedBanner.style.display='flex';
        lockedBanner.innerHTML=`
          <span style="font-size:1.4rem;">🔒</span>
          <div>
            <b>Daily Attendance Completed (1 Check-in / Check-out per day)</b><br/>
            <span>You have completed your check-in and check-out for today. Attendance can only be marked once per day. Next punch will be available tomorrow in Indian Local Time (IST).</span>
          </div>
        `;
      }
    }

    if(!$('reqCorrBtn') && outBtn && outBtn.parentNode){
      const b=document.createElement('button');
      b.id='reqCorrBtn';
      b.type='button';
      b.className='btn btn-outline';
      b.style.marginLeft='8px';
      b.textContent='Request Punch Correction';
      b.addEventListener('click', openCorrectionModal);
      outBtn.parentNode.appendChild(b);
    }
  } catch(e){console.error('refreshPunchStatus error', e);}
}

on('checkInBtn','click',async()=>{
  const msg=$('punchMsg');
  const btn=$('checkInBtn');
  if(btn) btn.disabled=true;
  try{
    const res=await api('/attendance/checkin',{method:'POST'});
    setFormMsg(msg,'Checked in at '+fmtTimeIST(res.checkIn)+'. Have a productive day!',true);
    refreshPunchStatus();
    loadMyCalendar();
  } catch(e){
    setFormMsg(msg,e.message,false);
    if(btn) btn.disabled=false;
  }
});

on('checkOutBtn','click',async()=>{
  const msg=$('punchMsg');
  const btn=$('checkOutBtn');
  if(btn) btn.disabled=true;
  try{
    const res=await api('/attendance/checkout',{method:'POST'});
    const duration=res.workedFormattedFull || fmtExactDurationFull(res.workedSeconds);
    setFormMsg(msg,'Checked out at '+fmtTimeIST(res.checkOut)+'. Total worked: '+duration+'. Shift completed for today!',true);
    refreshPunchStatus();
    loadMyCalendar();
  } catch(e){
    setFormMsg(msg,e.message,false);
    if(btn) btn.disabled=false;
  }
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
      const nameButton=document.createElement('button'); nameButton.type='button'; nameButton.className='small-btn'; nameButton.textContent=u.name||'—'; nameButton.addEventListener('click',()=>showEmployeeDetails(u)); tr.cells[0].appendChild(nameButton); tr.cells[1].textContent=u.email||'—';
      tr.cells[2].textContent=(u.role||'').replace(/_/g,' '); tr.cells[3].textContent=u.department||'—';
      tr.cells[4].textContent=u.status||'active'; tbody.appendChild(tr);
    });
  }catch(e){console.error(e);}
}
function showEmployeeDetails(user){
  let panel=$('employeeDetailsPanel');
  if(!panel){panel=document.createElement('section');panel.id='employeeDetailsPanel';panel.className='form-card';panel.style.cssText='margin-block-start:18px;max-inline-size:760px;';$('panel-employees')?.appendChild(panel);}
  panel.innerHTML=''; const heading=document.createElement('h3'); heading.textContent='Complete profile details'; panel.appendChild(heading);
  const grid=document.createElement('div'); grid.className='profile-detail-grid'; panel.appendChild(grid);
  [['Name',user.name],['Email',user.email],['Role',(user.role||'').replace(/_/g,' ')],['Department',user.department],['Designation',user.designation],['Phone',user.phone],['Joining date',user.joiningDate],['Shift',user.shift],['Status',user.status],['Created',user.createdAt?new Date(user.createdAt).toLocaleString():'']].forEach(([label,value])=>{const item=document.createElement('div');const key=document.createElement('b');key.textContent=label;const val=document.createElement('span');val.textContent=value||'—';item.append(key,val);grid.appendChild(item);});
  panel.scrollIntoView({behavior:'smooth',block:'nearest'});
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
    let details=$('profileDetails'); if(!details){details=document.createElement('div');details.id='profileDetails';details.className='profile-detail-grid';form.insertBefore(details,$('profileStats'));} details.innerHTML=''; [['Department',d.department],['Designation',d.designation],['Joining date',d.joiningDate],['Shift',d.shift],['Status',d.status],['Created',d.createdAt?new Date(d.createdAt).toLocaleString():'']].forEach(([label,value])=>{const item=document.createElement('div');item.innerHTML='<b></b><span></span>';item.firstChild.textContent=label;item.lastChild.textContent=value||'—';details.appendChild(item);});
    const cards=$('profileStats'); cards.innerHTML=''; [[d.totalReports||0,'Total reports'],[d.reportsThisMonth||0,'This month']].forEach(([v,l])=>{const c=document.createElement('div');c.className='stat-card glass-glow';c.innerHTML='<b></b><span></span>';c.firstChild.textContent=v;c.lastChild.textContent=l;cards.appendChild(c);});
  }catch(e){setFormMsg($('profileMsg'),e.message,false);}
}
on('profileForm','submit',async e=>{
  e.preventDefault(); const payload={name:$('profileName').value,phone:$('profilePhone').value}; if($('profilePassword').value) payload.password=$('profilePassword').value;
  try{await api('/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$('profilePassword').value='';setFormMsg($('profileMsg'),'Profile saved.',true);}catch(err){setFormMsg($('profileMsg'),err.message,false);}
});

/* ═══════════════════════════════════════════════════════════════════════════
 * HRMS ENTERPRISE MODULE LOADERS (KYK TECHNOLOGIES)
 * ═══════════════════════════════════════════════════════════════════════════ */

/* ── Topbar Clock & Notifications ── */
function startTopbarClock(){
  const clock = $('topbarClock');
  if(!clock) return;
  const update = () => {
    const now = new Date();
    clock.textContent = now.toLocaleDateString('en-IN', { weekday:'short', day:'numeric', month:'short' }) + ' ' + now.toLocaleTimeString('en-IN');
  };
  update();
  setInterval(update, 1000);
}

async function loadNotifications(){
  const badge = $('topbarNotifBadge');
  const list = $('topbarNotifItems');
  if(!badge || !list) return;
  try{
    const notifs = await api('/notifications');
    const unread = notifs.filter(n=>!n.read).length;
    if(unread > 0){
      badge.textContent = unread;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
    list.innerHTML = '';
    if(!notifs.length){
      list.innerHTML = '<div style="color:var(--steel);font-size:0.8rem;text-align:center;padding:12px 0;">No notifications yet.</div>';
      return;
    }
    notifs.forEach(n=>{
      const item = document.createElement('div');
      item.className = 'notif-item' + (!n.read ? ' unread' : '');
      item.innerHTML = `
        <b style="display:block;font-size:0.82rem;color:var(--ink);">${esc(n.title)}</b>
        <span style="display:block;font-size:0.75rem;color:var(--steel-light);margin-top:2px;">${esc(n.message)}</span>
        <time style="display:block;font-size:0.68rem;color:var(--steel);margin-top:4px;">${n.createdAt ? new Date(n.createdAt).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : ''}</time>
      `;
      list.appendChild(item);
    });
  }catch(e){
    console.error('Notifs error', e);
  }
}

/* ── Module 1 & 12: Departments, Designations & Shifts ── */
async function loadDepartments(){
  try{
    const [depts, desigs, shifts] = await Promise.all([
      api('/org/departments'),
      api('/org/designations'),
      api('/org/shifts')
    ]);

    const dBody = $('deptsBody');
    if(dBody){
      dBody.innerHTML = '';
      if(!depts.length) dBody.innerHTML = '<tr><td colspan="4">No departments found.</td></tr>';
      depts.forEach(d=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${esc(d.code||'—')}</b></td><td>${esc(d.name)}</td><td>${esc(d.branch||'Warangal HQ')}</td><td><span class="badge badge-active">Active</span></td>`;
        dBody.appendChild(tr);
      });
    }

    const gBody = $('desigsBody');
    if(gBody){
      gBody.innerHTML = '';
      if(!desigs.length) gBody.innerHTML = '<tr><td colspan="3">No designations found.</td></tr>';
      desigs.forEach(d=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${esc(d.title)}</b></td><td>${esc(d.department||'General')}</td><td><span class="badge badge-active">Active</span></td>`;
        gBody.appendChild(tr);
      });
    }

    const sBody = $('shiftsBody');
    if(sBody){
      sBody.innerHTML = '';
      if(!shifts.length) sBody.innerHTML = '<tr><td colspan="5">No work shifts configured.</td></tr>';
      shifts.forEach(s=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><b>${esc(s.name)}</b></td><td>${esc(s.startTime)} – ${esc(s.endTime)}</td><td>${s.gracePeriodMins||15} mins</td><td>${s.halfDayHours||4} hrs</td><td><span class="badge badge-active">Active</span></td>`;
        sBody.appendChild(tr);
      });
    }

    on('addDeptBtn', 'click', () => {
      openHrmsModal('Add Department', `
        <form id="addDeptForm" style="display:flex;flex-direction:column;gap:12px;">
          <div class="field"><label>Department Name *</label><input id="depName" required/></div>
          <div class="field"><label>Code *</label><input id="depCode" placeholder="e.g. SWS" required/></div>
          <div class="field"><label>Branch</label><input id="depBranch" value="Warangal Headquarters"/></div>
          <button type="submit" class="btn btn-primary">Save Department</button>
          <div class="form-msg" id="depMsg"></div>
        </form>
      `);
      $('addDeptForm').addEventListener('submit', async(e)=>{
        e.preventDefault();
        try{
          await api('/org/departments', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({name:$('depName').value, code:$('depCode').value, branch:$('depBranch').value})
          });
          closeHrmsModal(); loadDepartments();
        }catch(err){ setFormMsg($('depMsg'), err.message, false); }
      });
    });

    on('addDesigBtn', 'click', () => {
      openHrmsModal('Add Designation', `
        <form id="addDesigForm" style="display:flex;flex-direction:column;gap:12px;">
          <div class="field"><label>Designation Title *</label><input id="desTitle" required/></div>
          <div class="field"><label>Department *</label><input id="desDept" value="Software & Web Services" required/></div>
          <button type="submit" class="btn btn-primary">Save Designation</button>
          <div class="form-msg" id="desMsg"></div>
        </form>
      `);
      $('addDesigForm').addEventListener('submit', async(e)=>{
        e.preventDefault();
        try{
          await api('/org/designations', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({title:$('desTitle').value, department:$('desDept').value})
          });
          closeHrmsModal(); loadDepartments();
        }catch(err){ setFormMsg($('desMsg'), err.message, false); }
      });
    });

    on('addShiftBtn', 'click', () => {
      openHrmsModal('Add Work Shift', `
        <form id="addShiftForm" style="display:flex;flex-direction:column;gap:12px;">
          <div class="field"><label>Shift Name *</label><input id="shName" placeholder="e.g. Night Shift" required/></div>
          <div class="field"><label>Start Time *</label><input type="time" id="shStart" value="09:30" required/></div>
          <div class="field"><label>End Time *</label><input type="time" id="shEnd" value="18:30" required/></div>
          <div class="field"><label>Grace Period (minutes)</label><input type="number" id="shGrace" value="15"/></div>
          <button type="submit" class="btn btn-primary">Save Shift</button>
          <div class="form-msg" id="shMsg"></div>
        </form>
      `);
      $('addShiftForm').addEventListener('submit', async(e)=>{
        e.preventDefault();
        try{
          await api('/org/shifts', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
              name:$('shName').value, startTime:$('shStart').value,
              endTime:$('shEnd').value, gracePeriodMins:Number($('shGrace').value)
            })
          });
          closeHrmsModal(); loadDepartments();
        }catch(err){ setFormMsg($('shMsg'), err.message, false); }
      });
    });
  }catch(e){console.error(e);}
}

/* ── Module 1 & 12: Branches ── */
async function loadBranches(){
  try{
    const [companies, branches] = await Promise.all([
      api('/org/companies'),
      api('/org/branches')
    ]);

    const compCard = $('companyOverviewCard');
    if(compCard && companies.length){
      const c = companies[0];
      compCard.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <div>
            <h3 style="margin:0 0 6px;">${esc(c.name)}</h3>
            <p style="color:var(--steel);margin:0;font-size:0.85rem;">Registration: <b>${esc(c.registrationNo||'CIN: U72200TG2022PTC160000')}</b> | GSTIN / Tax ID: <b>${esc(c.taxId||'AAACK9999K')}</b></p>
            <p style="color:var(--steel-light);margin:4px 0 0;font-size:0.8rem;">Email: ${esc(c.email)} &bull; Phone: ${esc(c.phone)} &bull; Timezone: ${esc(c.timezone||'Asia/Kolkata')}</p>
          </div>
          <span class="badge badge-published">Active Entity</span>
        </div>
      `;
    }

    const bBody = $('branchesBody');
    if(bBody){
      bBody.innerHTML = '';
      branches.forEach(b=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${esc(b.code)}</b></td>
          <td>${esc(b.name)}</td>
          <td>${esc(b.city||'Warangal')}, ${esc(b.state||'Telangana')}</td>
          <td>${esc(b.country||'India')}</td>
          <td>${esc(b.phone||'—')}</td>
          <td>${esc(b.taxId||'36AAACK9999K1Z5')}</td>
          <td><span class="badge badge-active">Operational</span></td>
        `;
        bBody.appendChild(tr);
      });
    }

    on('addBranchBtn', 'click', () => {
      openHrmsModal('Add Branch Location', `
        <form id="addBranchForm" style="display:flex;flex-direction:column;gap:12px;">
          <div class="field"><label>Branch Name *</label><input id="brName" required/></div>
          <div class="field"><label>Branch Code *</label><input id="brCode" placeholder="e.g. KYK-HYD" required/></div>
          <div class="field"><label>City *</label><input id="brCity" required/></div>
          <div class="field"><label>State *</label><input id="brState" value="Telangana" required/></div>
          <div class="field"><label>Phone</label><input id="brPhone"/></div>
          <button type="submit" class="btn btn-primary">Create Branch</button>
          <div class="form-msg" id="brMsg"></div>
        </form>
      `);
      $('addBranchForm').addEventListener('submit', async(e)=>{
        e.preventDefault();
        try{
          await api('/org/branches', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
              name:$('brName').value, code:$('brCode').value,
              city:$('brCity').value, state:$('brState').value, phone:$('brPhone').value
            })
          });
          closeHrmsModal(); loadBranches();
        }catch(err){ setFormMsg($('brMsg'), err.message, false); }
      });
    });
  }catch(e){console.error(e);}
}

/* ── Module 4: Leave Management ── */
async function loadLeaveMgmt(){
  try{
    const [requests, types] = await Promise.all([
      api('/admin/leave'),
      api('/leave/types')
    ]);

    const stats = $('leaveMgmtStats');
    if(stats){
      const pending = requests.filter(r=>r.status==='pending').length;
      const approved = requests.filter(r=>r.status==='approved').length;
      stats.innerHTML = '';
      [
        [pending, 'Pending Approval'],
        [approved, 'Approved Leaves'],
        [requests.length, 'Total Leave Applications'],
        [types.length, 'Configured Leave Types']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const tbody = $('leaveMgmtBody');
    if(tbody){
      const filter = $('leaveStatusFilter')?.value || '';
      const filtered = filter ? requests.filter(r=>r.status===filter) : requests;
      tbody.innerHTML = '';
      if(!filtered.length){ tbody.innerHTML = '<tr><td colspan="7">No leave requests found.</td></tr>'; }
      filtered.forEach(r=>{
        const tr = document.createElement('tr');
        const badgeClass = r.status==='approved'?'badge-approved':(r.status==='rejected'?'badge-rejected':'badge-pending');
        let actions = '—';
        if(r.status==='pending'){
          actions = `
            <button class="btn btn-success btn-sm" onclick="decideLeave(${r.id}, 'approved')">Approve</button>
            <button class="btn btn-danger btn-sm" style="margin-left:4px;" onclick="decideLeave(${r.id}, 'rejected')">Reject</button>
          `;
        }
        tr.innerHTML = `
          <td><b>${esc(r.adminName||r.employeeName||'Staff')}</b><br/><small style="color:var(--steel);">${esc(r.adminEmail||'')}</small></td>
          <td>${esc(r.type||r.leaveType||'Casual Leave')}</td>
          <td>${esc(r.fromDate)} &rarr; ${esc(r.toDate)}</td>
          <td>${esc(r.totalDays||1)} d</td>
          <td>${esc(r.reason||'—')}</td>
          <td><span class="badge ${badgeClass}">${esc(r.status||'pending')}</span></td>
          <td style="white-space:nowrap;">${actions}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    const tBody = $('leaveTypesBody');
    if(tBody){
      tBody.innerHTML = '';
      types.forEach(t=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${esc(t.name)}</b></td>
          <td><code>${esc(t.code)}</code></td>
          <td>${t.quotaPerYear||12} days / year</td>
          <td>Max ${t.carryForwardMax||5} days</td>
          <td>${t.paid!==false?'Yes (Paid)':'Unpaid'}</td>
        `;
        tBody.appendChild(tr);
      });
    }
  }catch(e){console.error(e);}
}

async function decideLeave(id, decision){
  try{
    await api('/admin/leave/'+id+'/decision', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({decision})
    });
    loadLeaveMgmt();
  }catch(e){ alert(e.message); }
}

on('leaveStatusFilter', 'change', loadLeaveMgmt);
on('refreshLeaveMgmt', 'click', loadLeaveMgmt);

/* ── Module 4: My Leaves ── */
async function loadMyLeaves(){
  try{
    const [balData, myLeaves, types] = await Promise.all([
      api('/leave/balances'),
      api('/leave/my'),
      api('/leave/types')
    ]);

    const balGrid = $('myLeaveBalances');
    if(balGrid){
      balGrid.innerHTML = '';
      const b = balData.balances || {};
      Object.entries(b).forEach(([name, val])=>{
        const card = document.createElement('div');
        card.className = 'leave-balance-card glass-glow';
        card.innerHTML = `
          <span>${esc(name)}</span>
          <b>${val.available ?? val.quota ?? 12}</b>
          <small>${val.used||0} used / ${val.quota||12} total</small>
        `;
        balGrid.appendChild(card);
      });
    }

    const tbody = $('myLeavesBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!myLeaves.length){ tbody.innerHTML = '<tr><td colspan="7">No leave applications filed yet.</td></tr>'; }
      myLeaves.forEach(r=>{
        const tr = document.createElement('tr');
        const badgeClass = r.status==='approved'?'badge-approved':(r.status==='rejected'?'badge-rejected':'badge-pending');
        let cancelBtn = '—';
        if(r.status === 'pending'){
          cancelBtn = `<button class="btn btn-danger btn-sm" onclick="cancelMyLeave(${r.id})">Cancel</button>`;
        }
        tr.innerHTML = `
          <td><b>${esc(r.type||r.leaveType||'Casual Leave')}</b></td>
          <td>${esc(r.fromDate)} &rarr; ${esc(r.toDate)}</td>
          <td>${esc(r.totalDays||1)} d</td>
          <td>${esc(r.reason||'—')}</td>
          <td><span class="badge ${badgeClass}">${esc(r.status)}</span></td>
          <td>${r.createdAt ? new Date(r.createdAt).toLocaleDateString() : '—'}</td>
          <td>${cancelBtn}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    on('applyLeaveBtn', 'click', () => {
      openApplyLeaveModal(types);
    });
  }catch(e){console.error(e);}
}

function openApplyLeaveModal(types){
  const opts = (types||[]).map(t=>`<option value="${esc(t.name)}">${esc(t.name)} (Quota: ${t.quotaPerYear} d/yr)</option>`).join('') || `
    <option value="Casual Leave">Casual Leave</option>
    <option value="Sick Leave">Sick Leave</option>
    <option value="Paid / Annual Leave">Paid / Annual Leave</option>
    <option value="Work From Home">Work From Home</option>
  `;
  openHrmsModal('Apply for Leave', `
    <form id="applyLeaveForm" style="display:flex;flex-direction:column;gap:12px;">
      <div class="field"><label>Leave Type *</label><select id="alType">${opts}</select></div>
      <div class="field"><label>From Date *</label><input type="date" id="alFrom" value="${new Date().toISOString().slice(0,10)}" required/></div>
      <div class="field"><label>To Date *</label><input type="date" id="alTo" value="${new Date().toISOString().slice(0,10)}" required/></div>
      <div class="field"><label>Reason / Handover Note *</label><textarea id="alReason" rows="3" placeholder="Provide reason and who will cover your urgent responsibilities" required></textarea></div>
      <button type="submit" class="btn btn-primary">Submit Leave Application</button>
      <div class="form-msg" id="alMsg"></div>
    </form>
  `);
  $('applyLeaveForm').addEventListener('submit', async(e)=>{
    e.preventDefault();
    try{
      await api('/leave/apply', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          type:$('alType').value,
          fromDate:$('alFrom').value,
          toDate:$('alTo').value,
          reason:$('alReason').value.trim()
        })
      });
      setFormMsg($('alMsg'), 'Leave application submitted.', true);
      setTimeout(()=>{ closeHrmsModal(); loadMyLeaves(); }, 1200);
    }catch(err){ setFormMsg($('alMsg'), err.message, false); }
  });
}

async function cancelMyLeave(id){
  if(!confirm('Cancel this leave request?')) return;
  try{
    await api('/leave/cancel/'+id, {method:'POST'});
    loadMyLeaves();
  }catch(e){ alert(e.message); }
}

/* ── Module 5: Payroll & Payslips ── */
async function loadPayroll(){
  try{
    const [runs, structures] = await Promise.all([
      api('/payroll/runs'),
      api('/payroll/salary-structures')
    ]);

    const stats = $('payrollStats');
    if(stats && runs.length){
      const latest = runs[0];
      stats.innerHTML = '';
      [
        [`₹${Number(latest.totalNet||0).toLocaleString()}`, `Latest Net Payout (${latest.monthYear})`],
        [`₹${Number(latest.totalGross||0).toLocaleString()}`, `Latest Gross Cost`],
        [latest.employeeCount||0, 'Employees Paid'],
        [latest.status.toUpperCase(), 'Run Status']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const rBody = $('payrollRunsBody');
    if(rBody){
      rBody.innerHTML = '';
      if(!runs.length){ rBody.innerHTML = '<tr><td colspan="7">No payroll runs found.</td></tr>'; }
      runs.forEach(r=>{
        const tr = document.createElement('tr');
        const badgeClass = r.status==='published'?'badge-published':(r.status==='approved'?'badge-approved':'badge-pending');
        let actions = '';
        if(r.status === 'calculated' || r.status === 'draft'){
          actions = `<button class="btn btn-success btn-sm" onclick="approvePayrollRun(${r.id})">Approve</button>`;
        } else if(r.status === 'approved'){
          actions = `<button class="btn btn-primary btn-sm" onclick="publishPayrollRun(${r.id})">Publish Payslips</button>`;
        } else {
          actions = `<span style="color:#38d273;font-size:0.8rem;font-weight:600;">✓ Live to Employees</span>`;
        }
        tr.innerHTML = `
          <td><b>${esc(r.monthYear)}</b></td>
          <td>${r.employeeCount} staff</td>
          <td>₹${Number(r.totalGross||0).toLocaleString()}</td>
          <td>₹${Number(r.totalDeductions||0).toLocaleString()}</td>
          <td><b>₹${Number(r.totalNet||0).toLocaleString()}</b></td>
          <td><span class="badge ${badgeClass}">${esc(r.status)}</span></td>
          <td>${actions}</td>
        `;
        rBody.appendChild(tr);
      });
    }

    const sBody = $('salaryStructuresBody');
    if(sBody){
      sBody.innerHTML = '';
      structures.forEach(s=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${esc(s.employeeName||'Staff')}</b></td>
          <td>₹${Number(s.ctc||(s.grossSalary*12)||0).toLocaleString()}</td>
          <td>₹${Number(s.basicSalary||0).toLocaleString()}</td>
          <td>₹${Number(s.hra||0).toLocaleString()}</td>
          <td>₹${Number((s.specialAllowance||0)+(s.conveyance||0)).toLocaleString()}</td>
          <td>₹${Number(s.pfDeduction||0).toLocaleString()}</td>
          <td>₹${Number(s.taxDeduction||0).toLocaleString()}</td>
          <td><b>₹${Number(s.netSalary||0).toLocaleString()}</b></td>
        `;
        sBody.appendChild(tr);
      });
    }

    on('generatePayrollBtn', 'click', () => {
      const now = new Date();
      const defMonth = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
      openHrmsModal('Run Monthly Payroll', `
        <form id="payrollRunForm" style="display:flex;flex-direction:column;gap:12px;">
          <div class="field"><label>Pay Period (YYYY-MM) *</label><input type="month" id="prMonthYear" value="${defMonth}" required/></div>
          <p style="font-size:0.85rem;color:var(--steel-light);">This computes CTC, Basic, HRA, Allowances, PF, and Tax deductions for all active employees across KYK Technologies branches.</p>
          <button type="submit" class="btn btn-primary">Process &amp; Calculate Run</button>
          <div class="form-msg" id="prMsg"></div>
        </form>
      `);
      $('payrollRunForm').addEventListener('submit', async(e)=>{
        e.preventDefault();
        try{
          await api('/payroll/runs', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({monthYear:$('prMonthYear').value})
          });
          setFormMsg($('prMsg'), 'Payroll calculated successfully.', true);
          setTimeout(()=>{ closeHrmsModal(); loadPayroll(); }, 1200);
        }catch(err){ setFormMsg($('prMsg'), err.message, false); }
      });
    });
  }catch(e){console.error(e);}
}

async function approvePayrollRun(id){
  try{
    await api('/payroll/runs/'+id+'/approve', {method:'POST'});
    loadPayroll();
  }catch(e){ alert(e.message); }
}

async function publishPayrollRun(id){
  if(!confirm('Publish payslips to employees? They will be notified immediately.')) return;
  try{
    await api('/payroll/runs/'+id+'/publish', {method:'POST'});
    loadPayroll();
  }catch(e){ alert(e.message); }
}

/* ── Module 5: My Payslips ── */
async function loadMyPayslips(){
  try{
    const slips = await api('/payslips/my');
    const tbody = $('myPayslipsBody');
    if(!tbody) return;
    tbody.innerHTML = '';
    if(!slips.length){ tbody.innerHTML = '<tr><td colspan="7">No payslips published yet.</td></tr>'; return; }
    slips.forEach(s=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${esc(s.monthYear)}</b></td>
        <td>₹${Number(s.basic||0).toLocaleString()}</td>
        <td>₹${Number((s.hra||0)+(s.allowances||0)).toLocaleString()}</td>
        <td>₹${Number(s.deductions||(s.pf+s.tax)||0).toLocaleString()}</td>
        <td><b style="color:var(--orange);">₹${Number(s.netPay||0).toLocaleString()}</b></td>
        <td><span class="badge badge-published">Published</span></td>
        <td><button class="btn btn-outline btn-sm" onclick="viewPayslipModal(${s.id})">View / Print Slip</button></td>
      `;
      tbody.appendChild(tr);
    });
  }catch(e){console.error(e);}
}

async function viewPayslipModal(slipId){
  try{
    const d = await api('/payslips/'+slipId);
    const slip = d.payslip;
    const comp = d.company || {};
    const html = `
      <div class="payslip-sheet">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #e2e8f0;padding-bottom:16px;margin-bottom:16px;">
          <div>
            <h2>${esc(comp.name || 'KYK Technologies Pvt Ltd')}</h2>
            <p>${esc(comp.registrationNo || 'CIN: U72200TG2022PTC160000')} | Tax ID: ${esc(comp.taxId || 'AAACK9999K')}</p>
            <p style="font-size:0.75rem;color:#64748b;">${esc(comp.website || 'https://kyktechnologies.com')} &bull; ${esc(comp.phone || '+91 870 245 0000')}</p>
          </div>
          <div style="text-align:right;">
            <span class="badge badge-published" style="font-size:0.85rem;padding:4px 10px;">SALARY SLIP</span>
            <div style="font-weight:700;margin-top:6px;font-size:1.1rem;color:#0f172a;">${esc(slip.monthYear)}</div>
          </div>
        </div>
        <div class="payslip-meta-grid">
          <div><b>Employee Name:</b> ${esc(slip.employeeName)}</div>
          <div><b>Employee Code:</b> ${esc(slip.employeeCode || 'KYK-001')}</div>
          <div><b>Department:</b> ${esc(slip.department || 'Engineering')}</div>
          <div><b>Designation:</b> ${esc(slip.designation || 'Staff')}</div>
          <div><b>Email:</b> ${esc(slip.employeeEmail || '')}</div>
          <div><b>Pay Status:</b> ${esc(slip.status || 'Published').toUpperCase()}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
          <div>
            <h4 style="margin:0 0 8px;color:#0f172a;font-size:0.9rem;border-bottom:1px solid #cbd5e1;padding-bottom:4px;">EARNINGS (INR)</h4>
            <table style="width:100%;font-size:0.85rem;">
              <tr><td>Basic Salary</td><td style="text-align:right;font-weight:600;">₹${Number(slip.basic || 0).toLocaleString()}</td></tr>
              <tr><td>House Rent Allowance (HRA)</td><td style="text-align:right;font-weight:600;">₹${Number(slip.hra || 0).toLocaleString()}</td></tr>
              <tr><td>Special / Travel Allowance</td><td style="text-align:right;font-weight:600;">₹${Number(slip.allowances || 0).toLocaleString()}</td></tr>
              ${slip.bonus ? `<tr><td>Performance Bonus</td><td style="text-align:right;font-weight:600;">₹${Number(slip.bonus).toLocaleString()}</td></tr>` : ''}
              <tr style="border-top:1.5px solid #cbd5e1;font-weight:700;"><td>Total Gross Earnings</td><td style="text-align:right;color:#0f172a;">₹${Number(slip.grossEarnings || (slip.basic + slip.hra + slip.allowances)).toLocaleString()}</td></tr>
            </table>
          </div>
          <div>
            <h4 style="margin:0 0 8px;color:#0f172a;font-size:0.9rem;border-bottom:1px solid #cbd5e1;padding-bottom:4px;">DEDUCTIONS (INR)</h4>
            <table style="width:100%;font-size:0.85rem;">
              <tr><td>Provident Fund (PF)</td><td style="text-align:right;font-weight:600;">₹${Number(slip.pf || 0).toLocaleString()}</td></tr>
              <tr><td>Income Tax / TDS</td><td style="text-align:right;font-weight:600;">₹${Number(slip.tax || 0).toLocaleString()}</td></tr>
              <tr><td>Professional Tax</td><td style="text-align:right;font-weight:600;">₹200</td></tr>
              <tr style="border-top:1.5px solid #cbd5e1;font-weight:700;"><td>Total Deductions</td><td style="text-align:right;color:#e11d48;">₹${Number((slip.deductions || (slip.pf + slip.tax)) + 200).toLocaleString()}</td></tr>
            </table>
          </div>
        </div>
        <div class="payslip-net">
          <div>
            <span style="font-size:0.8rem;text-transform:uppercase;color:#475569;letter-spacing:0.04em;">Net Take-Home Salary</span>
            <div style="font-size:0.75rem;color:#64748b;">Direct Bank Transfer &bull; Confidential</div>
          </div>
          <b>₹${Number(slip.netPay || 0).toLocaleString()}</b>
        </div>
        <div style="margin-top:24px;display:flex;justify-content:flex-end;gap:12px;">
          <button class="btn btn-outline print-btn" onclick="window.print()">🖨️ Print / Download PDF</button>
          <button class="btn btn-primary print-btn" onclick="closeHrmsModal()">Close</button>
        </div>
      </div>
    `;
    openHrmsModal('Salary Payslip', html, true);
  }catch(e){ alert(e.message); }
}

/* ── Module 3: Timesheets (Manager / Approvals) ── */
async function loadTimesheets(){
  try{
    const rows = await api('/manager/timesheets');
    const stats = $('timesheetStats');
    if(stats){
      const pending = rows.filter(r=>r.status==='submitted').length;
      const approved = rows.filter(r=>r.status==='approved').length;
      stats.innerHTML = '';
      [
        [pending, 'Pending Timesheets'],
        [approved, 'Approved Weeks'],
        [rows.length, 'Total Timesheets Filed']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const tbody = $('timesheetsBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!rows.length){ tbody.innerHTML = '<tr><td colspan="6">No timesheet submissions found.</td></tr>'; }
      rows.forEach(t=>{
        const tr = document.createElement('tr');
        const badgeClass = t.status==='approved'?'badge-approved':(t.status==='rejected'?'badge-rejected':'badge-pending');
        let actions = '—';
        if(t.status === 'submitted'){
          actions = `
            <button class="btn btn-success btn-sm" onclick="decideTimesheet(${t.id}, 'approved')">Approve</button>
            <button class="btn btn-danger btn-sm" style="margin-left:4px;" onclick="decideTimesheet(${t.id}, 'rejected')">Reject</button>
          `;
        }
        tr.innerHTML = `
          <td><b>${esc(t.employeeName||'Staff')}</b><br/><small style="color:var(--steel);">${esc(t.employeeEmail||'')}</small></td>
          <td>${esc(t.weekStartDate)}</td>
          <td>${esc(t.projectName)}</td>
          <td><b>${t.totalHours} hrs</b></td>
          <td><span class="badge ${badgeClass}">${esc(t.status)}</span></td>
          <td>${actions}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    on('refreshTimesheetsBtn', 'click', loadTimesheets);
  }catch(e){console.error(e);}
}

async function decideTimesheet(id, decision){
  try{
    await api('/manager/timesheets/'+id+'/decide', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({decision})
    });
    loadTimesheets();
  }catch(e){ alert(e.message); }
}

/* ── Module 3: My Timesheets ── */
async function loadMyTimesheets(){
  try{
    const rows = await api('/timesheets/my');
    const tbody = $('myTimesheetsBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!rows.length){ tbody.innerHTML = '<tr><td colspan="6">No timesheets submitted yet.</td></tr>'; }
      rows.forEach(t=>{
        const tr = document.createElement('tr');
        const badgeClass = t.status==='approved'?'badge-approved':(t.status==='rejected'?'badge-rejected':'badge-pending');
        tr.innerHTML = `
          <td><b>${esc(t.weekStartDate)}</b></td>
          <td>${esc(t.projectName)}</td>
          <td>${t.totalHours} hrs</td>
          <td><span class="badge ${badgeClass}">${esc(t.status)}</span></td>
          <td>${t.submittedAt ? new Date(t.submittedAt).toLocaleDateString() : '—'}</td>
          <td>${esc(t.comments||'—')}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    const startInput = $('tsWeekStart');
    if(startInput && !startInput.value){
      const d = new Date();
      d.setDate(d.getDate() - (d.getDay() === 0 ? 6 : d.getDay() - 1)); // Mon
      startInput.value = d.toISOString().slice(0,10);
    }

    const form = $('timesheetSubmitForm');
    if(form && !form.dataset.bound){
      form.dataset.bound = '1';
      form.addEventListener('submit', async(e)=>{
        e.preventDefault();
        const msg = $('tsMsg');
        const hours = {
          mon: Number($('tsMon').value||0),
          tue: Number($('tsTue').value||0),
          wed: Number($('tsWed').value||0),
          thu: Number($('tsThu').value||0),
          fri: Number($('tsFri').value||0)
        };
        const total = Object.values(hours).reduce((a,b)=>a+b, 0);
        try{
          await api('/timesheets/submit', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
              weekStartDate:$('tsWeekStart').value,
              projectName:$('tsProject').value,
              hoursBreakdown:hours,
              totalHours:total,
              notes:$('tsTasks').value
            })
          });
          setFormMsg(msg, `Timesheet for week (${total}h) submitted for manager review.`, true);
          loadMyTimesheets();
        }catch(err){ setFormMsg(msg, err.message, false); }
      });
    }
  }catch(e){console.error(e);}
}

/* ── Module 6: Recruitment & ATS ── */
async function loadRecruitment(){
  try{
    const [jobs, apps] = await Promise.all([
      api('/admin/jobs'),
      api('/admin/applications')
    ]);

    const stats = $('recruitmentStats');
    if(stats){
      stats.innerHTML = '';
      [
        [jobs.filter(j=>j.active).length, 'Active Job Openings'],
        [apps.length, 'Total Applicants'],
        [apps.filter(a=>a.status==='interview').length, 'Interview Stage'],
        [apps.filter(a=>a.status==='hired').length, 'Hired Candidates']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const tbody = $('recruitmentAppsBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!apps.length){ tbody.innerHTML = '<tr><td colspan="5">No candidates found.</td></tr>'; }
      apps.forEach(a=>{
        const tr = document.createElement('tr');
        const resume = a.resumeFile ? `<a href="/api/admin/files/${encodeURIComponent(a.resumeFile)}?token=${encodeURIComponent(gToken)}" target="_blank" style="color:var(--orange);">View Resume</a>` : '—';
        let actions = ``;
        if(a.status !== 'hired'){
          actions = `<button class="btn btn-primary btn-sm" onclick="openConvertToEmployeeModal(${JSON.stringify(a).replace(/"/g,'&quot;')})">Convert to Employee &rarr;</button>`;
        } else {
          actions = `<span class="badge badge-hired">Employee Created</span>`;
        }
        tr.innerHTML = `
          <td><b>${esc(a.name)}</b><br/><small style="color:var(--steel);">${esc(a.email||'')}</small></td>
          <td>${esc(a.jobTitle||'—')}</td>
          <td><span class="badge badge-${a.status||'new'}">${esc(a.status||'new')}</span></td>
          <td>${resume}</td>
          <td>${actions}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    on('recruitmentRefresh', 'click', loadRecruitment);
  }catch(e){console.error(e);}
}

function openConvertToEmployeeModal(cand){
  openHrmsModal('Convert Candidate to Employee', `
    <form id="convertEmpForm" style="display:flex;flex-direction:column;gap:12px;">
      <div class="field"><label>Candidate Name</label><input id="convName" value="${esc(cand.name)}" required/></div>
      <div class="field"><label>Corporate Email</label><input id="convEmail" value="${esc(cand.email||'')}" required/></div>
      <div class="field"><label>Department</label>
        <select id="convDept">
          <option>Software & Web Services</option>
          <option>AI, AGI, ASI Applications</option>
          <option>Global Recruitment</option>
          <option>Operations & Support</option>
        </select>
      </div>
      <div class="field"><label>Designation</label><input id="convDesig" value="${esc(cand.jobTitle||'Software Engineer')}" required/></div>
      <div class="field"><label>Monthly Basic Salary (₹)</label><input type="number" id="convSalary" value="55000" min="20000" required/></div>
      <div class="field"><label>Joining Date</label><input type="date" id="convJoinDate" value="${new Date().toISOString().slice(0,10)}" required/></div>
      <div class="field"><label>Temporary Password</label><input id="convPass" value="Welcome@12345" required/></div>
      <button type="submit" class="btn btn-primary" style="margin-top:10px;">Confirm &amp; Generate Credentials</button>
      <div class="form-msg" id="convMsg"></div>
    </form>
  `);
  $('convertEmpForm').addEventListener('submit', async(e)=>{
    e.preventDefault();
    const msg = $('convMsg');
    try{
      const res = await api('/recruitment/candidates/'+cand.id+'/convert-to-employee', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          department:$('convDept').value,
          designation:$('convDesig').value,
          basicSalary:Number($('convSalary').value),
          joiningDate:$('convJoinDate').value,
          password:$('convPass').value
        })
      });
      setFormMsg(msg, res.message + ' Temporary Password: ' + res.tempPassword, true);
      setTimeout(()=>{ closeHrmsModal(); loadRecruitment(); }, 2000);
    }catch(err){ setFormMsg(msg, err.message, false); }
  });
}

/* ── Module 6: Onboarding ── */
async function loadOnboarding(){
  try{
    const tasks = await api('/onboarding/tasks');
    const container = $('onboardingList');
    if(!container) return;
    container.innerHTML = '';
    if(!tasks.length){ container.innerHTML = '<div style="color:var(--steel);">No onboarding tasks active.</div>'; return; }

    const grouped = {};
    tasks.forEach(t=>{
      const emp = t.employeeName || 'Staff';
      if(!grouped[emp]) grouped[emp] = [];
      grouped[emp].push(t);
    });

    Object.entries(grouped).forEach(([empName, list])=>{
      const card = document.createElement('div');
      card.className = 'form-card';
      card.style.marginBottom = '20px';
      const completed = list.filter(t=>t.status==='completed').length;
      const pct = Math.round((completed / list.length) * 100);

      let taskRows = list.map(t=>`
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
          <div>
            <span style="font-size:0.88rem;${t.status==='completed'?'text-decoration:line-through;color:var(--steel);':''}">${esc(t.title)}</span>
            <small style="display:block;color:var(--steel);font-size:0.75rem;">Assigned to: ${esc(t.assignedTo||'HR')} &bull; Category: ${esc(t.category||'HR')}</small>
          </div>
          ${t.status==='completed' ?
            '<span class="badge badge-published">Completed</span>' :
            `<button class="btn btn-outline btn-sm" onclick="completeOnboardingTask(${t.id})">Mark Done</button>`
          }
        </div>
      `).join('');

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <div>
            <h4 style="margin:0 0 4px;">${esc(empName)}</h4>
            <span style="font-size:0.78rem;color:var(--steel-light);">${completed} of ${list.length} tasks finished (${pct}%)</span>
          </div>
          <span class="badge ${pct===100?'badge-published':'badge-pending'}">${pct}% Done</span>
        </div>
        <div class="progress-bar" style="margin-bottom:14px;"><div class="progress-fill" style="width:${pct}%;"></div></div>
        <div style="display:flex;flex-direction:column;">${taskRows}</div>
      `;
      container.appendChild(card);
    });
  }catch(e){console.error(e);}
}

async function completeOnboardingTask(id){
  try{
    await api('/onboarding/tasks/'+id+'/complete', {method:'POST'});
    loadOnboarding();
  }catch(e){ alert(e.message); }
}

/* ── Module 8: Document Vault & Review Desk ── */
async function loadDocuments(){
  try{
    const statusVal = $('docStatusFilter')?.value || '';
    const catVal = $('docCategoryFilter')?.value || '';
    const qVal = $('docSearchQuery')?.value || '';
    const query = new URLSearchParams();
    if(statusVal) query.set('status', statusVal);
    if(catVal) query.set('category', catVal);
    if(qVal) query.set('q', qVal);

    const docs = await api('/documents/all?' + query.toString());
    const allDocs = await api('/documents/all');

    // Update stats cards
    const statsBox = $('docsReviewStats');
    if(statsBox){
      statsBox.innerHTML = '';
      const total = allDocs.length;
      const pending = allDocs.filter(d=>d.status==='pending' || (!d.verified && !d.status)).length;
      const approved = allDocs.filter(d=>d.status==='approved' || d.verified).length;
      const rejected = allDocs.filter(d=>d.status==='rejected').length;

      [
        [total, 'Total Documents', 'var(--steel-light)'],
        [pending, '⏳ Pending Review', '#e5a93b'],
        [approved, '✓ Approved / Verified', '#38d273'],
        [rejected, '✗ Rejected Submissions', '#e25c5c']
      ].forEach(([val, label, color])=>{
        const card = document.createElement('div');
        card.className = 'stat-card glass-glow';
        card.innerHTML = `<b style="color:${color};">${val}</b><span>${label}</span>`;
        statsBox.appendChild(card);
      });
    }

    const alertBox = $('docExpiryAlert');
    if(alertBox){
      const expiring = allDocs.filter(d=>d.expiringSoon || (d.daysToExpiry !== undefined && d.daysToExpiry <= 30));
      if(expiring.length){
        alertBox.style.display = 'block';
        alertBox.innerHTML = `⚠️ <b>${expiring.length} document(s) expiring within 30 days!</b> (${expiring.map(x=>x.title).join(', ')})`;
      } else {
        alertBox.style.display = 'none';
      }
    }

    const tbody = $('docsBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!docs.length){
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--steel-light);">No documents matching filter criteria.</td></tr>';
      }
      docs.forEach(d=>{
        const tr = document.createElement('tr');
        const st = (d.status || (d.verified ? 'approved' : 'pending')).toLowerCase();
        let badge = '<span class="badge badge-pending">⏳ Pending Review</span>';
        if(st === 'approved') badge = '<span class="badge badge-published">✓ Approved</span>';
        if(st === 'rejected') badge = '<span class="badge badge-rejected">✗ Rejected</span>';

        const fileLink = d.fileUrl ?
          `<a href="${esc(d.fileUrl)}${d.fileUrl.includes('?')?'&':'?'}token=${encodeURIComponent(gToken)}" target="_blank" rel="noopener" style="color:var(--orange);font-weight:600;display:inline-flex;align-items:center;gap:4px;">👁️ View File</a>` :
          '—';

        let reviewerDetails = '—';
        if(st === 'approved' && d.reviewedBy){
          reviewerDetails = `<small style="color:var(--steel-light);">Approved by <b>${esc(d.reviewedBy)}</b></small>`;
        } else if(st === 'rejected'){
          reviewerDetails = `<div style="max-width:220px;color:#e25c5c;font-size:0.78rem;"><b>Reason:</b> ${esc(d.rejectionReason||'Did not meet criteria')}</div>`;
        }

        let actionBtns = `
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-sm btn-primary" onclick="approveDocument(${d.id})" title="Approve this document" style="background:#38d273;border-color:#38d273;padding:4px 10px;font-size:0.75rem;">✓ Approve</button>
            <button class="btn btn-sm btn-outline" onclick="openRejectDocModal(${d.id}, '${esc(d.title)}')" title="Reject this document with feedback" style="color:#e25c5c;border-color:rgba(226,92,92,0.4);padding:4px 10px;font-size:0.75rem;">✗ Reject</button>
          </div>
        `;
        if(st === 'approved'){
          actionBtns = `
            <div style="display:flex;gap:6px;align-items:center;">
              <span style="color:#38d273;font-size:0.8rem;font-weight:600;">✓ Verified</span>
              <button class="btn btn-sm btn-outline" onclick="openRejectDocModal(${d.id}, '${esc(d.title)}')" style="color:#e25c5c;padding:2px 8px;font-size:0.72rem;">Revoke</button>
            </div>
          `;
        } else if(st === 'rejected'){
          actionBtns = `
            <div style="display:flex;gap:6px;align-items:center;">
              <button class="btn btn-sm btn-outline" onclick="approveDocument(${d.id})" style="color:#38d273;padding:3px 8px;font-size:0.75rem;">Change to Approve</button>
            </div>
          `;
        }

        tr.innerHTML = `
          <td>
            <b>${esc(d.employeeName||'Staff')}</b><br/>
            <small style="color:var(--steel-light);">${esc(d.employeeRole||'Employee')}</small>
          </td>
          <td>
            <b>${esc(d.docType||d.title)}</b><br/>
            <small style="color:var(--steel-light);">${esc(d.fileName||d.title)} (${esc(d.fileSize||'—')})</small>
          </td>
          <td><span class="badge badge-draft">${esc(d.category||'other')}</span></td>
          <td><span class="badge badge-draft">v${d.version||1}</span></td>
          <td>${esc((d.uploadedAt||d.createdAt||'').slice(0,10) || '—')}</td>
          <td>${badge}<br/>${reviewerDetails}</td>
          <td>${fileLink}</td>
          <td>${actionBtns}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    on('addDocBtn', 'click', () => {
      openDocUploadModal('', null, '', true);
    });

    on('docCategoryFilter', 'change', loadDocuments);
    on('docStatusFilter', 'change', loadDocuments);
    on('applyDocsFilterBtn', 'click', loadDocuments);
    on('refreshDocsBtn', 'click', loadDocuments);
  }catch(e){console.error(e);}
}

async function approveDocument(docId){
  try{
    await api('/documents/' + docId + '/approve', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({notes: 'Verified and approved by manager/admin'})
    });
    loadDocuments();
    if($('panel-my_documents')?.classList.contains('active')) loadMyDocuments();
  }catch(e){ alert(e.message); }
}

function openRejectDocModal(docId, docTitle){
  openHrmsModal(`Reject Document — ${esc(docTitle)}`, `
    <form id="rejectDocForm" style="display:flex;flex-direction:column;gap:12px;">
      <div style="background:rgba(226,92,92,0.1);border-left:4px solid #e25c5c;padding:10px 14px;border-radius:6px;">
        <p style="margin:0;font-size:0.84rem;color:#e25c5c;">
          When you reject this document, the employee will receive an instant notification with your feedback and will be asked to re-upload a corrected file.
        </p>
      </div>
      <div class="field">
        <label>Select Common Rejection Reason</label>
        <select id="commonRejectReason" onchange="if(this.value)$('rejectReasonInput').value=this.value;">
          <option value="">-- Choose reason or write below --</option>
          <option value="Document scan / photo is blurry and illegible. Please re-upload a clear copy.">Blurry or unreadable scan</option>
          <option value="Document has expired. Please re-upload a currently valid document.">Expired document</option>
          <option value="Official signature / company seal is missing. Please re-upload signed copy.">Missing signature or seal</option>
          <option value="Incorrect document uploaded under this category. Please re-upload the correct file.">Incorrect document uploaded</option>
          <option value="Incomplete document. Please upload all pages (front and back / all semesters).">Incomplete / missing pages</option>
          <option value="Name / details on document do not match employee records.">Name / detail mismatch</option>
        </select>
      </div>
      <div class="field">
        <label>Feedback &amp; Instructions for Re-upload *</label>
        <textarea id="rejectReasonInput" rows="3" required placeholder="Specify why the document is rejected and what the employee should fix when re-uploading…"></textarea>
      </div>
      <button type="submit" class="btn btn-primary" style="background:#e25c5c;border-color:#e25c5c;">Confirm Rejection &amp; Notify Employee</button>
      <div class="form-msg" id="rejectDocMsg"></div>
    </form>
  `);

  $('rejectDocForm').addEventListener('submit', async(e)=>{
    e.preventDefault();
    const reason = $('rejectReasonInput').value.trim();
    if(!reason){ setFormMsg($('rejectDocMsg'), 'Please enter a rejection reason.', false); return; }
    try{
      await api('/documents/' + docId + '/reject', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({reason})
      });
      closeHrmsModal();
      loadDocuments();
      if($('panel-my_documents')?.classList.contains('active')) loadMyDocuments();
    }catch(err){
      setFormMsg($('rejectDocMsg'), err.message, false);
    }
  });
}

/* ── Module 8: My Documents & Policies ── */
async function loadMyDocuments(){
  try{
    const res = await api('/documents/my');
    const myDocs = res.documents || [];
    const checklist = res.checklist || [];
    const policies = res.policies || [];
    const stats = res.stats || {};

    // 1. Render Stats
    const statsBox = $('myDocsStats');
    if(statsBox){
      statsBox.innerHTML = '';
      [
        [stats.totalUploaded || myDocs.length, 'Total Uploaded', 'var(--steel-light)'],
        [stats.approvedCount || 0, '✓ Approved / Verified', '#38d273'],
        [stats.pendingCount || 0, '⏳ Pending Manager Review', '#e5a93b'],
        [stats.rejectedCount || 0, '⚠️ Action Required (Rejected)', stats.rejectedCount > 0 ? '#e25c5c' : 'var(--steel-light)']
      ].forEach(([val, label, color])=>{
        const card = document.createElement('div');
        card.className = 'stat-card glass-glow';
        if(label.includes('Rejected') && val > 0){
          card.style.border = '1px solid #e25c5c';
          card.style.background = 'rgba(226,92,92,0.08)';
        }
        card.innerHTML = `<b style="color:${color};">${val}</b><span>${label}</span>`;
        statsBox.appendChild(card);
      });
    }

    // 2. Rejection Banner (If any document is rejected)
    const rejBanner = $('myDocRejectionBanner');
    const rejList = $('myDocRejectionList');
    const rejectedItems = checklist.filter(c=>c.status==='rejected');
    if(rejBanner && rejList){
      if(rejectedItems.length){
        rejBanner.style.display = 'block';
        rejList.innerHTML = rejectedItems.map(item => `
          <div style="margin-top:8px;padding:8px 12px;background:rgba(255,255,255,0.04);border-radius:8px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div>
              <b style="color:var(--ink);">${esc(item.type)}:</b>
              <span style="color:#e25c5c;"> "${esc(item.rejectionReason||'Needs review')}"</span>
            </div>
            <button class="btn btn-sm btn-primary" onclick="openDocUploadModal('${esc(item.type)}', ${item.document ? item.document.id : 'null'}, '${esc(item.rejectionReason||'')}')" style="background:#e25c5c;border-color:#e25c5c;padding:3px 10px;font-size:0.75rem;">
              🔄 Re-upload Document
            </button>
          </div>
        `).join('');
      } else {
        rejBanner.style.display = 'none';
      }
    }

    // 3. Checklist Badge
    const compBadge = $('checklistCompletionBadge');
    if(compBadge){
      const uploadedCount = checklist.filter(c=>c.isUploaded).length;
      compBadge.textContent = `${uploadedCount} of ${checklist.length} Uploaded`;
      compBadge.className = 'badge ' + (uploadedCount === checklist.length ? 'badge-published' : 'badge-pending');
    }

    // 4. Render 16 Mandatory Document Slots Grid
    const grid = $('mandatoryDocsGrid');
    if(grid){
      grid.innerHTML = '';
      checklist.forEach(item => {
        const card = document.createElement('div');
        card.className = 'form-card glass-glow';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.style.justifyContent = 'space-between';
        card.style.padding = '16px';
        card.style.margin = '0';
        card.style.borderRadius = '12px';

        let statusBadge = '<span class="badge badge-draft">Not Uploaded</span>';
        if(item.status === 'approved') statusBadge = '<span class="badge badge-published">✓ Approved / OK</span>';
        else if(item.status === 'pending') statusBadge = '<span class="badge badge-pending">⏳ Pending Review</span>';
        else if(item.status === 'rejected') {
          statusBadge = '<span class="badge badge-rejected" style="box-shadow:0 0 8px rgba(226,92,92,0.3);">✗ Rejected</span>';
          card.style.border = '1px solid rgba(226,92,92,0.4)';
        }

        let buttonArea = '';
        if(item.status === 'rejected'){
          buttonArea = `
            <div style="margin-top:10px;padding:8px;background:rgba(226,92,92,0.1);border-radius:6px;border-left:3px solid #e25c5c;">
              <small style="color:#e25c5c;display:block;margin-bottom:6px;"><b>Reviewer Feedback:</b> ${esc(item.rejectionReason||'Did not meet criteria')}</small>
              <button class="btn btn-sm btn-primary" onclick="openDocUploadModal('${esc(item.type)}', ${item.document ? item.document.id : 'null'}, '${esc(item.rejectionReason||'')}')" style="width:100%;background:#e25c5c;border-color:#e25c5c;font-weight:600;">
                🔄 Re-upload ${esc(item.type)}
              </button>
            </div>
          `;
        } else if(item.status === 'not_uploaded'){
          buttonArea = `
            <div style="margin-top:12px;">
              <button class="btn btn-sm btn-outline" onclick="openDocUploadModal('${esc(item.type)}')" style="width:100%;">
                📤 Upload Document
              </button>
            </div>
          `;
        } else if(item.status === 'pending'){
          buttonArea = `
            <div style="margin-top:12px;display:flex;gap:8px;">
              <a href="${esc(item.document.fileUrl)}${item.document.fileUrl.includes('?')?'&':'?'}token=${encodeURIComponent(gToken)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline" style="flex:1;text-align:center;">👁️ View File</a>
              <button class="btn btn-sm btn-outline" onclick="openDocUploadModal('${esc(item.type)}', ${item.document.id})" title="Update or replace file">🔄 Replace</button>
            </div>
          `;
        } else if(item.status === 'approved'){
          buttonArea = `
            <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
              <a href="${esc(item.document.fileUrl)}${item.document.fileUrl.includes('?')?'&':'?'}token=${encodeURIComponent(gToken)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline" style="flex:1;text-align:center;color:#38d273;border-color:rgba(56,210,115,0.4);">✓ View Verified File</a>
            </div>
          `;
        }

        card.innerHTML = `
          <div>
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
              <span style="font-size:1.6rem;">${item.icon || '📄'}</span>
              ${statusBadge}
            </div>
            <h4 style="margin:0 0 4px;font-size:0.96rem;">${esc(item.type)}</h4>
            <p style="margin:0;font-size:0.78rem;color:var(--steel-light);line-height:1.35;">${esc(item.description)}</p>
            ${item.document ? `<small style="display:block;margin-top:6px;font-size:0.74rem;color:var(--steel-light);">Version: v${item.document.version||1} &bull; ${esc(item.document.fileSize||'')}</small>` : ''}
          </div>
          ${buttonArea}
        `;
        grid.appendChild(card);
      });
    }

    // 5. Render Upload History Table
    const tbody = $('myDocsBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!myDocs.length){
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--steel-light);">No documents uploaded yet. Click "Upload Document" to begin.</td></tr>';
      }
      myDocs.forEach(d=>{
        const tr = document.createElement('tr');
        const st = (d.status || (d.verified ? 'approved' : 'pending')).toLowerCase();
        let badge = '<span class="badge badge-pending">⏳ Pending Review</span>';
        if(st === 'approved') badge = '<span class="badge badge-published">✓ Approved</span>';
        if(st === 'rejected') badge = '<span class="badge badge-rejected">✗ Rejected</span>';

        const fileLink = d.fileUrl ?
          `<a href="${esc(d.fileUrl)}${d.fileUrl.includes('?')?'&':'?'}token=${encodeURIComponent(gToken)}" target="_blank" rel="noopener" style="color:var(--orange);font-weight:600;">👁️ View</a>` :
          '—';

        let notes = '—';
        if(st === 'rejected'){
          notes = `<span style="color:#e25c5c;font-size:0.8rem;"><b>Rejected:</b> ${esc(d.rejectionReason||'Needs re-upload')}</span>`;
        } else if(st === 'approved' && d.reviewedBy){
          notes = `<span style="color:#38d273;font-size:0.8rem;">Approved by ${esc(d.reviewedBy)}</span>`;
        }

        let actionBtn = fileLink;
        if(st === 'rejected'){
          actionBtn = `
            <div style="display:flex;gap:6px;align-items:center;">
              ${fileLink}
              <button class="btn btn-sm btn-primary" onclick="openDocUploadModal('${esc(d.docType||d.title)}', ${d.id}, '${esc(d.rejectionReason||'')}')" style="background:#e25c5c;border-color:#e25c5c;padding:3px 8px;font-size:0.75rem;">
                🔄 Re-upload
              </button>
            </div>
          `;
        }

        tr.innerHTML = `
          <td><b>${esc(d.title)}</b><br/><small style="color:var(--steel-light);">${esc(d.fileName||'')}</small></td>
          <td><span class="badge badge-draft">${esc(d.category||'other')}</span></td>
          <td><span class="badge badge-draft">v${d.version||1}</span></td>
          <td>${esc((d.uploadedAt||d.createdAt||'').slice(0,10) || '—')}</td>
          <td>${badge}</td>
          <td>${notes}</td>
          <td>${actionBtn}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // 6. Render Company Policies
    const polBox = $('policiesList');
    if(polBox){
      polBox.innerHTML = '';
      if(!policies.length){ polBox.innerHTML = '<div style="color:var(--steel);">No active company policies.</div>'; }
      policies.forEach(p=>{
        const item = document.createElement('div');
        item.className = 'form-card';
        item.style.marginBottom = '12px';
        item.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
            <div>
              <h4 style="margin:0 0 4px;">${esc(p.title)}</h4>
              <p style="margin:0;font-size:0.8rem;color:var(--steel-light);">${esc(p.description||'Corporate governance & code of conduct')}</p>
            </div>
            ${p.acknowledged ?
              '<span class="badge badge-published">✓ Acknowledged</span>' :
              `<button class="btn btn-primary btn-sm" onclick="acknowledgePolicy(${p.id})">Acknowledge &amp; Sign</button>`
            }
          </div>
        `;
        polBox.appendChild(item);
      });
    }

    on('myDocUploadBtn', 'click', () => {
      openDocUploadModal();
    });

  }catch(e){console.error(e);}
}

function openDocUploadModal(prefillType='', docId=null, previousReason='', isCorporate=false){
  const standardTypes = [
    "Employee Resume / CV",
    "Offer Letter",
    "Appointment Letter",
    "Employment Agreement",
    "Joining Letter",
    "Employee ID Proof",
    "Aadhaar Card",
    "PAN Card",
    "Passport",
    "Address Proof",
    "Educational Certificates",
    "Experience Certificates",
    "Relieving Letter",
    "Resignation Letter",
    "Salary Slips",
    "Bank Account Details Form"
  ];

  const typeOptions = standardTypes.map(t =>
    `<option value="${esc(t)}" ${t.toLowerCase() === (prefillType||'').toLowerCase() ? 'selected' : ''}>${esc(t)}</option>`
  ).join('');

  const modalTitle = docId ? `Re-upload Document — ${esc(prefillType||'Update')}` : (prefillType ? `Upload ${esc(prefillType)}` : 'Upload Verification Document');

  const rejectionNotice = previousReason ? `
    <div style="background:rgba(226,92,92,0.12);border-left:4px solid #e25c5c;padding:12px;border-radius:6px;margin-bottom:14px;">
      <b style="color:#e25c5c;display:block;margin-bottom:4px;">⚠️ Previous Rejection Reason:</b>
      <span style="font-size:0.86rem;color:var(--ink);">"${esc(previousReason)}"</span>
      <small style="display:block;margin-top:6px;color:var(--steel-light);">Uploading a replacement file will reset the status to <b>Pending Review</b> so your manager or admin can re-verify it.</small>
    </div>
  ` : '';

  openHrmsModal(modalTitle, `
    <form id="docUploadForm" style="display:flex;flex-direction:column;gap:12px;">
      ${rejectionNotice}
      <div class="field">
        <label>Document Type *</label>
        <select id="uploadDocType" required>
          <option value="">-- Select Document Type --</option>
          ${typeOptions}
          <option value="Other / Additional Document" ${prefillType === 'Other / Additional Document' ? 'selected' : ''}>Other / Additional Document</option>
        </select>
      </div>

      <div class="field">
        <label>Document Title</label>
        <input id="uploadDocTitle" placeholder="e.g. Aadhaar Card - Front & Back" value="${esc(prefillType || '')}"/>
      </div>

      <div class="field">
        <label>Category</label>
        <select id="uploadDocCategory">
          <option value="identity">Identity &amp; Address Proof</option>
          <option value="career">Career / Resume</option>
          <option value="joining">Joining &amp; Offer Letters</option>
          <option value="contract">Employment Agreement</option>
          <option value="educational">Educational Certificates</option>
          <option value="experience">Experience &amp; Relieving</option>
          <option value="financial">Salary &amp; Bank Details</option>
          <option value="lifecycle">Exit / Resignation</option>
          <option value="policy">Corporate Policy</option>
        </select>
      </div>

      <div class="field">
        <label>Attach File (PDF, DOC, DOCX, JPG, PNG, WEBP — Max 10MB) *</label>
        <input type="file" id="uploadDocFile" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.webp" required style="padding:8px;background:rgba(255,255,255,0.03);border:1px dashed var(--glass-border);border-radius:8px;width:100%;"/>
      </div>

      <div class="field">
        <label>Document Expiry Date (If applicable, e.g. Passport/Visa)</label>
        <input type="date" id="uploadDocExpiry"/>
      </div>

      <div class="field">
        <label>Employee Notes / Remarks (Optional)</label>
        <textarea id="uploadDocNotes" rows="2" placeholder="Any special notes or explanations for the reviewer…"></textarea>
      </div>

      <button type="submit" class="btn btn-primary" id="submitDocUploadBtn">
        ${docId ? '🔄 Submit Re-uploaded Document' : '📤 Upload Document for Review'}
      </button>
      <div class="form-msg" id="docUploadFormMsg"></div>
    </form>
  `);

  // Auto-sync title when type selected
  $('uploadDocType')?.addEventListener('change', (e)=>{
    if(!$('uploadDocTitle').value || standardTypes.includes($('uploadDocTitle').value)){
      $('uploadDocTitle').value = e.target.value;
    }
    const val = e.target.value.toLowerCase();
    const cat = $('uploadDocCategory');
    if(cat){
      if(val.includes('aadhaar') || val.includes('pan') || val.includes('passport') || val.includes('id proof') || val.includes('address')) cat.value = 'identity';
      else if(val.includes('resume') || val.includes('cv')) cat.value = 'career';
      else if(val.includes('offer') || val.includes('appointment') || val.includes('joining')) cat.value = 'joining';
      else if(val.includes('agreement') || val.includes('contract')) cat.value = 'contract';
      else if(val.includes('educational')) cat.value = 'educational';
      else if(val.includes('experience') || val.includes('relieving')) cat.value = 'experience';
      else if(val.includes('salary') || val.includes('bank')) cat.value = 'financial';
      else if(val.includes('resignation')) cat.value = 'lifecycle';
    }
  });

  $('docUploadForm').addEventListener('submit', async(e)=>{
    e.preventDefault();
    const btn = $('submitDocUploadBtn');
    const msg = $('docUploadFormMsg');
    const fileInput = $('uploadDocFile');
    if(!fileInput || !fileInput.files || !fileInput.files[0]){
      setFormMsg(msg, 'Please select a document file to upload.', false);
      return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('docType', $('uploadDocType').value);
    formData.append('title', $('uploadDocTitle').value || $('uploadDocType').value);
    formData.append('category', $('uploadDocCategory').value);
    formData.append('expiryDate', $('uploadDocExpiry').value || '');
    formData.append('notes', $('uploadDocNotes').value || '');
    if(docId) formData.append('docId', docId);

    btn.disabled = true;
    btn.textContent = 'Uploading file…';
    try{
      const res = await fetch('/api/documents/upload', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + gToken
        },
        body: formData
      });
      const data = await res.json();
      if(!res.ok){
        throw new Error(data.error || 'Failed to upload document');
      }
      closeHrmsModal();
      loadMyDocuments();
      if($('panel-documents')?.classList.contains('active')) loadDocuments();
    }catch(err){
      setFormMsg(msg, err.message, false);
      btn.disabled = false;
      btn.textContent = docId ? '🔄 Submit Re-uploaded Document' : '📤 Upload Document for Review';
    }
  });
}

async function acknowledgePolicy(id){
  try{
    await api('/documents/policies/'+id+'/acknowledge', {method:'POST'});
    loadMyDocuments();
  }catch(e){ alert(e.message); }
}

/* ── Module 11: Offboarding & Lifecycle ── */
async function loadLifecycle(){
  try{
    const records = await api('/offboarding/records');
    const stats = $('lifecycleStats');
    if(stats){
      stats.innerHTML = '';
      const inProgress = records.filter(r=>r.status!=='completed').length;
      [
        [inProgress, 'Active Resignations'],
        [records.filter(r=>r.status==='completed').length, 'Completed Exits'],
        [records.length, 'Total Lifecycle Records']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const tbody = $('lifecycleBody');
    if(tbody){
      tbody.innerHTML = '';
      if(!records.length){ tbody.innerHTML = '<tr><td colspan="9">No offboarding records.</td></tr>'; }
      records.forEach(r=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${esc(r.employeeName)}</b></td>
          <td>${esc(r.resignationDate||'—')}</td>
          <td>${esc(r.lastWorkingDay||'—')}</td>
          <td>${r.noticePeriodDays||30} days</td>
          <td><span class="badge ${r.knowledgeTransferDone?'badge-published':'badge-pending'}">${r.knowledgeTransferDone?'Done':'Pending'}</span></td>
          <td><span class="badge ${r.assetsReturned?'badge-published':'badge-pending'}">${r.assetsReturned?'Returned':'Pending'}</span></td>
          <td><span class="badge ${r.finalSettlementDone?'badge-published':'badge-pending'}">${r.finalSettlementDone?'Settled':'Pending'}</span></td>
          <td><span class="badge ${r.status==='completed'?'badge-rejected':'badge-pending'}">${esc(r.status)}</span></td>
          <td>
            ${r.status!=='completed' ?
              `<button class="btn btn-danger btn-sm" onclick="finalizeOffboarding(${r.id})">Finalize Exit</button>` :
              `<span style="color:var(--steel);font-size:0.8rem;">Archived</span>`
            }
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  }catch(e){console.error(e);}
}

async function finalizeOffboarding(id){
  if(!confirm('Finalize offboarding for this employee? Account will be deactivated.')) return;
  try{
    await api('/offboarding/records/'+id+'/finalize', {method:'POST'});
    loadLifecycle();
  }catch(e){ alert(e.message); }
}

/* ── Module 10: Reports & Analytics ── */
async function loadReports(){
  try{
    const summary = await api('/reports/analytics-summary');
    const stats = $('reportsStats');
    if(stats){
      stats.innerHTML = '';
      [
        [summary.totalEmployees||0, 'Total Headcount'],
        [summary.punctualityRate||'96.2%', 'Attendance Punctuality'],
        [summary.leaveUtilizationRate||'14.5%', 'Leave Utilization'],
        [`₹${Number(summary.monthlyPayrollCost||0).toLocaleString()}`, 'Monthly Payroll Expense']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const deptBars = $('deptHeadcountBars');
    if(deptBars && summary.headcountByDept){
      deptBars.innerHTML = '';
      const total = summary.totalEmployees || 1;
      Object.entries(summary.headcountByDept).forEach(([dept, count])=>{
        const pct = Math.round((count / total) * 100);
        const item = document.createElement('div');
        item.style.marginBottom = '12px';
        item.innerHTML = `
          <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:4px;">
            <b>${esc(dept)}</b>
            <span>${count} staff (${pct}%)</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;"></div></div>
        `;
        deptBars.appendChild(item);
      });
    }
  }catch(e){console.error(e);}
}

/* ── Module 12: Security & Audit Log ── */
async function loadAuditLog(){
  try{
    const logs = await api('/audit-logs');
    const tbody = $('auditLogBody');
    if(!tbody) return;
    tbody.innerHTML = '';
    if(!logs.length){ tbody.innerHTML = '<tr><td colspan="6">No audit records found.</td></tr>'; }
    logs.slice(0, 50).forEach(l=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="white-space:nowrap;">${l.createdAt ? new Date(l.createdAt).toLocaleString() : '—'}</td>
        <td><b>${esc(l.adminName||l.actor||'System')}</b></td>
        <td><span class="badge badge-draft">${esc(l.role||'admin')}</span></td>
        <td><code>${esc(l.action)}</code></td>
        <td><small>${esc(l.ipAddress||'127.0.0.1')}</small></td>
        <td>${esc(l.details||'—')}</td>
      `;
      tbody.appendChild(tr);
    });
  }catch(e){console.error(e);}
}

/* ── Module 3 & 7: Manager Team Modules ── */
async function loadTeam(){
  try{
    const members = await api('/manager/team');
    const stats = $('teamStats');
    if(stats){
      stats.innerHTML = '';
      [
        [members.length, 'Direct Reports'],
        [members.filter(m=>m.presentToday).length, 'Present Today'],
        [members.filter(m=>m.onLeaveToday).length, 'On Leave Today']
      ].forEach(([v,l])=>{
        const d = document.createElement('div');
        d.className = 'stat-card glass-glow';
        d.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(d);
      });
    }

    const grid = $('teamGrid');
    if(!grid) return;
    grid.innerHTML = '';
    if(!members.length){ grid.innerHTML = '<div style="color:var(--steel);">No direct reports assigned.</div>'; return; }
    members.forEach(m=>{
      const card = document.createElement('div');
      card.className = 'form-card glass-glow';
      card.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
          <div style="width:44px;height:44px;border-radius:999px;background:var(--orange);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem;">${esc(m.name.charAt(0))}</div>
          <div>
            <h4 style="margin:0;">${esc(m.name)}</h4>
            <span style="font-size:0.75rem;color:var(--steel-light);">${esc(m.designation||'Engineer')} &bull; ${esc(m.employeeCode||'KYK-001')}</span>
          </div>
        </div>
        <p style="margin:0 0 8px;font-size:0.8rem;color:var(--steel);">Email: ${esc(m.email)}<br/>Phone: ${esc(m.phone||'—')}<br/>Shift: ${esc(m.shift||'General (09:30 – 18:30)')}</p>
        <span class="badge ${m.presentToday?'badge-approved':'badge-draft'}">${m.presentToday?'Clocked In Today':'Not Punched'}</span>
      `;
      grid.appendChild(card);
    });
  }catch(e){console.error(e);}
}

async function loadTeamAttendance(){
  try{
    const dateInput = $('teamAttDate');
    if(dateInput && !dateInput.value) dateInput.value = new Date().toISOString().slice(0,10);
    const date = dateInput?.value || new Date().toISOString().slice(0,10);
    const d = await api('/manager/team-attendance?date='+encodeURIComponent(date));

    const stats = $('teamAttStats');
    if(stats){
      stats.innerHTML = '';
      [
        [d.present||0, 'Present'],
        [d.late||0, 'Late Arrivals'],
        [d.onLeave||0, 'On Leave'],
        [d.absent||0, 'Absent']
      ].forEach(([v,l])=>{
        const dEl = document.createElement('div');
        dEl.className = 'stat-card glass-glow';
        dEl.innerHTML = `<b>${v}</b><span>${l}</span>`;
        stats.appendChild(dEl);
      });
    }

    const tbody = $('teamAttBody');
    if(tbody){
      tbody.innerHTML = '';
      const rows = d.rows || [];
      if(!rows.length){ tbody.innerHTML = '<tr><td colspan="6">No attendance punches recorded for this date.</td></tr>'; }
      rows.forEach(r=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><b>${esc(r.employeeName)}</b></td>
          <td>${esc(r.shiftName||'General')}</td>
          <td>${esc(r.checkIn||'—')}</td>
          <td>${esc(r.checkOut||'—')}</td>
          <td>${r.workedHours!=null ? r.workedHours+' hrs' : '—'}</td>
          <td><span class="badge ${r.dayStatus==='present'?'badge-approved':'badge-draft'}">${esc(r.dayStatus||'absent')}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }

    on('refreshTeamAttBtn', 'click', loadTeamAttendance);
  }catch(e){console.error(e);}
}

async function loadTeamLeaves(){
  try{
    const rows = await api('/manager/leave');
    const tbody = $('teamLeavesBody');
    if(!tbody) return;
    tbody.innerHTML = '';
    if(!rows.length){ tbody.innerHTML = '<tr><td colspan="7">No leave applications from team members.</td></tr>'; }
    rows.forEach(r=>{
      const tr = document.createElement('tr');
      const badgeClass = r.status==='approved'?'badge-approved':(r.status==='rejected'?'badge-rejected':'badge-pending');
      let actions = '—';
      if(r.status==='pending'){
        actions = `
          <button class="btn btn-success btn-sm" onclick="decideLeave(${r.id}, 'approved')">Approve</button>
          <button class="btn btn-danger btn-sm" style="margin-left:4px;" onclick="decideLeave(${r.id}, 'rejected')">Reject</button>
        `;
      }
      tr.innerHTML = `
        <td><b>${esc(r.adminName||r.employeeName||'Staff')}</b></td>
        <td>${esc(r.type||r.leaveType||'Casual Leave')}</td>
        <td>${esc(r.fromDate)} &rarr; ${esc(r.toDate)}</td>
        <td>${r.totalDays||1} d</td>
        <td>${esc(r.reason||'—')}</td>
        <td><span class="badge ${badgeClass}">${esc(r.status)}</span></td>
        <td>${actions}</td>
      `;
      tbody.appendChild(tr);
    });
  }catch(e){console.error(e);}
}

async function loadTeamGoals(){
  try{
    const goals = await api('/performance/team-goals');
    const container = $('teamGoalsList');
    if(!container) return;
    container.innerHTML = '';
    if(!goals.length){ container.innerHTML = '<div style="color:var(--steel);">No team goals active.</div>'; }
    goals.forEach(g=>{
      const card = document.createElement('div');
      card.className = 'form-card';
      card.style.marginBottom = '14px';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <div>
            <h4 style="margin:0 0 2px;">${esc(g.title)}</h4>
            <span style="font-size:0.78rem;color:var(--steel-light);">Assigned to: <b>${esc(g.employeeName||'Staff')}</b> &bull; Target: ${esc(g.metricTarget||'100%')}</span>
          </div>
          <span class="badge badge-published">${g.progressPercent||0}% Completed</span>
        </div>
        <div class="progress-bar" style="margin-bottom:10px;"><div class="progress-fill" style="width:${g.progressPercent||0}%;"></div></div>
        <p style="margin:0;font-size:0.8rem;color:var(--steel);">${esc(g.description||'')}</p>
      `;
      container.appendChild(card);
    });

    on('addTeamGoalBtn', 'click', () => {
      openHrmsModal('Assign Goal to Team Member', `
        <form id="addGoalForm" style="display:flex;flex-direction:column;gap:12px;">
          <div class="field"><label>Employee ID *</label><input type="number" id="goalEmpId" value="4" required/></div>
          <div class="field"><label>Goal Title *</label><input id="goalTitle" placeholder="e.g. Deliver Microservices Migration" required/></div>
          <div class="field"><label>Target Metric *</label><input id="goalMetric" placeholder="e.g. 99.9% Uptime, Zero Severity 1 bugs" required/></div>
          <div class="field"><label>Description</label><textarea id="goalDesc" rows="2"></textarea></div>
          <button type="submit" class="btn btn-primary">Assign Goal</button>
          <div class="form-msg" id="goalMsg"></div>
        </form>
      `);
      $('addGoalForm').addEventListener('submit', async(e)=>{
        e.preventDefault();
        try{
          await api('/performance/team-goals', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
              employeeId:Number($('goalEmpId').value),
              title:$('goalTitle').value,
              metricTarget:$('goalMetric').value,
              description:$('goalDesc').value
            })
          });
          closeHrmsModal(); loadTeamGoals();
        }catch(err){ setFormMsg($('goalMsg'), err.message, false); }
      });
    });
  }catch(e){console.error(e);}
}

async function loadTeamReviews(){
  try{
    const reviews = await api('/performance/team-reviews');
    const container = $('teamReviewsList');
    if(!container) return;
    container.innerHTML = '';
    if(!reviews.length){ container.innerHTML = '<div style="color:var(--steel);">No pending reviews for this cycle.</div>'; }
    reviews.forEach(r=>{
      const card = document.createElement('div');
      card.className = 'form-card';
      card.style.marginBottom = '16px';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
          <div>
            <h4 style="margin:0 0 2px;">Appraisal Review: ${esc(r.employeeName||'Staff')}</h4>
            <span style="font-size:0.75rem;color:var(--steel-light);">${esc(r.cycleTitle||'Annual Review')} &bull; Status: ${esc(r.status||'submitted')}</span>
          </div>
          <span class="badge ${r.status==='completed'?'badge-published':'badge-pending'}">${esc(r.status)}</span>
        </div>
        <div style="background:rgba(255,255,255,0.03);padding:10px;border-radius:8px;margin-bottom:12px;font-size:0.82rem;">
          <b>Employee Self-Assessment:</b>
          <p style="margin:4px 0 0;color:var(--steel-light);">${esc(r.selfAssessment||'Awaiting submission.')}</p>
        </div>
        <form onsubmit="submitManagerReview(event, ${r.id})" style="display:flex;gap:12px;align-items:flex-end;">
          <div class="field" style="width:120px;margin-bottom:0;"><label>Rating (1-5)</label><input type="number" id="mRating_${r.id}" min="1" max="5" value="${r.managerRating||5}" required/></div>
          <div class="field" style="flex:1;margin-bottom:0;"><label>Manager Feedback</label><input id="mFeedback_${r.id}" value="${esc(r.managerFeedback||'')}" placeholder="Manager constructive feedback" required/></div>
          <button type="submit" class="btn btn-primary btn-sm">Save Review</button>
        </form>
      `;
      container.appendChild(card);
    });
  }catch(e){console.error(e);}
}

async function submitManagerReview(e, id){
  e.preventDefault();
  try{
    await api('/performance/reviews/'+id+'/submit-manager', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        managerRating:Number($('mRating_'+id).value),
        managerFeedback:$('mFeedback_'+id).value
      })
    });
    alert('Manager review saved.'); loadTeamReviews();
  }catch(err){ alert(err.message); }
}

async function loadTeamCalendar(){
  try{
    const cal = await api('/leave/team-calendar');
    const container = $('teamCalendarView');
    if(!container) return;
    const leaves = cal.leaves || [];
    const holidays = cal.holidays || [];
    container.innerHTML = `
      <h4>Company Holidays &amp; Observed Days</h4>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-bottom:20px;">
        ${holidays.map(h=>`
          <div style="background:rgba(255,255,255,0.03);border:1px solid var(--glass-border);padding:10px;border-radius:8px;">
            <b style="color:var(--orange);">${esc(h.name)}</b>
            <small style="display:block;color:var(--steel);">${esc(h.date)}</small>
          </div>
        `).join('')}
      </div>
      <h4>Upcoming Team Leave Schedule</h4>
      <table><thead><tr><th>Employee</th><th>Leave Type</th><th>Dates</th><th>Status</th></tr></thead><tbody>
        ${leaves.length ? leaves.map(l=>`
          <tr>
            <td><b>${esc(l.adminName||l.employeeName||'Staff')}</b></td>
            <td>${esc(l.type||l.leaveType||'Leave')}</td>
            <td>${esc(l.fromDate)} &rarr; ${esc(l.toDate)}</td>
            <td><span class="badge ${l.status==='approved'?'badge-approved':'badge-pending'}">${esc(l.status)}</span></td>
          </tr>
        `).join('') : '<tr><td colspan="4">No team leaves scheduled.</td></tr>'}
      </tbody></table>
    `;
  }catch(e){console.error(e);}
}

/* ── Module 7: My Goals & Review (Employee) ── */
async function loadMyGoals(){
  try{
    const [goals, reviews] = await Promise.all([
      api('/performance/my-goals'),
      api('/performance/my-reviews')
    ]);

    const container = $('myGoalsList');
    if(container){
      container.innerHTML = '';
      if(!goals.length){ container.innerHTML = '<div style="color:var(--steel);">No active performance goals assigned.</div>'; }
      goals.forEach(g=>{
        const card = document.createElement('div');
        card.className = 'form-card';
        card.style.marginBottom = '14px';
        card.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div>
              <h4 style="margin:0 0 2px;">${esc(g.title)}</h4>
              <span style="font-size:0.78rem;color:var(--steel-light);">Target: ${esc(g.metricTarget||'100%')}</span>
            </div>
            <span class="badge badge-published" id="goalPctLabel_${g.id}">${g.progressPercent||0}%</span>
          </div>
          <div class="progress-bar" style="margin-bottom:10px;"><div class="progress-fill" id="goalBar_${g.id}" style="width:${g.progressPercent||0}%;"></div></div>
          <div style="display:flex;gap:12px;align-items:center;margin-top:10px;">
            <input type="range" min="0" max="100" value="${g.progressPercent||0}" id="goalSlider_${g.id}" style="flex:1;" oninput="updateGoalPreview(${g.id}, this.value)"/>
            <button class="btn btn-outline btn-sm" onclick="saveGoalProgress(${g.id})">Save Progress</button>
          </div>
        `;
        container.appendChild(card);
      });
    }

    const revBox = $('myReviewContainer');
    if(revBox){
      revBox.innerHTML = '';
      if(!reviews.length){ revBox.innerHTML = '<div style="color:var(--steel);">No open appraisal cycle currently.</div>'; }
      reviews.forEach(r=>{
        const item = document.createElement('div');
        item.className = 'form-card';
        item.innerHTML = `
          <h4>${esc(r.cycleTitle||'Annual Performance Appraisal')}</h4>
          <p style="font-size:0.82rem;color:var(--steel-light);margin-bottom:12px;">Submit your annual accomplishments, self-rating, and milestones for manager feedback.</p>
          <form onsubmit="submitSelfReview(event, ${r.id})">
            <div class="field"><label>Self-Assessment Summary *</label><textarea id="selfSummary_${r.id}" rows="3" required>${esc(r.selfAssessment||'')}</textarea></div>
            <div class="field" style="max-width:140px;"><label>Self-Rating (1-5)</label><input type="number" id="selfRating_${r.id}" min="1" max="5" value="${r.selfRating||5}" required/></div>
            <button type="submit" class="btn btn-primary btn-sm">Submit Self-Assessment</button>
            ${r.managerFeedback ? `<div style="margin-top:12px;background:rgba(56,210,115,0.08);border:1px solid #38d273;border-radius:8px;padding:10px;font-size:0.82rem;"><b>Manager Rating:</b> ${r.managerRating}/5<br/><b>Manager Feedback:</b> ${esc(r.managerFeedback)}</div>` : ''}
          </form>
        `;
        revBox.appendChild(item);
      });
    }
  }catch(e){console.error(e);}
}

function updateGoalPreview(id, val){
  const bar = $('goalBar_'+id), lbl = $('goalPctLabel_'+id);
  if(bar) bar.style.width = val + '%';
  if(lbl) lbl.textContent = val + '%';
}

async function saveGoalProgress(id){
  const slider = $('goalSlider_'+id);
  if(!slider) return;
  try{
    await api('/performance/goals/'+id+'/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({progressPercent:Number(slider.value)})
    });
    alert('Goal progress updated.');
  }catch(e){ alert(e.message); }
}

async function submitSelfReview(e, id){
  e.preventDefault();
  try{
    await api('/performance/reviews/'+id+'/submit-self', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        selfAssessment:$('selfSummary_'+id).value,
        selfRating:Number($('selfRating_'+id).value)
      })
    });
    alert('Self-assessment submitted.');
  }catch(err){ alert(err.message); }
}

/* ── Punch Correction Modal Helper ── */
function openCorrectionModal(){
  openHrmsModal('Request Attendance Punch Correction', `
    <form id="punchCorrForm" style="display:flex;flex-direction:column;gap:12px;">
      <div class="field"><label>Date of Missed / Erroneous Punch *</label><input type="date" id="pcDate" value="${new Date().toISOString().slice(0,10)}" required/></div>
      <div class="field"><label>Requested Check-In (HH:MM) *</label><input type="time" id="pcIn" value="09:30" required/></div>
      <div class="field"><label>Requested Check-Out (HH:MM) *</label><input type="time" id="pcOut" value="18:30" required/></div>
      <div class="field"><label>Reason for Correction *</label><textarea id="pcReason" rows="3" placeholder="Explain why the punch was missed (e.g. client meeting, biometric scanner error, field visit)" required></textarea></div>
      <button type="submit" class="btn btn-primary">Submit for HR Approval</button>
      <div class="form-msg" id="pcMsg"></div>
    </form>
  `);
  $('punchCorrForm').addEventListener('submit', async(e)=>{
    e.preventDefault();
    const msg = $('pcMsg');
    try{
      await api('/attendance/correction-request', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          date:$('pcDate').value,
          checkIn:$('pcIn').value,
          checkOut:$('pcOut').value,
          reason:$('pcReason').value.trim()
        })
      });
      setFormMsg(msg, 'Correction request submitted for HR approval.', true);
      setTimeout(()=>{ closeHrmsModal(); }, 1400);
    }catch(err){ setFormMsg(msg, err.message, false); }
  });
}
