(() => {
  const $ = (s) => document.querySelector(s);
  const messagesEl = $("#messages");
  const welcomeEl = $("#welcome");
  const input = $("#input");
  const urlInput = $("#urlInput");
  const sendBtn = $("#sendBtn");
  const statusBar = $("#statusBar");
  const maxStepsEl = $("#maxSteps");
  const stepsVal = $("#stepsVal");
  const settingsSheet = $("#settingsSheet");
  const overlay = $("#overlay");

  let busy = false;
  let sessionId = null;

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  }
  input.addEventListener("input", autoResize);

  maxStepsEl.addEventListener("input", () => {
    stepsVal.textContent = maxStepsEl.value;
    statusBar.textContent = `Ready · max ${maxStepsEl.value} steps`;
  });

  function showSettings(show) {
    settingsSheet.classList.toggle("hidden", !show);
    overlay.classList.toggle("hidden", !show);
  }
  $("#menuBtn").onclick = () => showSettings(true);
  $("#closeSettings").onclick = () => showSettings(false);
  overlay.onclick = () => showSettings(false);

  document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      if (t.dataset.tab === "settings") showSettings(true);
    };
  });

  $("#newChatBtn").onclick = () => {
    messagesEl.innerHTML = "";
    welcomeEl.style.display = "";
    sessionId = null;
    statusBar.textContent = `Ready · max ${maxStepsEl.value} steps`;
  };

  document.querySelectorAll(".chip").forEach((c) => {
    c.onclick = () => {
      input.value = c.dataset.prompt || "";
      if (c.dataset.url) urlInput.value = c.dataset.url;
      autoResize();
      input.focus();
    };
  });

  function addMessage(role, html, meta) {
    welcomeEl.style.display = "none";
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.innerHTML = `<div class="bubble">${html}</div>${meta ? `<div class="meta">${meta}</div>` : ""}`;
    messagesEl.appendChild(div);
    messagesEl.parentElement.scrollTop = messagesEl.parentElement.scrollHeight;
    return div;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function send() {
    const text = input.value.trim();
    if (!text || busy) return;
    busy = true;
    sendBtn.disabled = true;
    const url = urlInput.value.trim() || null;
    const maxSteps = parseInt(maxStepsEl.value, 10) || 80;

    addMessage("user", escapeHtml(text));
    input.value = "";
    autoResize();
    statusBar.textContent = "Agent running…";

    const thinking = addMessage("bot", "Working on it…");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          url,
          max_steps: maxSteps,
          session_id: sessionId,
          headless: $("#headless").checked,
        }),
      });
      const data = await res.json();
      if (data.session_id) sessionId = data.session_id;

      thinking.remove();
      if (data.error) {
        addMessage("bot", escapeHtml(data.error));
        statusBar.textContent = "Error";
      } else {
        const r = data.result || data.reply || {};
        const badge = r.success
          ? '<span class="badge ok">SUCCESS</span>'
          : '<span class="badge fail">FAILED</span>';
        let body = badge + escapeHtml(r.message || data.reply?.content || "Done.");
        if (r.data) {
          body += `<div class="data-block">${escapeHtml(JSON.stringify(r.data, null, 2))}</div>`;
        }
        const meta = [
          r.steps != null ? `${r.steps} steps` : null,
          r.duration_sec != null ? `${r.duration_sec}s` : null,
        ].filter(Boolean).join(" · ");
        addMessage("bot", body, meta);
        statusBar.textContent = r.success ? "Done ✓" : "Finished with errors";
      }
    } catch (e) {
      thinking.remove();
      addMessage("bot", "Network error: " + escapeHtml(e.message));
      statusBar.textContent = "Error";
    } finally {
      busy = false;
      sendBtn.disabled = false;
    }
  }

  sendBtn.onclick = send;
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  // Health check
  fetch("/api/health")
    .then((r) => r.json())
    .then((h) => {
      if (!h.has_api_key) {
        statusBar.textContent = "⚠ NVIDIA_API_KEY not set on server";
      }
    })
    .catch(() => {});
})();
