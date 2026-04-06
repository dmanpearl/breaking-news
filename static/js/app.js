/* Breaking News – app.js */

// ── Inactivity timer ──────────────────────────────────────────────────────────
(function () {
  const overlay = document.getElementById("inactivity-overlay");
  if (!overlay) return;

  const countdownEl = document.getElementById("inactivity-countdown");
  const stayBtn = document.getElementById("inactivity-stay");
  const logoutBtn = document.getElementById("inactivity-logout");

  const warnAfterMs = parseInt(overlay.dataset.warnAfter, 10);
  const warningMs = parseInt(overlay.dataset.warningDuration, 10);
  const logoutUrl = overlay.dataset.logoutUrl;

  let warnTimer, countdownInterval;
  let countdownValue;
  let warningVisible = false;

  function resetTimers() {
    // Do NOT reset if the warning dialog is already showing —
    // any user activity at that point should only affect Stay/Logout buttons.
    if (warningVisible) return;

    clearTimeout(warnTimer);
    warnTimer = setTimeout(showWarning, warnAfterMs);
  }

  function showWarning() {
    warningVisible = true;
    countdownValue = Math.ceil(warningMs / 1000);
    countdownEl.textContent = countdownValue;
    overlay.classList.add("visible");

    countdownInterval = setInterval(() => {
      countdownValue -= 1;
      countdownEl.textContent = countdownValue;
      if (countdownValue <= 0) {
        clearInterval(countdownInterval);
        window.location.href = logoutUrl;
      }
    }, 1000);
  }

  function dismissWarning() {
    warningVisible = false;
    clearInterval(countdownInterval);
    overlay.classList.remove("visible");
    // Restart the idle watch from now
    clearTimeout(warnTimer);
    warnTimer = setTimeout(showWarning, warnAfterMs);
  }

  stayBtn.addEventListener("click", dismissWarning);
  logoutBtn.addEventListener("click", () => {
    window.location.href = logoutUrl;
  });

  ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach((evt) => {
    document.addEventListener(evt, resetTimers, { passive: true });
  });

  // Kick off the initial idle timer
  warnTimer = setTimeout(showWarning, warnAfterMs);
})();

// ── Connection status refresh ─────────────────────────────────────────────────
(function () {
  const panel = document.getElementById("conn-status-panel");
  if (!panel) return;

  async function refreshStatus() {
    try {
      const res = await fetch("/connections/status/");
      const data = await res.json();
      const chips = panel.querySelectorAll(".conn-chip");
      chips.forEach((chip) => {
        const id = chip.dataset.connId;
        const conn = data.connections.find((c) => String(c.id) === id);
        if (!conn) return;
        const dot = chip.querySelector(".dot");
        dot.className = "dot " + (conn.enabled ? conn.status : "");
        chip.classList.toggle("disabled", !conn.enabled);
        chip.title = conn.status_message || conn.status;
      });
    } catch (_) {}
  }

  setInterval(refreshStatus, 30000);
})();

// ── Password visibility toggle ───────────────────────────────────────────────
// Automatically adds an eye/eye-off button to every password input on the page.
(function () {
  // SVG icons — pure line art, no fill
  var EYE_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.964-7.178z"/><circle cx="12" cy="12" r="3.75"/></svg>';
  var EYE_SHUT = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88"/></svg>';

  function wrapInput(input) {
    // Avoid double-wrapping
    if (input.parentElement && input.parentElement.classList.contains('pw-wrap')) return;

    var wrap = document.createElement('div');
    wrap.className = 'pw-wrap';

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw-eye';
    btn.setAttribute('aria-label', 'Show password');
    btn.innerHTML = EYE_OPEN;

    // Insert wrapper before input, move input inside
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(btn);

    btn.addEventListener('click', function () {
      var showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      btn.innerHTML = showing ? EYE_OPEN : EYE_SHUT;
      btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    });
  }

  function init() {
    document.querySelectorAll('input[type="password"]').forEach(wrapInput);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// ── Recent feature banner ─────────────────────────────────────────────────────
(function () {
  var featureBanner = document.getElementById("bn-feature-banner");
  if (!featureBanner) return;

  var featureId  = featureBanner.dataset.featureId;
  var dismissUrl = featureBanner.dataset.dismissUrl;
  var csrf       = featureBanner.dataset.csrf;

  function dismissBanner() {
    featureBanner.style.display = "none";
    return fetch(dismissUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      credentials: "same-origin",
      body: JSON.stringify({ id: featureId }),
    });
  }

  // Close button — dismiss and stay on page
  var bannerClose = featureBanner.querySelector(".bn-fb-close");
  if (bannerClose) {
    bannerClose.onclick = function (e) {
      e.stopPropagation();
      dismissBanner().catch(function () {});
    };
  }

  // "See all features" link — dismiss then navigate
  var bannerLink = featureBanner.querySelector(".bn-fb-link");
  if (bannerLink) {
    bannerLink.onclick = function (e) {
      e.preventDefault();
      var href = bannerLink.href;
      dismissBanner()
        .catch(function () {})
        .finally(function () { window.location.href = href; });
    };
  }

  // Tap description to expand full text; tap again to collapse.
  // Clicks on the actions wrapper (link + close) are ignored.
  var descEl    = document.getElementById("bn-fb-desc-text");
  var fbInner   = featureBanner.querySelector(".bn-fb-inner");
  var fbActions = featureBanner.querySelector(".bn-fb-actions");
  if (descEl && fbInner) {
    fbInner.style.cursor = "pointer";
    fbInner.addEventListener("click", function (e) {
      if (fbActions && fbActions.contains(e.target)) return;
      var expanded = descEl.classList.toggle("bn-fb-desc-expanded");
      fbInner.title = expanded ? "Tap to collapse" : "";
    });
  }
})();
