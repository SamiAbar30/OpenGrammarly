<div align="center">

# ✨ OpenGrammarly

### 100% Private, Offline Grammar Checker & DeepL-Style Neural Translator for macOS

[![Platform: macOS](https://img.shields.io/badge/platform-macOS%20(Apple%20Silicon%20%26%20Intel)-000000.svg?logo=apple&style=flat-square)](#)
[![100% Offline](https://img.shields.io/badge/privacy-100%25%20Offline%20%26%20Local-10b981.svg?style=flat-square)](#)
[![Zero Telemetry](https://img.shields.io/badge/telemetry-Zero%20Data%20Collected-blue.svg?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-purple.svg?style=flat-square)](LICENSE)

**OpenGrammarly** is an all-in-one, zero-config desktop application and browser extension that gives you the best of **Grammarly + DeepL** running completely locally on your Mac. No accounts, no cloud API keys, no subscriptions, and zero telemetry.

</div>

---

## ⚡ Fast Access & 1-Click Installation (Zero Config)

### Option 1: 1-Click Drag-and-Drop Installer (Recommended)
1. Download **`OpenGrammarly.dmg`** from this repository (or from [Releases](https://github.com/SamiAbar30/OpenGrammarly/releases)).
2. Double-click **`OpenGrammarly.dmg`**.
3. Drag **OpenGrammarly** into your **Applications** folder.
4. Launch OpenGrammarly!

### Option 2: 1-Line Automated Terminal Setup
Open your macOS Terminal and run:

```bash
curl -fsSL https://raw.githubusercontent.com/SamiAbar30/OpenGrammarly/main/install.sh | bash
```

Or clone the repo and run:

```bash
git clone https://github.com/SamiAbar30/OpenGrammarly.git
cd OpenGrammarly
./install.sh
```

---

## 🌟 Key Features

### 1. 🎛️ macOS Menu Bar / System Tray Fast Access
- Lives in your top macOS menu bar (`✍️`) just like standard Windows tray apps.
- Closing the window (red 'X' button) keeps OpenGrammarly running silently in the background.
- Dropdown menu for instant access:
  - **Open OpenGrammarly**
  - **Fix Selected Text (`⌘⌥G` or `⌘⇧G`)**
  - **DeepL Translator Tab**
  - **Chrome Extension Folder...**
  - **Launch on Mac Startup** (toggle auto-start on boot)
  - **Quit OpenGrammarly**

### 2. ⚡ In-Place Global Hotkey (`⌘⌥G` / `⌘⇧G`)
- Highlight text in **ANY application** on your Mac (Safari, Chrome, Notes, Word, Slack, WhatsApp, TextEdit).
- Press **`Command + Option + G`** (or **`Command + Shift + G`**).
- OpenGrammarly instantly auto-corrects spelling, punctuation, and grammar mistakes directly in place and shows a clean confirmation banner.

### 3. ✨ Local AI Styles & Tone (Phi-3-Mini SLM)
- Powered by **Microsoft Phi-3-Mini** running 100% locally via Ollama with native Apple Silicon Metal acceleration.
- **5 Writing Styles**:
  - **👔 Formal**: Executive and polished correspondence without artificial filler.
  - **💬 Casual**: Warm, friendly, and natural conversational tone.
  - **✂️ Concise**: Punchy and direct, removing fluff while preserving meaning.
  - **🦁 Confident**: Assertive, eliminating passive voice and hesitation.
  - **🎓 Academic**: Articulate and scholarly flow with advanced vocabulary.
- **1-Click Actions**: Instant Copy, Editor Insertion, or **"🎯 Paste to Active App"**.

### 4. ✍️ Native macOS Desktop App & Translator
- **Grammar & Style Editor**: Real-time mistake detection, spell checking, and one-click **"⚡ Auto-Fix All"**.
- **🌐 DeepL-Style Dual-Panel Translator**:
  - **✨ Phi-3-Mini Neural Engine**: Context-aware, human-level phrasing for English, Spanish, French, German, Italian, Portuguese, Arabic, and more.
  - Automatic source language detection.
  - **`⇄` Swap Languages** & **`📑 1-Click Copy`**.
  - **`🎯 Paste to Active App`**: Translates and pastes directly into whichever app you were working in (WhatsApp, Slack, Notes, Word, etc.).

### 5. 🧩 Browser Extension (WhatsApp Web, Slack, Gmail, Notion)
- Native floating widget inside Chromium browsers (**Google Chrome, Brave, Edge**).
- **1-Click WhatsApp In-Place Fix**: Fixes mistakes directly inside the WhatsApp Web compose bar without duplicating or losing cursor focus.
- **1-Click AI Style Chips**: Rewrite chat messages on the fly (`[ 👔 Formal ]`, `[ 💬 Casual ]`, `[ ✂️ Concise ]`, `[ 🦁 Confident ]`).
- **1-Click In-Page Translation**: Quick target language chips (`[ 🇪🇸 ES ]`, `[ 🇫🇷 FR ]`, `[ 🇩🇪 DE ]`, `[ 🇸🇦 AR ]`, `[ 🇬🇧 EN ]`).

---

## 🧩 Setting Up the Browser Extension

1. Open **Google Chrome**, **Brave**, or **Edge** and navigate to:
   ```text
   chrome://extensions
   ```
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **"Load unpacked"**.
4. Click **Downloads** on the left and select:
   ```text
   OpenGrammarly-Extension
   ```
   *(Or click **"🧩 Chrome Extension"** inside OpenGrammarly to reveal it directly).*
5. You're done! A floating indicator will now appear whenever you type in WhatsApp Web, Slack, Gmail, or any text field.

---

## 🔒 Privacy & Offline Guarantee

- **Zero Cloud APIs**: All grammar checking runs against your local LanguageTool server on `localhost:8081`.
- **Zero External AI Calls**: Phi-3-Mini and Argos Translate run 100% locally and offline on your Mac's hardware (Apple Silicon Metal GPU / Intel CPU).
- **Clipboard Safety**: Your normal clipboard copy (`⌘C`) is never intercepted or altered. Fixing is strictly on-demand.
- **Works Without Internet**: Once installed, you can turn off Wi-Fi completely and OpenGrammarly will continue checking grammar, rewriting styles, and translating seamlessly.

---

## 🛠️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                             OpenGrammarly                              │
├──────────────────────────────┬─────────────────────────────────────────┤
│    Desktop PyWebView App     │        Chromium Extension               │
│    (HTML5 / Modern Dark)     │        (Content Script + Service Worker)│
└──────────────┬───────────────┴────────────────────┬────────────────────┘
               │                                    │
               ▼                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Local REST Engine (localhost:8082)                       │
├───────────────────────┬────────────────────────────┬───────────────────┤
│ LanguageTool (8081)   │ Phi-3-Mini SLM (11434)     │ Argos Translate   │
│ - Spelling & Grammar  │ - Metal GPU Acceleration   │ - CTranslate2     │
│ - Multi-language rules│ - Multi-Style Rewriting    │ - Fallback Engine │
│                       │ - Neural Translation       │                   │
└───────────────────────┴────────────────────────────┴───────────────────┘
```

---

## 📄 License

MIT License. Free and open-source for personal and commercial use.

