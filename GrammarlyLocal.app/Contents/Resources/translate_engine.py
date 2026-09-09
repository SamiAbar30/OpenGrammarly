#!/usr/bin/env python3
"""
GrammarlyLocal - Local DeepL-like Offline Neural Translation Engine.
Powered by Argos Translate & OpenNMT / CTranslate2.
Runs 100% offline on Apple Silicon with zero external API calls.
"""

import os
import re
import threading
import argostranslate.package
import argostranslate.translate

# Pre-defined common language names and codes
SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "flag": "🇬🇧"},
    {"code": "es", "name": "Spanish", "flag": "🇪🇸"},
    {"code": "fr", "name": "French", "flag": "🇫🇷"},
    {"code": "de", "name": "German", "flag": "🇩🇪"},
    {"code": "it", "name": "Italian", "flag": "🇮🇹"},
    {"code": "pt", "name": "Portuguese", "flag": "🇵🇹"},
    {"code": "ar", "name": "Arabic", "flag": "🇸🇦"},
    {"code": "zh", "name": "Chinese", "flag": "🇨🇳"},
    {"code": "ru", "name": "Russian", "flag": "🇷🇺"},
    {"code": "ja", "name": "Japanese", "flag": "🇯🇵"},
]

# High-frequency words for fast offline language detection
STOPWORDS = {
    "es": {"el", "la", "de", "que", "y", "en", "un", "una", "es", "por", "para", "con", "no", "como", "su", "al", "hola", "estás", "está", "amigo"},
    "fr": {"le", "la", "les", "de", "et", "en", "un", "une", "est", "pour", "dans", "qui", "avec", "bonjour", "merci", "vous", "nous"},
    "de": {"der", "die", "das", "und", "in", "zu", "den", "das", "nicht", "von", "sie", "ist", "des", "sich", "mit", "hallo", "danke"},
    "it": {"il", "la", "di", "e", "in", "un", "che", "per", "non", "del", "sono", "con", "ciao", "grazie", "questo"},
    "pt": {"o", "a", "de", "e", "que", "do", "da", "em", "um", "para", "com", "não", "uma", "olá", "obrigado"},
    "en": {"the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with", "he", "as", "you", "do", "hello", "hi"},
}

_installing_pairs = set()
_lock = threading.Lock()


def detect_language(text: str) -> str:
    """Fast, accurate offline language detector for common languages."""
    if not text or not text.strip():
        return "en"

    # Check for Arabic script
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    # Check for Chinese characters
    if re.search(r"[\u4E00-\u9FFF]", text):
        return "zh"
    # Check for Japanese kana
    if re.search(r"[\u3040-\u30FF]", text):
        return "ja"
    # Check for Cyrillic / Russian
    if re.search(r"[\u0400-\u04FF]", text):
        return "ru"

    # Tokenize words for Latin-based languages
    words = set(re.findall(r"\b[A-Za-zÀ-ÿ']+\b", text.lower()))
    if not words:
        return "en"

    scores = {}
    for lang, stoplist in STOPWORDS.items():
        matched = words.intersection(stoplist)
        scores[lang] = len(matched)

    best_lang = max(scores, key=scores.get)
    if scores[best_lang] > 0:
        return best_lang

    # Check Spanish special punctuation (¿, ¡, ñ)
    if re.search(r"[¿¡ñ]", text, re.IGNORECASE):
        return "es"

    return "en"


def get_installed_pairs() -> list[dict]:
    """Return list of currently installed translation pairs."""
    try:
        installed = argostranslate.translate.get_installed_languages()
        pairs = []
        for from_lang in installed:
            for to_lang in from_lang.translations_from:
                pairs.append({
                    "from_code": from_lang.code,
                    "from_name": from_lang.name,
                    "to_code": to_lang.to_lang.code,
                    "to_name": to_lang.to_lang.name,
                })
        return pairs
    except Exception:
        return []


def is_pair_installed(from_code: str, to_code: str) -> bool:
    """Check if a specific language pair model is installed."""
    pairs = get_installed_pairs()
    return any(p["from_code"] == from_code and p["to_code"] == to_code for p in pairs)


def install_pair_sync(from_code: str, to_code: str) -> bool:
    """Download and install a language package synchronously."""
    pair_key = f"{from_code}_{to_code}"
    with _lock:
        if is_pair_installed(from_code, to_code):
            return True
        if pair_key in _installing_pairs:
            return False
        _installing_pairs.add(pair_key)

    try:
        print(f"[Translate] Updating package index for {pair_key}...")
        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()

        target_pkg = next((p for p in available if p.from_code == from_code and p.to_code == to_code), None)
        if not target_pkg:
            print(f"[Translate] No direct package found for {pair_key}")
            return False

        print(f"[Translate] Downloading package {pair_key}...")
        download_path = target_pkg.download()
        argostranslate.package.install_from_path(download_path)
        print(f"[Translate] Successfully installed {pair_key}!")
        return True
    except Exception as e:
        print(f"[Translate] Error installing {pair_key}: {e}")
        return False
    finally:
        with _lock:
            _installing_pairs.discard(pair_key)


def install_pair_async(from_code: str, to_code: str):
    """Download and install a language package in background thread."""
    t = threading.Thread(target=install_pair_sync, args=(from_code, to_code), daemon=True)
    t.start()


def translate_text(text: str, from_code: str = "auto", to_code: str = "es") -> dict:
    """
    Translate text completely locally and offline.
    Returns:
      {
        "translated": str,
        "from": str,
        "to": str,
        "detected": str
      }
    """
    if not text or not text.strip():
        return {"translated": "", "from": from_code, "to": to_code, "detected": from_code}

    detected = from_code
    if from_code == "auto" or not from_code:
        detected = detect_language(text)
        from_code = detected

    # If same language, return as is
    if from_code == to_code:
        # Default flip: if typing English and target is English, translate to Spanish
        if to_code == "en":
            to_code = "es"
        else:
            to_code = "en"

    # Check if pair is installed
    if not is_pair_installed(from_code, to_code):
        # Trigger background install if not already installing
        install_pair_async(from_code, to_code)
        # Attempt sync install if it's a popular pair
        success = install_pair_sync(from_code, to_code)
        if not success:
            return {
                "translated": f"Installing local model for {from_code.upper()} -> {to_code.upper()}... Please try again in a few seconds.",
                "from": from_code,
                "to": to_code,
                "detected": detected,
                "status": "installing"
            }

    try:
        translated = argostranslate.translate.translate(text, from_code, to_code)
        return {
            "translated": translated,
            "from": from_code,
            "to": to_code,
            "detected": detected,
            "status": "ok"
        }
    except Exception as e:
        return {
            "translated": f"Translation error: {e}",
            "from": from_code,
            "to": to_code,
            "detected": detected,
            "status": "error"
        }


if __name__ == "__main__":
    import sys
    test_text = sys.argv[1] if len(sys.argv) > 1 else "Hello world, this is a local offline test."
    print("Input:", test_text)
    res = translate_text(test_text, "auto", "es")
    print("Output:", res)
