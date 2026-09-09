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

## ⚡ 1-Line Automated Install (Zero Config)

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

### What the installer does automatically:
- Installs and starts the local **LanguageTool** grammar engine on `localhost:8081`.
- Sets up Python dependencies (`pywebview`, `argostranslate`, `ctranslate2`, `torch`).
- Downloads offline neural translation models for **English, Spanish, French, German, Italian, Portuguese, Arabic**.
- Installs `OpenGrammarly.app` into `/Applications` and launches it.
- **Zero manual configuration required!**

---

## 🌟 Key Features

### 1. ✍️ Native macOS Desktop App
- **Grammar & Style Editor**: Real-time mistake detection, spell checking, and one-click **"⚡ Auto-Fix All"**.
- **🌐 DeepL-Style Dual-Panel Translator**:
  - Automatic source language detection.
  - Bidirectional instant offline translation powered by local CTranslate2 neural networks.
  - **`⇄` Swap Languages** & **`📑 1-Click Copy`**.
  - **`🎯 Paste to Active App`**: Translates and pastes directly into whichever app you were working in (WhatsApp, Slack, Notes, Word, etc.).

### 2. 🧩 Browser Extension (WhatsApp Web, Slack, Gmail, Notion)
- Native floating widget inside Chromium browsers (**Google Chrome, Brave, Edge**).
- **1-Click WhatsApp In-Place Fix**: Fixes mistakes or translates entire messages directly inside the WhatsApp Web chat box without duplicating or losing cursor focus.
- **1-Click In-Page Translation**: Quick target language chips (`[ 🇪🇸 ES ]`, `[ 🇫🇷 FR ]`, `[ 🇩🇪 DE ]`, `[ 🇸🇦 AR ]`, `[ 🇬🇧 EN ]`).

### 3. 🎯 Global System-Wide Shortcut (`⌘ + ⇧ + G`)
- Highlight text anywhere on macOS (Safari, Pages, Notes, Slack, VS Code).
- Press your shortcut (or click **"Fix Active App"**) to automatically fix mistakes in place.

---

## 🧩 Setting Up the Browser Extension

1. Open **Google Chrome**, **Brave**, or **Edge** and navigate to:
   ```text
   chrome://extensions
   ```
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **"Load unpacked"**.
4. Select the extension directory:
   ```text
   /Applications/OpenGrammarly.app/Contents/Resources/extension
   ```
   *(Or the `extension` folder inside this repository).*
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
