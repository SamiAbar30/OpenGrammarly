// OpenGrammarly Browser Extension Content Script
(() => {
  // Clean up any stale UI elements from previous extension loads/reloads
  document.querySelectorAll(".gl-badge, .gl-popover").forEach((node) => node.remove());

  let activeElement = null;
  let currentMatches = [];
  let checkTimeout = null;
  let isFixing = false; // Flag to prevent synthetic events from creating recursive feedback loops

  // Create badge element
  const badge = document.createElement("div");
  badge.className = "gl-badge";
  badge.innerHTML = "✓";
  badge.style.display = "none";
  document.body.appendChild(badge);

  // Create floating popover
  const popover = document.createElement("div");
  popover.className = "gl-popover";
  popover.style.display = "none";
  document.body.appendChild(popover);

  // CRITICAL: Prevent mousedown & pointerdown from blurring the active input/editor
  // When e.preventDefault() is called, focus and text selection remain active in WhatsApp Web / Slack / etc.
  [badge, popover].forEach((node) => {
    node.addEventListener("mousedown", (e) => e.preventDefault(), true);
    node.addEventListener("pointerdown", (e) => e.preventDefault(), true);
  });

  function findInputElement(target) {
    if (!target) return null;
    if (
      target.tagName === "TEXTAREA" ||
      (target.tagName === "INPUT" && ["text", "search", "email", ""].includes(target.type))
    ) {
      return target;
    }
    const ce = target.closest('[contenteditable="true"]') || target.closest('[role="textbox"]');
    if (ce) return ce;
    if (target.isContentEditable) return target;
    return null;
  }

  function getResolvedTarget() {
    if (activeElement && document.contains(activeElement)) {
      return activeElement;
    }
    const current = findInputElement(document.activeElement);
    if (current) {
      activeElement = current;
      return activeElement;
    }
    // Search common chat editors on page (WhatsApp Web compose bar, Telegram, Slack, etc.)
    const fallback =
      document.querySelector('footer div[contenteditable="true"][role="textbox"]') ||
      document.querySelector('div[contenteditable="true"][role="textbox"]') ||
      document.querySelector('div[contenteditable="true"][data-tab="10"]') ||
      document.querySelector('div[contenteditable="true"]') ||
      document.querySelector('textarea:focus') ||
      document.querySelector('textarea');
    if (fallback) {
      activeElement = fallback;
      return activeElement;
    }
    return null;
  }

  function getElementText(el) {
    if (!el) return "";
    let val = el.isContentEditable ? (el.innerText || el.textContent || "") : (el.value || "");
    // Strip zero-width spaces/BOM and trailing single newline automatically added by browsers
    return val.replace(/[\uFEFF\u200B]/g, "").replace(/\r?\n$/, "");
  }

  // Robust string replacer for single fixes: replaces m.wrong with replacement without offset errors
  function computeSingleFixText(currentText, m, replacement) {
    const wrongLen = m.length;
    // 1. Check if m.wrong or candidate at m.offset matches
    if (m.offset >= 0 && m.offset + wrongLen <= currentText.length) {
      const candidate = currentText.substring(m.offset, m.offset + wrongLen);
      if (!m.wrong || candidate.toLowerCase() === m.wrong.toLowerCase()) {
        return currentText.substring(0, m.offset) + replacement + currentText.substring(m.offset + wrongLen);
      }
    }
    // 2. If offsets shifted, search for m.wrong in currentText
    if (m.wrong) {
      const idx = currentText.indexOf(m.wrong);
      if (idx !== -1) {
        return currentText.substring(0, idx) + replacement + currentText.substring(idx + m.wrong.length);
      }
    }
    // 3. Fallback to offset replacement
    return currentText.substring(0, m.offset) + replacement + currentText.substring(m.offset + wrongLen);
  }

  // Bulletproof text replacer for any editor (WhatsApp Web Lexical, Slack, generic contenteditable, textarea)
  function replaceTextInElement(el, newText, callback) {
    if (!el) return;
    const cleanText = newText.replace(/\r\n/g, "\n");
    isFixing = true;

    // Case 1: Standard input / textarea (React/Vue prototype setter)
    if (!el.isContentEditable) {
      const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
      if (setter) {
        setter.call(el, cleanText);
      } else {
        el.value = cleanText;
      }
      try {
        el.setSelectionRange(cleanText.length, cleanText.length);
      } catch (e) {}

      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      setTimeout(() => {
        isFixing = false;
        if (callback) callback();
      }, 100);
      return;
    }

    // Case 2: ContentEditable (WhatsApp Web Lexical, Slack, Notion, Gmail, etc.)
    el.focus();

    // 1. Collect innermost text nodes within the editable element
    const textNodes = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null, false);
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeValue !== null) {
        textNodes.push(node);
      }
    }

    // 2. Target the exact text span selection range from start to end of text nodes
    const sel = window.getSelection();
    if (sel) {
      sel.removeAllRanges();
      const range = document.createRange();
      if (textNodes.length > 0) {
        range.setStart(textNodes[0], 0);
        const lastNode = textNodes[textNodes.length - 1];
        range.setEnd(lastNode, lastNode.nodeValue ? lastNode.nodeValue.length : 0);
      } else {
        range.selectNodeContents(el);
      }
      sel.addRange(range);
    }

    // 3. Atomically replace the text selection in one operation (avoids Lexical container deletion rejection)
    let inserted = false;
    try {
      inserted = document.execCommand("insertText", false, cleanText);
    } catch (e) {
      inserted = false;
    }

    // 4. Post-replacement verification: if editor did not sync or duplicated, directly reconcile text node
    let currentVal = getElementText(el);
    if (currentVal.trim() !== cleanText.trim()) {
      if (textNodes.length > 0) {
        textNodes[0].nodeValue = cleanText;
        for (let i = 1; i < textNodes.length; i++) {
          textNodes[i].nodeValue = "";
        }
      } else {
        const lexicalSpan = el.querySelector('[data-lexical-text="true"]');
        if (lexicalSpan) {
          lexicalSpan.textContent = cleanText;
        } else {
          el.innerText = cleanText;
        }
      }
    }

    // 6. Ensure cursor is positioned at the end of the new text
    if (sel) {
      try {
        const finalRange = document.createRange();
        finalRange.selectNodeContents(el);
        finalRange.collapse(false);
        sel.removeAllRanges();
        sel.addRange(finalRange);
      } catch (e) {}
    }

    // 7. Fire standard input & change events for WhatsApp / React form state
    // CRITICAL: NEVER dispatch new InputEvent("input", { inputType: "insertText" })
    // because that causes Meta Lexical to insert the text a second time!
    try {
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } catch (e) {}

    setTimeout(() => {
      isFixing = false;
      if (callback) callback();
    }, 200);
  }

  function updateBadgePosition() {
    if (!activeElement || !document.contains(activeElement)) {
      badge.style.display = "none";
      popover.style.display = "none";
      return;
    }

    const rect = activeElement.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 15 || rect.bottom < 0 || rect.top > window.innerHeight) {
      badge.style.display = "none";
      return;
    }

    // WhatsApp Web and chat apps have send/mic buttons on the right side of the footer input
    const isChatApp =
      window.location.hostname.includes("whatsapp") ||
      window.location.hostname.includes("telegram") ||
      window.location.hostname.includes("slack");

    const rightOffset = isChatApp ? 65 : 12;
    const badgeX = Math.max(10, Math.min(window.innerWidth - 38, rect.right - rightOffset));
    const badgeY = Math.max(10, Math.min(window.innerHeight - 38, rect.bottom - 34));

    badge.style.left = `${badgeX}px`;
    badge.style.top = `${badgeY}px`;
    badge.style.display = "flex";

    if (popover.style.display === "flex") {
      repositionPopover(rect);
    }
  }

  function repositionPopover(rect) {
    const popWidth = 340;
    let popLeft = rect.right - popWidth - 10;
    if (popLeft < 12) popLeft = 12;
    if (popLeft + popWidth > window.innerWidth - 12) {
      popLeft = window.innerWidth - popWidth - 12;
    }
    popover.style.left = `${popLeft}px`;

    // Position ABOVE the input field when near bottom (like WhatsApp Web chat bar)
    if (rect.bottom > window.innerHeight / 2) {
      popover.style.bottom = `${Math.max(12, window.innerHeight - rect.top + 10)}px`;
      popover.style.top = "auto";
    } else {
      popover.style.top = `${Math.max(12, rect.bottom + 10)}px`;
      popover.style.bottom = "auto";
    }
  }

  // Client-side fallback smart rule enhancer
  function applySmartEnhancements(text, matches) {
    const enhanced = [...matches];
    const existingIds = new Set(matches.map((m) => (m.rule ? m.rule.id : m.id)));

    // 1. Missing comma after greeting or missing subject: "Hi am Sami" -> "Hi, I'm Sami"
    if (!existingIds.has("GREETING_IM_NAME") && !existingIds.has("GREETING_COMMA")) {
      const mHiAm = text.match(/\b(Hi|Hello|Hey)\s+am\s+([A-Za-z\']+)/i);
      if (mHiAm) {
        const g = mHiAm[1].charAt(0).toUpperCase() + mHiAm[1].slice(1).toLowerCase();
        enhanced.push({
          message: `Did you mean "${g}, I'm ${mHiAm[2]}"?`,
          shortMessage: "Missing subject",
          replacements: [{ value: `${g}, I'm ${mHiAm[2]}` }, { value: `${g}, I am ${mHiAm[2]}` }],
          offset: mHiAm.index,
          length: mHiAm[0].length,
          rule: { id: "GREETING_IM_NAME", issueType: "grammar" },
        });
      } else {
        const mGreeting = text.match(/\b(Hello|Hi|Hey|Dear)\s+([A-Za-z\']+)/i);
        if (mGreeting && !text.substring(mGreeting.index).startsWith(mGreeting[1] + ",")) {
          const g = mGreeting[1].charAt(0).toUpperCase() + mGreeting[1].slice(1).toLowerCase();
          enhanced.push({
            message: `Add a comma after the greeting "${g}".`,
            shortMessage: "Missing comma",
            replacements: [{ value: `${g}, ${mGreeting[2]}` }],
            offset: mGreeting.index,
            length: mGreeting[0].length,
            rule: { id: "GREETING_COMMA", issueType: "grammar" },
          });
        }
      }
    }

    // 2. Question phrasing: "what to do" / "so what to do"
    if (!existingIds.has("QUESTION_PHRASING")) {
      const mQ = text.match(/\b(so\s+)?(what to do)\b/i);
      if (mQ) {
        enhanced.push({
          message: "Consider phrasing this as a question for clarity.",
          shortMessage: "Question phrasing",
          replacements: [{ value: "what should I do?" }, { value: "what to do?" }],
          offset: mQ.index,
          length: mQ[0].length,
          rule: { id: "QUESTION_PHRASING", issueType: "style" },
        });
      }
    }

    // 3. Informal/Slang typo: "homo" -> "homie" / "bro" / "man"
    if (!existingIds.has("WORD_CHOICE")) {
      const mSlang = text.match(/\bhomo\b/i);
      if (mSlang) {
        enhanced.push({
          message: 'Informal word choice or typo. Did you mean "homie" or "bro"?',
          shortMessage: "Word choice",
          replacements: [{ value: "homie" }, { value: "bro" }, { value: "man" }],
          offset: mSlang.index,
          length: 4,
          rule: { id: "WORD_CHOICE", issueType: "style" },
        });
      }
    }

    // Filter out overlapping matches, preferring longer/more comprehensive fixes
    // Sort by start asc, then longer length first
    enhanced.sort((a, b) => {
      if (a.offset !== b.offset) return a.offset - b.offset;
      return b.length - a.length;
    });

    const filtered = [];
    let lastEnd = -1;
    for (const m of enhanced) {
      if (m.offset >= lastEnd) {
        filtered.push(m);
        lastEnd = m.offset + m.length;
      }
    }

    // Sort descending by offset for safe right-to-left processing
    filtered.sort((a, b) => b.offset - a.offset);
    return filtered;
  }

  function checkActiveText() {
    const targetEl = getResolvedTarget();
    if (!targetEl) return;
    const text = getElementText(targetEl);
    if (!text || text.trim().length < 3) {
      badge.className = "gl-badge";
      badge.innerHTML = "✓";
      currentMatches = [];
      if (popover.style.display === "flex") popover.style.display = "none";
      return;
    }

    // Send check request to background service worker (avoids page CSP & Mixed Content blocks)
    chrome.runtime.sendMessage(
      { action: "check", text: text, language: "auto" },
      (response) => {
        if (chrome.runtime.lastError || !response) {
          currentMatches = applySmartEnhancements(text, []);
        } else {
          const rawMatches = response.matches || [];
          currentMatches = applySmartEnhancements(text, rawMatches);
        }

        if (currentMatches.length > 0) {
          badge.className = "gl-badge has-errors";
          badge.innerHTML = currentMatches.length;
        } else {
          badge.className = "gl-badge";
          badge.innerHTML = "✓";
        }

        if (popover.style.display === "flex") {
          renderPopover();
        }
      }
    );
  }

  function autoFixAll() {
    if (isFixing) return;
    const el = getResolvedTarget();
    if (!el || currentMatches.length === 0) return;
    isFixing = true;
    popover.style.display = "none";

    const originalText = getElementText(el);

    // Call background service worker for server-side smart autofix
    chrome.runtime.sendMessage(
      { action: "autofix", text: originalText, language: "auto" },
      (response) => {
        let fixedText = "";
        if (response && response.success && response.fixed) {
          fixedText = response.fixed;
        } else {
          // Client-side fallback computation
          const sorted = [...currentMatches].sort((a, b) => b.offset - a.offset);
          let chars = originalText.split("");
          let lastEnd = originalText.length + 1;
          for (const m of sorted) {
            const start = m.offset;
            const end = start + m.length;
            if (end <= lastEnd && m.replacements && m.replacements[0]) {
              chars.splice(start, m.length, ...m.replacements[0].value.split(""));
              lastEnd = start;
            }
          }
          fixedText = chars.join("");
        }

        console.log("[OpenGrammarly] autoFixAll replacing with:", fixedText);
        replaceTextInElement(el, fixedText, () => {
          checkActiveText();
        });
      }
    );
  }

  function fixSingleMatch(idx) {
    if (isFixing) return;
    const el = getResolvedTarget();
    if (!el) return;

    const m = currentMatches[idx];
    if (!m || !m.replacements || !m.replacements[0]) return;
    isFixing = true;
    popover.style.display = "none";

    const rep = m.replacements[0].value;
    const currentText = getElementText(el);
    const targetText = computeSingleFixText(currentText, m, rep);

    console.log(`[OpenGrammarly] Single fix #${idx}: replacing with: "${targetText}"`);

    replaceTextInElement(el, targetText, () => {
      checkActiveText();
    });
  }

  function renderPopover() {
    const el = getResolvedTarget();
    if (!el) return;
    const rect = el.getBoundingClientRect();
    repositionPopover(rect);

    function renderTranslateSection() {
      return `
        <div class="gl-translate-section">
          <div class="gl-translate-header">
            <span class="gl-translate-title">🌐 Translate Text</span>
            <span class="gl-translate-badge">100% Offline</span>
          </div>
          <div class="gl-translate-chips">
            <button class="gl-chip-lang" data-lang="es">🇪🇸 Spanish</button>
            <button class="gl-chip-lang" data-lang="fr">🇫🇷 French</button>
            <button class="gl-chip-lang" data-lang="de">🇩🇪 German</button>
            <button class="gl-chip-lang" data-lang="it">🇮🇹 Italian</button>
            <button class="gl-chip-lang" data-lang="pt">🇵🇹 Portuguese</button>
            <button class="gl-chip-lang" data-lang="ar">🇸🇦 Arabic</button>
            <button class="gl-chip-lang" data-lang="en">🇬🇧 English</button>
          </div>
        </div>
      `;
    }

    if (currentMatches.length === 0) {
      popover.innerHTML = `
        <div class="gl-popover-header">
          <span class="gl-title">✨ All clear</span>
        </div>
        <div style="font-size: 12px; color: #94a3b8; margin-bottom: 6px;">No spelling or grammar errors detected.</div>
        ${renderTranslateSection()}
      `;
    } else {
      const text = getElementText(el);
      let itemsHtml = currentMatches
        .slice(0, 6)
        .map((m, idx) => {
          const wrong = text.substring(m.offset, m.offset + m.length);
          m.wrong = wrong; // Store wrong text on match object for offset-drift safety
          const fix = m.replacements && m.replacements[0] ? m.replacements[0].value : "";
          return `
          <div class="gl-card-item">
            <div class="gl-item-diff">
              <span class="gl-word-wrong">"${wrong}"</span>
              <span class="gl-arrow">→</span>
              <span class="gl-word-fix">"${fix || "Remove"}"</span>
            </div>
            <div class="gl-item-msg">${m.message}</div>
            ${fix ? `<button class="gl-btn-fix-single" data-idx="${idx}">Fix with "${fix}"</button>` : ""}
          </div>
        `;
        })
        .join("");

      popover.innerHTML = `
        <div class="gl-popover-header">
          <span class="gl-title">✍️ ${currentMatches.length} Suggestions</span>
          <button class="gl-btn-fix-all" id="gl-btn-fix-all">⚡ Fix All</button>
        </div>
        ${itemsHtml}
        ${renderTranslateSection()}
      `;
    }

    popover.style.display = "flex";
  }

  function translateAndReplace(targetLang, btnEl) {
    if (isFixing) return;
    const el = getResolvedTarget();
    if (!el) return;
    const currentText = getElementText(el);
    if (!currentText || !currentText.trim()) return;
    isFixing = true;

    if (btnEl) {
      btnEl.classList.add("gl-translating");
      btnEl.innerText = "Translating...";
    }

    chrome.runtime.sendMessage(
      { action: "translate", text: currentText, from: "auto", to: targetLang },
      (response) => {
        if (response && response.translated) {
          console.log(`[OpenGrammarly] Translated to ${targetLang}:`, response.translated);
          popover.style.display = "none";
          replaceTextInElement(el, response.translated, () => {
            checkActiveText();
          });
        } else {
          isFixing = false;
          if (btnEl) {
            btnEl.classList.remove("gl-translating");
            btnEl.innerText = "Error";
          }
        }
      }
    );
  }

  // Delegated click handler on popover - instant response with zero race conditions
  popover.addEventListener("click", (e) => {
    e.stopPropagation();
    if (isFixing) return;

    const fixAllBtn = e.target.closest("#gl-btn-fix-all");
    if (fixAllBtn) {
      autoFixAll();
      return;
    }

    const fixSingleBtn = e.target.closest(".gl-btn-fix-single");
    if (fixSingleBtn) {
      const idx = parseInt(fixSingleBtn.getAttribute("data-idx"), 10);
      fixSingleMatch(idx);
      return;
    }

    const translateChip = e.target.closest(".gl-chip-lang");
    if (translateChip) {
      const targetLang = translateChip.getAttribute("data-lang");
      translateAndReplace(targetLang, translateChip);
      return;
    }
  });

  badge.addEventListener("click", (e) => {
    e.stopPropagation();
    if (popover.style.display === "flex") {
      popover.style.display = "none";
    } else {
      renderPopover();
    }
  });

  document.addEventListener("click", (e) => {
    if (!popover.contains(e.target) && !badge.contains(e.target)) {
      popover.style.display = "none";
    }
  });

  const triggerFastCheck = (el) => {
    if (isFixing) return;
    activeElement = el;
    updateBadgePosition();
    clearTimeout(checkTimeout);
    checkTimeout = setTimeout(() => {
      if (isFixing) return;
      checkActiveText();
    }, 180);
  };

  // Capture typing events across all inputs and contenteditable frameworks (WhatsApp, Slack, Notion)
  ["focusin", "input", "keyup", "paste", "mouseup"].forEach((evtType) => {
    document.addEventListener(
      evtType,
      (e) => {
        if (isFixing) return; // Prevent synthetic events triggered by our fixes from re-triggering check
        const el = findInputElement(e.target);
        if (el) {
          triggerFastCheck(el);
        }
      },
      true
    );
  });

  window.addEventListener("scroll", updateBadgePosition, true);
  window.addEventListener("resize", updateBadgePosition);
})();
