(() => {
  const p = (location.pathname || "").toLowerCase();
  if (p.includes("admin") || p.includes("dashboard") || p.includes("communication") || p.includes("portal") || p.includes("login")) {
    return;
  }

  const DISMISS_KEY = "kyk-install-dismissed";
  let installPrompt = null;

  const isInstalled = () => window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true || document.referrer.startsWith("android-app://");

  const isExcludedPage = () => {
    return p.includes("admin") || p.includes("dashboard") || p.includes("communication") || p.includes("portal") || p.includes("login");
  };

  const addManifest = () => {
    if (document.querySelector('link[rel="manifest"]')) return;
    const link = document.createElement("link");
    link.rel = "manifest";
    link.href = "/manifest.webmanifest";
    document.head.appendChild(link);
  };

  const addPwaMetaTags = () => {
    let themeMeta = document.querySelector('meta[name="theme-color"]');
    if (!themeMeta) {
      themeMeta = document.createElement("meta");
      themeMeta.name = "theme-color";
      document.head.appendChild(themeMeta);
    }
    themeMeta.content = "#05060a";

    if (!document.querySelector('meta[name="mobile-web-app-capable"]')) {
      const mobCap = document.createElement("meta");
      mobCap.name = "mobile-web-app-capable";
      mobCap.content = "yes";
      document.head.appendChild(mobCap);
    }
    if (!document.querySelector('meta[name="apple-mobile-web-app-capable"]')) {
      const appleCap = document.createElement("meta");
      appleCap.name = "apple-mobile-web-app-capable";
      appleCap.content = "yes";
      document.head.appendChild(appleCap);
    }
    if (!document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')) {
      const appleBar = document.createElement("meta");
      appleBar.name = "apple-mobile-web-app-status-bar-style";
      appleBar.content = "black-translucent";
      document.head.appendChild(appleBar);
    }
  };

  const showBanner = () => {
    if (document.getElementById("kyk-install-banner")) return;
    const banner = document.createElement("div");
    banner.id = "kyk-install-banner";
    banner.className = "kyk-install-banner";
    banner.innerHTML = `
      <div class="kyk-install-banner-inner">
        <div class="kyk-install-banner-left">
          <div class="kyk-install-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
          </div>
          <div class="kyk-install-text">
            <strong>Install KYK Technologies</strong>
            <span>Add our app to your home screen for quick offline access and updates.</span>
          </div>
        </div>
        <div class="kyk-install-actions">
          <button class="kyk-install-btn primary kyk-install-trigger">Install</button>
          <button class="kyk-install-btn secondary kyk-install-dismiss" aria-label="Dismiss">✕</button>
        </div>
      </div>
    `;
    document.body.appendChild(banner);

    banner.querySelector(".kyk-install-trigger").addEventListener("click", async () => {
      if (!installPrompt) return;
      installPrompt.prompt();
      const choice = await installPrompt.userChoice;
      if (choice.outcome === "accepted") {
        localStorage.setItem(DISMISS_KEY, "1");
      }
      installPrompt = null;
      banner.remove();
    });
    banner.querySelector(".kyk-install-dismiss").addEventListener("click", () => {
      localStorage.setItem(DISMISS_KEY, "1");
      banner.remove();
    });
  };

  addManifest();
  addPwaMetaTags();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js?v=20261102-v32", { updateViaCache: "none" })
      .then((reg) => { if (reg) reg.update(); })
      .catch(() => {});
  }
  window.addEventListener("beforeinstallprompt", (event) => {
    if (isInstalled() || isExcludedPage() || localStorage.getItem(DISMISS_KEY) === "1") {
      return;
    }
    event.preventDefault();
    installPrompt = event;
    showBanner();
  });
  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    document.getElementById("kyk-install-banner")?.remove();
  });
})();
