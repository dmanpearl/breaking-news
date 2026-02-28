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

  function resetTimers() {
    clearTimeout(warnTimer);
    clearInterval(countdownInterval);
    overlay.classList.remove("visible");
    warnTimer = setTimeout(showWarning, warnAfterMs);
  }

  function showWarning() {
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

  stayBtn.addEventListener("click", resetTimers);
  logoutBtn.addEventListener("click", () => { window.location.href = logoutUrl; });

  ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach((evt) => {
    document.addEventListener(evt, resetTimers, { passive: true });
  });

  resetTimers();
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
