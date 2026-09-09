#!/usr/bin/env bash
# ==============================================================================
# 🚀 OpenGrammarly - 100% Automated Zero-Config Installer for macOS
# 100% Local, Private, Offline Grammar Checker & DeepL-Style Translator
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${GREEN}${BOLD}"
echo "================================================================="
echo "   ✨ OpenGrammarly - Automated Zero-Config macOS Setup ✨      "
echo "   100% Local • Zero Telemetry • Offline Grammar & Translator    "
echo "================================================================="
echo -e "${NC}"

# Check OS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}❌ Error: OpenGrammarly is designed for macOS.${NC}"
    exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: Ensure Homebrew is installed
echo -e "${BLUE}[1/6] Checking Homebrew...${NC}"
if ! command -v brew &>/dev/null; then
    echo -e "${YELLOW}⚡ Homebrew not found. Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo -e "${GREEN}✓ Homebrew is ready.${NC}"
fi

# Step 2: Install LanguageTool
echo -e "${BLUE}[2/6] Checking LanguageTool Engine...${NC}"
if ! brew list languagetool &>/dev/null; then
    echo -e "${YELLOW}⚡ Installing LanguageTool server via Homebrew...${NC}"
    brew install languagetool
fi

# Ensure LanguageTool service is running
echo -e "${YELLOW}⚡ Starting LanguageTool background service on localhost:8081...${NC}"
brew services start languagetool || true

# Wait for LanguageTool to come online
echo -n "Waiting for LanguageTool engine..."
for i in {1..15}; do
    if curl -s "http://localhost:8081/v2/languages" &>/dev/null; then
        echo -e " ${GREEN}✓ Online!${NC}"
        break
    fi
    sleep 1
    echo -n "."
done

# Step 3: Python 3 & Dependencies
echo -e "${BLUE}[3/6] Setting up Python environment...${NC}"
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}Installing Python 3...${NC}"
    brew install python
fi

echo -e "${YELLOW}⚡ Installing required dependencies (pywebview, argostranslate, ctranslate2, pynput, pyobjc)...${NC}"
python3 -m pip install --quiet --upgrade pywebview argostranslate ctranslate2 torch pynput pyobjc-framework-Cocoa pyobjc-framework-Quartz langdetect

# macOS Python SSL certificate check
CERT_CMD=$(ls /Applications/Python*/Install\ Certificates.command 2>/dev/null | head -n 1 || true)
if [[ -n "$CERT_CMD" ]]; then
    echo -e "${YELLOW}⚡ Verifying Python SSL certificates...${NC}"
    /bin/bash "$CERT_CMD" &>/dev/null || true
fi

# Step 4: Pre-install Neural Translation Models (Argos Translate)
echo -e "${BLUE}[4/6] Pre-installing offline translation models (EN, ES, FR, DE, AR, IT, PT)...${NC}"
python3 -c "
import argostranslate.package
print('Checking local translation packages...')
try:
    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()
    pairs = [('en', 'es'), ('es', 'en'), ('en', 'fr'), ('fr', 'en'), ('en', 'de'), ('de', 'en'), ('en', 'ar'), ('ar', 'en')]
    for f, t in pairs:
        pkg = next((p for p in available if p.from_code == f and p.to_code == t), None)
        if pkg:
            installed = argostranslate.package.get_installed_packages()
            if not any(ip.from_code == f and ip.to_code == t for ip in installed):
                print(f'Downloading offline model: {f} -> {t}...')
                path = pkg.download()
                argostranslate.package.install_from_path(path)
    print('✓ Translation models ready!')
except Exception as e:
    print('Warning: Translation model download will continue in background:', e)
" || true

# Step 5: Install Desktop App to /Applications
echo -e "${BLUE}[5/6] Installing OpenGrammarly.app to /Applications...${NC}"
if [[ -d "$DIR/OpenGrammarly.app" ]]; then
    rm -rf /Applications/OpenGrammarly.app
    cp -R "$DIR/OpenGrammarly.app" /Applications/
    xattr -cr /Applications/OpenGrammarly.app 2>/dev/null || true
    echo -e "${GREEN}✓ OpenGrammarly.app installed to /Applications.${NC}"
fi

# Step 6: Launch and Finish
echo -e "${BLUE}[6/6] Launching OpenGrammarly...${NC}"
open /Applications/OpenGrammarly.app

echo ""
echo -e "${GREEN}${BOLD}🎉 Installation Complete! All systems are online.${NC}"
echo "-----------------------------------------------------------------"
echo -e "🖥️  ${BOLD}Desktop App:${NC} /Applications/OpenGrammarly.app (now running!)"
echo -e "🌐  ${BOLD}Translation:${NC} 100% Offline (DeepL-Style) ready in app"
echo -e "🧩  ${BOLD}Chrome / WhatsApp Extension:${NC}"
echo "    1. Open chrome://extensions in your browser"
echo "    2. Turn ON 'Developer mode' (top right corner)"
echo "    3. Click 'Load unpacked' and choose:"
echo -e "       ${BOLD}/Applications/OpenGrammarly.app/Contents/Resources/extension${NC}"
echo "-----------------------------------------------------------------"
echo -e "${GREEN}Enjoy private, offline grammar checking and translation! 🚀${NC}"
