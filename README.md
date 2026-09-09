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

### 3. ✍️ Native macOS Desktop App
- **Grammar & Style Editor**: Real-time mistake detection, spell checking, and one-click **"⚡ Auto-Fix All"**.
- **🌐 DeepL-Style Dual-Panel Translator**:
  - Automatic source language detection.
  - Bidirectional instant offline translation powered by local CTranslate2 neural networks.
  - **`⇄` Swap Languages** & **`📑 1-Click Copy`**.
  - **`🎯 Paste to Active App`**: Translates and pastes directly into whichever app you were working in (WhatsApp, Slack, Notes, Word, etc.).

### 4. 🧩 Browser Extension (WhatsApp Web, Slack, Gmail, Notion)
- Native floating widget inside Chromium browsers (**Google Chrome, Brave, Edge**).
- **1-Click WhatsApp In-Place Fix**: Fixes mistakes or translates entire messages directly inside the WhatsApp Web chat box without duplicating or losing cursor focus.
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
   *(Or click **"🧩 Chrome Extension"** inside OpenGrammarly to open it directly).*
5. You're done! A floating indicator will now appear whenever you type in WhatsApp Web, Slack, Gmail, or any text field.

---

## 🔒 Privacy & Offline Guarantee

- **Zero Cloud APIs**: All grammar checking runs against your local LanguageTool server on `localhost:8081`.
- **Zero External Translation Calls**: Translation weights run directly on your Mac's Apple Silicon / Intel CPU via CTranslate2.
- **Works Without Internet**: Once installed, you can turn off Wi-Fi completely and OpenGrammarly will continue checking grammar and translating seamlessly.

---

## 🛠️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────┐
│                   OpenGrammarly                       │
├──────────────────────────┬─────────────────────────────┤
│   Desktop PyWebView App  │   Chromium Extension        │
│   (HTML5 / Modern Dark)  │   (Content Script + Worker) │
└─────────────┬────────────┴──────────────┬──────────────┘
              │                           │
              ▼                           ▼
┌────────────────────────────────────────────────────────┐
│     Local Proxy & Translation API (localhost:8082)     │
├──────────────────────────┬─────────────────────────────┤
│  LanguageTool (8081)     │  Argos Translate            │
│  - Spelling & Grammar    │  - CTranslate2 Engine       │
│  - Multi-language rules  │  - Local Neural Weights     │
└──────────────────────────┴─────────────────────────────┘
```

---

## 📄 License

MIT License. Free and open-source for personal and commercial use.
