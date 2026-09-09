// OpenGrammarly Background Service Worker (Manifest V3)
// Bypasses page CSP and Mixed Content security restrictions on HTTPS pages (like WhatsApp Web).

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "check") {
    const text = request.text || "";
    const lang = request.language || "en-US";

    // 1. Try local proxy on 8082 (has smart enhanced rules)
    fetch("http://127.0.0.1:8082/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, language: lang })
    })
      .then((res) => res.json())
      .then((data) => {
        sendResponse({ success: true, matches: data.matches || [] });
      })
      .catch((err) => {
        // 2. Fallback directly to LanguageTool engine on 8081
        const params = new URLSearchParams({ text: text, language: lang });
        fetch("http://localhost:8081/v2/check", {
          method: "POST",
          body: params
        })
          .then((res) => res.json())
          .then((data) => {
            sendResponse({ success: true, matches: data.matches || [] });
          })
          .catch((err2) => {
            sendResponse({ success: false, error: err2.toString(), matches: [] });
          });
      });

    return true; // Keep channel open for async response
  }

  if (request.action === "translate") {
    const text = request.text || "";
    const fromCode = request.from || "auto";
    const toCode = request.to || "es";

    fetch("http://127.0.0.1:8082/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, from: fromCode, to: toCode })
    })
      .then((res) => res.json())
      .then((data) => {
        sendResponse({ success: true, ...data });
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.toString(), translated: text });
      });

    return true;
  }

  if (request.action === "autofix") {
    const text = request.text || "";
    const lang = request.language || "auto";

    fetch("http://127.0.0.1:8082/api/autofix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, language: lang })
    })
      .then((res) => res.json())
      .then((data) => {
        sendResponse({ success: true, fixed: data.fixed, count: data.count });
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.toString() });
      });

    return true;
  }
});
