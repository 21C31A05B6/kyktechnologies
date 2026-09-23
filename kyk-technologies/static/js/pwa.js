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

  const addInstallStyles = () => {
    if (document.getElementById("kyk-install-styles")) return;
    const style = document.createElement("style");
    style.id = "kyk-install-styles";
    style.textContent = `
      .kyk-install-banner{position:fixed;z-index:1000;inset:auto 16px 16px;display:flex;align-items:center;gap:14px;max-width:620px;margin:auto;padding:14px 16px;border:1px solid rgba(18,59,53,.18);border-radius:12px;background:#fff;box-shadow:0 12px 32px rgba(18,59,53,.18);color:#123b35;font:500 14px/1.35 system-ui,sans-serif}
      .kyk-install-banner strong{display:block;font-size:15px}.kyk-install-banner p{margin:3px 0 0;color:#50645e}.kyk-install-actions{display:flex;align-items:center;gap:8px;margin-left:auto;flex-shrink:0}.kyk-install-actions button{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;font:inherit}.kyk-install-button{background:#d8874d;color:#fff}.kyk-install-dismiss{background:transparent;color:#50645e}.kyk-install-banner[hidden]{display:none}@media(max-width:520px){.kyk-install-banner{inset:auto 10px 10px;align-items:flex-start;padding:12px}.kyk-install-actions{flex-direction:column-reverse;gap:2px}.kyk-install-actions button{padding:7px 10px}}
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
    banner.innerHTML = `<div><strong>Use KYK like an app</strong><p>Install once for faster access on this device.</p></div><div class="kyk-install-actions"><button class="kyk-install-dismiss" type="button">Later</button><button class="kyk-install-button" type="button">Install</button></div>`;
    document.body.appendChild(banner);
    banner.querySelector(".kyk-install-button").addEventListener("click", async () => {
      if (!installPrompt) {
        banner.querySelector("p").textContent = "Use your browser menu and choose Add to Home Screen.";
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
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/service-worker.js").catch(() => {});
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
