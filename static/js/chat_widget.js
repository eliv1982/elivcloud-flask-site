(function () {
  "use strict";

  var CHAT_URL   = "/chat";
  var MAX_HIST   = 6;
  var history    = [];
  var isLoading  = false;

  var toggle  = document.getElementById("chat-widget-toggle");
  var panel   = document.getElementById("chat-widget-panel");
  var msgs    = document.getElementById("chat-widget-messages");
  var form    = document.getElementById("chat-widget-form");
  var input   = document.getElementById("chat-widget-input");
  var submit  = document.getElementById("chat-widget-submit");
  var closeBtn = document.getElementById("chat-widget-close");

  if (!toggle || !panel || !msgs || !form || !input || !submit) return;

  function openPanel() {
    panel.classList.remove("chat-widget-panel--hidden");
    toggle.setAttribute("aria-label", "Закрыть чат");
    toggle.innerHTML = "&times;";
    input.focus();
  }

  function closePanel() {
    panel.classList.add("chat-widget-panel--hidden");
    toggle.setAttribute("aria-label", "Открыть чат");
    toggle.innerHTML = "&#x1F4AC;";
  }

  toggle.addEventListener("click", function () {
    if (panel.classList.contains("chat-widget-panel--hidden")) {
      openPanel();
    } else {
      closePanel();
    }
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", closePanel);
  }

  function cleanAssistantText(text) {
    if (!text) return "";
    return text
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/^#{1,6}\s+/gm, "")
      .trim();
  }

  function addMsg(text, cls) {
    var d = document.createElement("div");
    d.className = "chat-message " + cls;
    d.textContent = cls === "chat-message-assistant" ? cleanAssistantText(text) : text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  function addLoading() {
    var d = document.createElement("div");
    d.className = "chat-message chat-message-loading";
    d.innerHTML = "Печатаю... <span class='chat-dots'><span></span><span></span><span></span></span>";
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  function setBusy(val) {
    isLoading = val;
    submit.disabled = val;
    input.disabled = val;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text || isLoading) return;

    input.value = "";
    addMsg(text, "chat-message-user");

    var payload = {
      message: text,
      history: history.slice(-MAX_HIST)
    };

    setBusy(true);
    var loader = addLoading();

    fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
    .then(function (res) {
      loader.remove();
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (err) {
          addMsg(err.error || "Ошибка сервера. Попробуйте позже.", "chat-message-error");
          setBusy(false);
        });
      }
      return res.json().then(function (data) {
        var answer = (data.answer || "").trim();
        if (!answer) {
          addMsg("Пустой ответ. Попробуйте переформулировать.", "chat-message-error");
        } else {
          addMsg(answer, "chat-message-assistant");
          history.push({ role: "user",      content: text   });
          history.push({ role: "assistant", content: answer });
          if (history.length > MAX_HIST * 2) {
            history = history.slice(-MAX_HIST * 2);
          }
        }
        setBusy(false);
        input.focus();
      });
    })
    .catch(function () {
      loader.remove();
      addMsg("Нет соединения с сервером.", "chat-message-error");
      setBusy(false);
      input.focus();
    });
  });
})();
