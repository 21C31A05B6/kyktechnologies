// main.js — shared behavior across all pages.
if (!document.querySelector('script[src^="/js/pwa.js"]')) {
  const pwaScript = document.createElement("script");
  pwaScript.src = "/js/pwa.js?v=20261001-logo-2";
  document.head.appendChild(pwaScript);
}
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
      <p style="margin:0; max-inline-size:260px; font-size:.88rem;">${subtitle}</p>`;
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
      <div><b>KYK AI</b><span>Ask about services, careers, AI, or say "open careers"</span></div>
    </div>
    <div class="kyk-assistant-body" id="kykChatBody">
      <div class="kyk-msg bot">Hi! I'm the <b>KYK AI Assistant</b>. Ask me anything about our services, open roles, AI research, or type a page name and <b>"open"</b> (e.g. <i>"careers open"</i> or <i>"open contact"</i>) to navigate!</div>
    </div>
    <div class="kyk-assistant-quick">
      <button type="button" data-q="What services does KYK offer?">Services</button>
      <button type="button" data-q="What jobs are open right now?">Open roles</button>
      <button type="button" data-q="Tell me about KYK Technologies">About KYK</button>
      <button type="button" data-q="open careers">Open Careers</button>
      <button type="button" data-q="open contact">Open Contact</button>
    </div>
    <form class="kyk-assistant-form" id="kykChatForm">
      <input type="text" id="kykChatInput" placeholder="Ask a question or type 'careers open'…" autocomplete="off" />
      <button type="submit" aria-label="Send">→</button>
    </form>`;
  document.body.append(btn, panel);
  btn.addEventListener("click", () => {
    panel.classList.toggle("is-open");
    if (panel.classList.contains("is-open")) {
      const inp = panel.querySelector("#kykChatInput");
      if (inp) inp.focus();
    }
  });

  const chatBody = panel.querySelector("#kykChatBody");
  const assistantHistory = [];

  const assistantPages = [
    { name: "Home", path: "/index.html", aliases: ["home", "homepage", "main page", "index", "landing", "main"] },
    { name: "Global Recruitment", path: "/global-recruitment.html", aliases: ["global recruitment", "recruitment", "recruiting", "recruit", "talent", "staffing", "hire talent", "talent pool"] },
    { name: "Intelligence & AI", path: "/ai.html", aliases: ["intelligence", "ai", "agi", "asi", "artificial intelligence", "machine learning", "ai solutions", "ai practice"] },
    { name: "Services", path: "/services.html", aliases: ["services", "service", "work", "software", "web development", "software development", "cloud", "devops", "solutions"] },
    { name: "Careers", path: "/careers.html", aliases: ["careers", "career", "jobs", "job", "openings", "open roles", "hiring", "positions", "vacancies", "job openings"] },
    { name: "Insights", path: "/insights.html", aliases: ["insights", "insight", "articles", "news", "blog", "blogs"] },
    { name: "About Us", path: "/about.html", aliases: ["about us", "about", "company", "who we are", "about company", "story", "mission"] },
    { name: "Contact", path: "/contact.html", aliases: ["contact us", "contact", "support", "help", "reach us", "get in touch", "address", "email", "phone"] },
    { name: "Login", path: "/login.html", aliases: ["login", "sign in", "signin", "log in"] },
    { name: "Signup", path: "/login.html?mode=signup", aliases: ["signup", "sign up", "register", "registration", "create account"] },
    { name: "Client Portal", path: "/client-portal.html", aliases: ["client portal", "client", "portal", "clients"] },
    { name: "Privacy Policy", path: "/privacy.html", aliases: ["privacy policy", "privacy"] },
    { name: "Terms of Service", path: "/terms.html", aliases: ["terms of service", "terms", "tos"] },
    { name: "Admin Dashboard", path: "/admin.html", aliases: ["admin dashboard", "admin page", "admin portal", "admin"] },
    { name: "HR Dashboard", path: "/hr-dashboard.html", aliases: ["hr dashboard", "human resources dashboard", "hr page", "hr"] },
    { name: "Recruiter Dashboard", path: "/recruiter-dashboard.html", aliases: ["recruiter dashboard", "recruiter page", "recruiter"] },
    { name: "Team Lead Dashboard", path: "/team-lead-dashboard.html", aliases: ["team lead dashboard", "team lead page", "team lead"] },
    { name: "Employee Dashboard", path: "/employee-dashboard.html", aliases: ["employee dashboard", "employee page", "employee"] },
    { name: "Content Dashboard", path: "/content-dashboard.html", aliases: ["content dashboard", "content page", "content"] },
    { name: "Viewer Dashboard", path: "/viewer-dashboard.html", aliases: ["viewer dashboard", "viewer page", "viewer"] },
  ];

  function requestedAssistantPage(question) {
    const raw = (question || "").trim().toLowerCase();
    const cleanStr = raw.replace(/[^\w\s\.-]/g, " ").replace(/\s+/g, " ").trim();
    if (!cleanStr) return null;

    // Check direct filename match
    for (const p of assistantPages) {
      const fn = p.path.split("/").pop().split("?")[0].toLowerCase();
      if (cleanStr.includes(fn)) return p;
    }

    const navWords = /\b(open|go\s*to|goto|navigate|visit|take\s*me\s*to|show\s*me|display|load|launch|bring\s*up|view)\b/i;
    const hasNav = navWords.test(cleanStr);
    const hasOpen = /\bopen\b/i.test(cleanStr);

    if (!hasNav && !hasOpen) return null;

    const stripped = cleanStr
      .replace(navWords, " ")
      .replace(/\b(open|page|pages|screen|portal|tab|website|webpage|the|me|to|please|can|you|i|want|would|like|just)\b/gi, " ")
      .replace(/\s+/g, " ")
      .trim();

    let bestMatch = null;
    let bestScore = 0;

    for (const page of assistantPages) {
      for (const alias of page.aliases) {
        const aliasClean = alias.toLowerCase();
        const escAlias = aliasClean.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
        const pattern = new RegExp("(^|\\s)" + escAlias + "(\\s|$)", "i");
        let score = 0;
        if (stripped === aliasClean) {
          score = 100;
        } else if (pattern.test(stripped)) {
          score = 80 + aliasClean.length;
        } else if (pattern.test(cleanStr)) {
          score = 50 + aliasClean.length;
        }
        if (score > bestScore) {
          bestScore = score;
          bestMatch = page;
        }
      }
    }

    return bestScore > 0 ? bestMatch : null;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatBotText(raw) {
    if (!raw) return "";
    let s = escapeHtml(raw);

    // Format markdown bold **text**
    s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Format markdown italic *text*
    s = s.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Format markdown links [text](url)
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Auto-link relative page paths like /careers.html
    s = s.replace(/(^|\s)(\/[a-z0-9_-]+\.html(\?[a-z0-9_=&-]+)?)/gi, '$1<a href="$2">$2</a>');

    // Bullet points
    s = s.replace(/^[•\-\*]\s+(.*)$/gm, '<li style="margin-left:14px;list-style:disc;">$1</li>');

    // Convert newlines
    s = s.replace(/\n\n+/g, "<br/><br/>").replace(/\n/g, "<br/>");
    return s;
  }

  function generateClientAiReply(question, history) {
    const q = (question || "").toLowerCase().trim();

    // 1. Greetings
    if (/\b(hi|hii|hiii|hello|hey|heya|howdy|sup|greetings|good\s*(morning|afternoon|evening|day))\b/.test(q)) {
      return (
        "Hello! 👋 I'm the **KYK AI Assistant**.\n\n" +
        "I'm here to answer any questions about **KYK Technologies**, including:\n" +
        "• **Global Recruitment**: International talent sourcing & tech hiring\n" +
        "• **Software & Web Development**: Scalable web apps, APIs & cloud platforms\n" +
        "• **Artificial Intelligence**: Generative AI, autonomous agents & research into AGI/ASI\n" +
        "• **Careers & Jobs**: Open positions & application process\n\n" +
        "💡 *Tip: You can also open any page directly by typing its name and 'open' (for example: **'careers open'** or **'contact open'*)!*"
      );
    }

    // 2. About KYK / Who are you / Meaning of KYK
    if (/\b(who are you|what is kyk|about kyk|tell me about kyk|company info|what do you do|what does kyk do|key to your kognitio|kognitio|founders|headquarters|location|based)\b/.test(q)) {
      return (
        "**KYK Technologies** (Key to Your Kognitio — Knowledge, Yield, Kognitio) is an advanced technology and global recruitment firm headquartered in Warangal, Telangana, India, operating worldwide.\n\n" +
        "Our core pillars:\n" +
        "1. **Global Recruitment** (/global-recruitment.html): Sourcing elite engineering, AI, and leadership talent for companies worldwide.\n" +
        "2. **Software & Web Development** (/services.html): Engineering enterprise web applications, cloud systems, and high-performance digital products.\n" +
        "3. **Artificial Intelligence** (/ai.html): Building applied AI solutions, autonomous LLM agents, and conducting foundational research toward AGI and ASI.\n\n" +
        "You can say **'open about'** to visit our About Us page!"
      );
    }

    // 3. Services / Software / Web Development
    if (/\b(service|services|software|web dev|web development|app development|mobile|cloud|devops|api|tech stack|build|offerings|solutions)\b/.test(q)) {
      return (
        "**KYK Technologies** provides end-to-end software and cloud engineering services:\n\n" +
        "• **Web & Application Development**: Responsive, high-performance web applications built on modern frameworks.\n" +
        "• **Cloud & DevOps**: Scalable deployments, CI/CD automation, Docker/Kubernetes containerization, and cloud infrastructure management.\n" +
        "• **Enterprise Software**: Secure backend APIs, database optimization, and scalable microservices.\n" +
        "• **UI/UX Design**: Human-centered interface design optimized for usability and speed.\n\n" +
        "Say **'services open'** or **'open services'** to explore our work!"
      );
    }

    // 4. Global Recruitment / Talent / Hiring
    if (/\b(recruit|recruitment|talent|staffing|hire|hiring candidate|talent pool|headhunt|sourcing)\b/.test(q)) {
      return (
        "Our **Global Recruitment** division helps organizations worldwide build elite technology teams:\n\n" +
        "• **Specialized Tech Sourcing**: Vetting top software engineers, AI researchers, cloud architects, and product leaders.\n" +
        "• **Global Talent Pool**: Connecting cross-border candidates across North America, Europe, Asia, and emerging markets.\n" +
        "• **Flexible Models**: Direct hire, contract-to-hire, and dedicated remote engineering teams.\n\n" +
        "Type **'recruitment open'** or **'open recruitment'** to learn more!"
      );
    }

    // 5. AI / AGI / ASI / Machine Learning
    if (/\b(ai|agi|asi|artificial intelligence|machine learning|generative ai|llm|agent|agents|neural)\b/.test(q)) {
      return (
        "At **KYK Technologies**, our Intelligence practice spans three evolutionary phases:\n\n" +
        "• **Today (Applied & Generative AI)**: Custom LLMs, retrieval-augmented generation (RAG), and intelligent enterprise automation.\n" +
        "• **Tomorrow (Autonomous AI Agents)**: Multi-agent systems capable of end-to-end autonomous execution and decision-making.\n" +
        "• **Future (AGI & ASI)**: Active exploratory research into Artificial General Intelligence and Artificial Superintelligence.\n\n" +
        "Type **'ai open'** or **'open ai'** to explore our Intelligence research!"
      );
    }

    // 6. Careers / Jobs / Openings / Applications / Resumes
    if (/\b(career|careers|job|jobs|role|roles|opening|openings|vacancy|vacancies|hiring|apply|application|resume|cv)\b/.test(q)) {
      return (
        "KYK Technologies is actively hiring passionate talent! 🚀\n\n" +
        "• **Current Openings**: Full Stack Engineers, AI/ML Engineers, Frontend Developers, Backend Engineers, and Global Recruitment Specialists.\n" +
        "• **How to Apply**: Visit our Careers page (/careers.html), pick your role, and submit your resume.\n" +
        "• **Accepted Formats**: PDF, DOC, or DOCX (up to 5 MB).\n\n" +
        "Type **'careers open'** or **'open careers'** to see open positions and apply now!"
      );
    }

    // 7. Contact / Email / Location / Office
    if (/\b(contact|email|phone|address|location|headquarters|office|where are you|reach|get in touch|support)\b/.test(q)) {
      return (
        "You can connect with the KYK Technologies team anytime:\n\n" +
        "• **Email**: hello@kyktechnologies.com\n" +
        "• **Headquarters**: Warangal, Telangana, India (Global operations)\n" +
        "• **Contact Form**: Available at /contact.html\n" +
        "• **Response Time**: Within 24 business hours.\n\n" +
        "Type **'contact open'** or **'open contact'** to reach our contact page!"
      );
    }

    // 8. Dashboards & Portals
    if (/\b(dashboard|portal|portals|admin|hr|recruiter|employee|team lead|content|viewer|client portal|login|signup)\b/.test(q)) {
      return (
        "KYK Technologies includes comprehensive role-based portals:\n\n" +
        "• **Client Portal** (/client-portal.html): Project milestones & deliverables\n" +
        "• **Admin Dashboard** (/admin.html): Platform management & users\n" +
        "• **HR Dashboard** (/hr-dashboard.html): Employee records & attendance\n" +
        "• **Recruiter Dashboard** (/recruiter-dashboard.html): Candidate pipeline\n" +
        "• **Employee Dashboard** (/employee-dashboard.html): Check-in & task tracking\n" +
        "• **Login / Signup** (/login.html): Authentication portal\n\n" +
        "Type **'admin open'**, **'hr open'**, or **'login open'** to go directly to any portal!"
      );
    }

    // 9. Pricing / Quote
    if (/\b(price|pricing|cost|quote|rates|hire us|how much)\b/.test(q)) {
      return (
        "We offer transparent, flexible engagement models tailored to your requirements:\n\n" +
        "• **Dedicated Engineering Pods**: Dedicated full-stack teams tailored to your roadmap.\n" +
        "• **Milestone-Based Projects**: Fixed-scope deliverables with transparent timelines.\n" +
        "• **Talent Placement**: Success-based global talent acquisition.\n\n" +
        "Contact us at **hello@kyktechnologies.com** or type **'contact open'** for a tailored quote!"
      );
    }

    // 10. General Intelligent Fallback
    return (
        "Thank you for asking about **" + escapeHtml(question.slice(0, 60)) + "**!\n\n" +
        "**KYK Technologies** is dedicated to transforming businesses through **Global Recruitment**, **Software & Web Development**, and **Artificial Intelligence (AI / AGI / ASI)** solutions.\n\n" +
        "Here are a few quick pages you can explore:\n" +
        "• Type **'careers open'** to view open positions\n" +
        "• Type **'services open'** to see our software capabilities\n" +
        "• Type **'ai open'** to learn about our AI practice\n" +
        "• Type **'contact open'** to get in touch with our team"
    );
  }

  function pushMsg(content, who, isHtml = false) {
    const m = document.createElement("div");
    m.className = "kyk-msg " + who;
    if (isHtml) {
      m.innerHTML = content;
    } else {
      m.textContent = content;
    }
    chatBody.appendChild(m);
    chatBody.scrollTop = chatBody.scrollHeight;
    return m;
  }

  async function askAssistant(question) {
    const qTrimmed = (question || "").trim();
    if (!qTrimmed) return;

    // Display user bubble
    pushMsg(qTrimmed, "user");

    // 1. Check if user asked to open a page (e.g. "careers open", "open contact")
    const requestedPage = requestedAssistantPage(qTrimmed);
    if (requestedPage) {
      const cardHtml =
        `Opening <strong>${escapeHtml(requestedPage.name)}</strong>...` +
        `<br/><a href="${requestedPage.path}" class="kyk-chat-nav-btn">Open ${escapeHtml(requestedPage.name)} →</a>`;
      pushMsg(cardHtml, "bot", true);
      setTimeout(() => {
        window.location.assign(requestedPage.path);
      }, 400);
      return;
    }

    // Show typing indicator
    const typing = document.createElement("div");
    typing.className = "kyk-msg bot typing";
    typing.innerHTML = "<span></span><span></span><span></span>";
    chatBody.appendChild(typing);
    chatBody.scrollTop = chatBody.scrollHeight;

    let reply = null;
    let openPageTarget = null;

    // Try backend API first (both relative and local fallback port 3000 if running on Live Server :5500)
    const endpoints = ["/api/assistant"];
    if (window.location.port !== "3000" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
      endpoints.push("http://localhost:3000/api/assistant");
      endpoints.push("http://127.0.0.1:3000/api/assistant");
    }

    for (const ep of endpoints) {
      try {
        const controller = new AbortController();
        const tid = setTimeout(() => controller.abort(), 9000);
        const res = await fetch(ep, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: qTrimmed, history: assistantHistory.slice(-8) }),
          signal: controller.signal,
        });
        clearTimeout(tid);
        if (res.ok) {
          const data = await res.json();
          if (data && data.reply) {
            reply = data.reply;
            if (data.open_page) openPageTarget = data.open_page;
            break;
          }
        }
      } catch (_) {
        // Continue to next endpoint or fallback
      }
    }

    typing.remove();

    // Fall back to client-side real AI intelligence if backend was unreachable
    if (!reply) {
      reply = generateClientAiReply(qTrimmed, assistantHistory);
    }

    // Render formatted response
    pushMsg(formatBotText(reply), "bot", true);

    // If backend indicated a page redirect
    if (openPageTarget) {
      setTimeout(() => window.location.assign(openPageTarget), 600);
    }

    assistantHistory.push({ role: "user", content: qTrimmed }, { role: "assistant", content: reply });
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

