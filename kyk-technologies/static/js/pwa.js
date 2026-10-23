(() => {
  const DISMISS_KEY = "kyk-install-dismissed";
  let installPrompt = null;

  const isInstalled = () => window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true || document.referrer.startsWith("android-app://");

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
    if (!document.querySelector('meta[name="apple-mobile-web-app-title"]')) {
      const appleTitle = document.createElement("meta");
      appleTitle.name = "apple-mobile-web-app-title";
      appleTitle.content = "KYK Technologies";
      document.head.appendChild(appleTitle);
    }
    if (!document.querySelector('link[rel="apple-touch-icon"]')) {
      const appleIcon = document.createElement("link");
      appleIcon.rel = "apple-touch-icon";
      appleIcon.href = "/kyk_logo.webp";
      document.head.appendChild(appleIcon);
    }
  };

  const addInstallStyles = () => {
    if (document.getElementById("kyk-install-styles")) return;
    const style = document.createElement("style");
    style.id = "kyk-install-styles";
    style.textContent = `
      .kyk-install-banner{position:fixed;z-index:9999;inset:auto 16px 16px;display:flex;align-items:center;gap:14px;max-width:540px;margin:auto;padding:14px 18px;border:1px solid rgba(232,98,44,.4);border-radius:14px;background:rgba(12,16,26,.95);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);box-shadow:0 18px 45px rgba(0,0,0,.65),0 0 24px rgba(232,98,44,.2);color:#fff;font:500 14px/1.4 'Inter',system-ui,sans-serif;animation:kykFadeUp .3s ease;}
      @keyframes kykFadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
      .kyk-install-banner strong{display:block;font-size:15px;color:#fff;font-family:'Space Grotesk',sans-serif}.kyk-install-banner p{margin:3px 0 0;color:rgba(255,255,255,.75);font-size:13px}.kyk-install-actions{display:flex;align-items:center;gap:8px;margin-left:auto;flex-shrink:0}.kyk-install-actions button{border:0;border-radius:8px;padding:9px 15px;cursor:pointer;font:600 13px/1 inherit;transition:transform .15s ease,opacity .15s ease}.kyk-install-button{background:#E8622C;color:#fff;box-shadow:0 4px 12px rgba(232,98,44,.35)}.kyk-install-button:active{transform:scale(.97)}.kyk-install-dismiss{background:rgba(255,255,255,.08);color:rgba(255,255,255,.75)}.kyk-install-banner[hidden]{display:none}@media(max-width:520px){.kyk-install-banner{inset:auto 12px 12px;align-items:stretch;flex-direction:column;padding:14px;gap:10px}.kyk-install-actions{width:100%;justify-content:flex-end}}
    `;
    document.head.appendChild(style);
  };

  const showBanner = () => {
    if (isInstalled() || localStorage.getItem(DISMISS_KEY) === "1" || document.getElementById("kyk-install-banner")) return;
    addInstallStyles();
    const banner = document.createElement("aside");
    banner.id = "kyk-install-banner";
    banner.className = "kyk-install-banner";
    banner.setAttribute("aria-label", "Install KYK Technologies");
    banner.innerHTML = `<div><strong>Use KYK like an app</strong><p>Install once for faster, smoother access on this device.</p></div><div class="kyk-install-actions"><button class="kyk-install-dismiss" type="button">Later</button><button class="kyk-install-button" type="button">Install App</button></div>`;
    document.body.appendChild(banner);
    banner.querySelector(".kyk-install-button").addEventListener("click", async () => {
      if (!installPrompt) {
        banner.querySelector("p").textContent = "Tap your browser menu and choose Add to Home Screen.";
        return;
      }
      installPrompt.prompt();
      await installPrompt.userChoice;
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
    navigator.serviceWorker.register("/service-worker.js", { updateViaCache: "none" })
      .then((reg) => { if (reg) reg.update(); })
      .catch(() => {});
  }
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    showBanner();
  });
  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    document.getElementById("kyk-install-banner")?.remove();
  });
  window.addEventListener("load", () => setTimeout(showBanner, 1200), { once: true });
})();
