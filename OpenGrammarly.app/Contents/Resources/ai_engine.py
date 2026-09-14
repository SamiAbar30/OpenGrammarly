"""
OpenGrammarly - Local AI Engine (Phi-3-Mini)
100% Offline, Private AI text rewriting, style proposal, and high-accuracy neural translation.
Connects to local Ollama runtime on http://127.0.0.1:11434 with automatic fallback.
"""

import json
import logging
import threading
import urllib.error
import urllib.request

OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL_NAME = "qwen2.5:1.5b"
ALT_MODEL_NAMES = ["phi3:mini", "phi3", "qwen2.5:0.5b", "llama3.2:1b", "llama3.2:3b"]

logger = logging.getLogger("OpenGrammarlyAI")

_cached_status = {
    "ollama_running": False,
    "model_installed": False,
    "active_model": None,
    "installing": False,
    "progress": 0,
}
_status_lock = threading.Lock()


def is_ollama_running() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_available_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def get_active_model() -> str | None:
    models = get_available_models()
    for candidate in [MODEL_NAME] + ALT_MODEL_NAMES:
        for m in models:
            if m == candidate or m.startswith(candidate + ":") or candidate in m:
                return m
    return None


def check_ai_status() -> dict:
    global _cached_status
    running = is_ollama_running()
    active_model = None
    installed = False
    if running:
        active_model = get_active_model()
        installed = active_model is not None

    with _status_lock:
        _cached_status["ollama_running"] = running
        _cached_status["model_installed"] = installed
        _cached_status["active_model"] = active_model
        return dict(_cached_status)


