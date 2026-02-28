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