def install_phi3_async():
    """Trigger background pull of local model via Ollama."""
    with _status_lock:
        if _cached_status.get("installing"):
            return {"status": "already_installing"}
        _cached_status["installing"] = True
        _cached_status["progress"] = 0

    target = "qwen2.5:1.5b" if "qwen2.5:1.5b" not in get_available_models() else "phi3:mini"

    def _worker():
        global _cached_status
        try:
            req = urllib.request.Request(
                f"{OLLAMA_HOST}/api/pull",
                data=json.dumps({"name": target, "stream": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                resp.read()
        except Exception as e:
            logger.error(f"Failed to pull {target}: {e}")
        finally:
            with _status_lock:
                _cached_status["installing"] = False
                check_ai_status()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return {"status": "started", "model": target}


def prewarm_model():
    """Keep active model loaded in Apple Silicon GPU memory permanently."""
    def _worker():
        try:
            if is_ollama_running():
                model = get_active_model()
                if model:
                    body = {
                        "model": model,
                        "prompt": "hi",
                        "stream": False,
                        "keep_alive": -1,
                        "options": {"num_predict": 1},
                    }
                    req = urllib.request.Request(
                        f"{OLLAMA_HOST}/api/generate",
                        data=json.dumps(body).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        resp.read()
                    logger.info(f"OpenGrammarly: AI Model {model} pinned in GPU VRAM.")
        except Exception as e:
            logger.debug(f"OpenGrammarly: AI pre-warm skipped: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _call_ollama_generate(prompt: str, system_prompt: str = "", model: str = None, response_format: str = None) -> str:
    active = model or get_active_model() or MODEL_NAME
    word_count = len(prompt.split())
    max_tokens = max(64, min(240, word_count * 4))

    body = {
        "model": active,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": max_tokens,
            "stop": [
                "<|end|>", "<|im_end|>", "<|user|>", "<|system|>",
                "\n\nText to", "\nText to", "Text to correct:", "Text to rewrite:", "Text to translate:",
                "\n\nOriginal:", "\n\n", "Translation:"
            ],
        },
    }
    if system_prompt:
        body["system"] = system_prompt
    if response_format:
        body["format"] = response_format

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20.0) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        out = res.get("response", "").strip()

        if response_format != "json":
            # Stop token safety: clean synthetic few-shot loops
            for delim in ["\n\nText to", "\nText to", "Text to correct:", "Text to rewrite:", "Text to translate:", "\n\nOriginal:"]:
                if delim in out:
                    out = out.split(delim)[0].strip()

            if out.startswith('"') and out.endswith('"') and len(out) > 2:
                out = out[1:-1]
        return out


STYLE_SYSTEM_PROMPTS = {
    "formal": (
        "You are a professional writing assistant. Rewrite the user's text in a polished, formal business tone. "
        "CRITICAL RULES: "
        "1. Keep the rewrite to the exact same format and length (sentence-for-sentence). "
        "2. NEVER add email greetings (like 'Dear...', 'Greetings'), sign-offs (like 'Best regards'), or placeholder names (like '[Your Name]'). "
        "3. Output ONLY the rewritten sentence(s), nothing else."
    ),
    "casual": (
        "You are a friendly writing assistant. Rewrite the user's text in a relaxed, warm, natural conversational tone. "
        "Keep the exact same length. Output ONLY the rewritten sentence(s), nothing else."
    ),
    "concise": (
        "You are a direct communications editor. Rewrite the user's text to be short, clear, and concise, removing all unnecessary filler. "
        "Output ONLY the rewritten sentence(s), nothing else."
    ),
    "confident": (
        "You are an assertive communications coach. Rewrite the user's text in a strong, confident, and decisive tone. "
        "Eliminate passive voice, hesitation, and apologies. Output ONLY the rewritten sentence(s), nothing else."
    ),
    "academic": (
        "You are an academic editor. Rewrite the user's text in an articulate, scholarly tone with sophisticated vocabulary. "
        "CRITICAL RULES: "
        "1. Keep the rewrite to the exact same format and length (sentence-for-sentence). "
        "2. NEVER add greetings (like 'Dear...', 'Greetings'), sign-offs, or placeholder names. "
        "3. Output ONLY the rewritten sentence(s), nothing else."
    ),
}


def rewrite_style(text: str, style: str = "formal") -> dict:
    if not text or not text.strip():
        return {"original": text, "rewritten": "", "style": style}

    if not is_ollama_running():
        return {
            "original": text,
            "rewritten": text,
            "style": style,
            "error": "Ollama is not running. Please start Ollama or install Phi-3-Mini.",
            "status": "ai_offline",
        }

    sys_prompt = STYLE_SYSTEM_PROMPTS.get(style.lower(), STYLE_SYSTEM_PROMPTS["formal"])
    user_prompt = f"Text to rewrite:\n{text.strip()}"

    try:
        rewritten = _call_ollama_generate(user_prompt, system_prompt=sys_prompt)
        return {
            "original": text,
            "rewritten": rewritten,
            "style": style,
            "status": "success",
        }
    except Exception as e:
        return {
            "original": text,
            "rewritten": text,
            "style": style,
            "error": str(e),
            "status": "error",
        }


def rewrite_all_styles(text: str) -> dict:
    """Generate proposals for all primary styles efficiently in a single pass."""
    if not text or not text.strip():
        return {"styles": {}}

    if not is_ollama_running():
        return {
            "original": text,
            "styles": {},
            "error": "Ollama is not running",
            "status": "ai_offline",
        }

    def _extract_text(val) -> str:
        if isinstance(val, str):
            return val.strip()
        if isinstance(val, dict):
            for subk in ["text", "rewritten", "sentence", "output", "result"]:
                if subk in val and isinstance(val[subk], str):
                    return val[subk].strip()
            for v in val.values():
                if isinstance(v, str):
                    return v.strip()
        return ""

    # Attempt 1: Ultra-fast single-pass JSON generation (~1-1.5s total)
    prompt = (
        f"Rewrite the following text into 4 distinct styles:\n"
        f"- formal: professional business tone, no email greetings or sign-offs\n"
        f"- casual: friendly, warm, natural conversational tone\n"
        f"- concise: short, direct, eliminating all filler words\n"
        f"- confident: assertive, decisive, eliminate passive voice and apologies\n\n"
        f"Input text: \"{text.strip()}\"\n\n"
        f"Example JSON structure:\n"
        f"{{\"formal\": \"text here\", \"casual\": \"text here\", \"concise\": \"text here\", \"confident\": \"text here\"}}"
    )
    sys_prompt = (
        "You are an expert writing assistant. You must respond strictly in valid JSON format "
        "with keys: formal, casual, concise, confident. Output ONLY valid JSON, no markdown formatting."
    )

    try:
        raw_json = _call_ollama_generate(prompt, system_prompt=sys_prompt, response_format="json")
        styles = json.loads(raw_json)
        clean_styles = {}
        for k in ["formal", "casual", "concise", "confident"]:
            extracted = _extract_text(styles.get(k))
            if extracted:
                clean_styles[k] = extracted
            else:
                clean_styles[k] = text.strip()
        return {"original": text, "styles": clean_styles, "status": "success"}
    except Exception as e:
        logger.warning(f"Single pass JSON rewrite failed, falling back to sequential: {e}")

    # Fallback: Sequential generation
    results = {}
    for style in ["formal", "casual", "concise", "confident"]:
        res = rewrite_style(text, style)
        results[style] = res.get("rewritten", text)

    return {"original": text, "styles": results, "status": "success"}


def ai_fix_grammar(text: str) -> dict:
    if not text or not text.strip():
        return {"original": text, "fixed": "", "status": "empty"}

    if not is_ollama_running():
        return {
            "original": text,
            "fixed": text,
            "error": "Ollama is offline",
            "status": "ai_offline",
        }

    sys_prompt = (
        "You are an elite proofreader and copyeditor. Correct all grammar, spelling, "
        "punctuation, and phrasing errors in the provided text. "
        "Maintain the exact intended meaning and tone of the author. "
        "Output ONLY the corrected text without preamble, explanations, or quotes."
    )
    user_prompt = f"Text to correct:\n{text.strip()}"

    try:
        fixed = _call_ollama_generate(user_prompt, system_prompt=sys_prompt)
        return {"original": text, "fixed": fixed, "status": "success"}
    except Exception as e:
        return {"original": text, "fixed": text, "error": str(e), "status": "error"}


def ai_translate(text: str, target_lang: str, source_lang: str = "auto") -> dict:
    if not text or not text.strip():
        return {"original": text, "translated": "", "status": "empty"}

    if not is_ollama_running():
        return {
            "original": text,
            "translated": "",
            "error": "Ollama is offline",
            "status": "ai_offline",
        }

    lang_names = {
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "ar": "Modern Standard Arabic (العربية)",
        "en": "English",
        "ru": "Russian",
        "zh": "Chinese",
        "ja": "Japanese",
    }
    tgt = lang_names.get(target_lang.lower(), target_lang)

    # For Arabic, Qwen2.5 is natively fluent and vastly superior to Phi-3
    avail = get_available_models()
    model = None
    if target_lang.lower() == "ar":
        for cand in ["qwen2.5:1.5b", "qwen2.5:0.5b", "qwen2.5:3b", "qwen2.5"]:
            if any(cand in m for m in avail):
                model = next(m for m in avail if cand in m)
                break

    sys_prompt = (
        f"You are a professional human translator. Translate into {tgt}. "
        f"Output ONLY the direct translation without notes or quotes."
    )
    user_prompt = text.strip()

    try:
        translated = _call_ollama_generate(user_prompt, system_prompt=sys_prompt, model=model)
        active_engine = model or get_active_model() or "local_ai"
        return {
            "original": text,
            "translated": translated,
            "target": target_lang,
            "engine": active_engine,
            "status": "success",
        }
    except Exception as e:
        return {
            "original": text,
            "translated": "",
            "engine": "local_ai",
            "error": str(e),
            "status": "error",
        }
