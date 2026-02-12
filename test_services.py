"""
News Anchor Voice AI - Service Diagnostics
============================================
Tests every component in the pipeline with detailed logs.

Usage: python test_services.py

Pipeline: Mic -> Whisper(8000) -> Gemma3(11434) -> Kokoro(Local) -> Speaker
Bot: FastAPI on port 7860
"""

import os
import sys
import json
import time
import wave
import struct
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

# Try to load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:8000/v1")
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/v1")
BOT_URL     = f"http://127.0.0.1:{os.getenv('BOT_PORT', '7860')}"
LLM_MODEL   = os.getenv("LLM_MODEL", "gemma3:4b")

# Strip /v1 for base health checks
WHISPER_BASE = WHISPER_URL.rstrip("/").removesuffix("/v1")
OLLAMA_BASE  = OLLAMA_URL.rstrip("/").removesuffix("/v1")

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

results = []

def log(icon, message, detail=""):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"  [{ts}] {icon}  {message}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def section(title):
    print()
    print(f"  {'=' * 60}")
    print(f"  {title}")
    print(f"  {'=' * 60}")


def timed_request(method, url, **kwargs):
    """Make a request and return (response, elapsed_ms) or (None, elapsed_ms)."""
    import urllib.request
    import urllib.error

    start = time.perf_counter()
    try:
        if method == "GET":
            req = urllib.request.Request(url)
            for k, v in kwargs.get("headers", {}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                elapsed = (time.perf_counter() - start) * 1000
                return {"status": resp.status, "body": body, "headers": dict(resp.headers)}, elapsed

        elif method == "POST":
            data = kwargs.get("data", None)
            headers = kwargs.get("headers", {})
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                elapsed = (time.perf_counter() - start) * 1000
                return {"status": resp.status, "body": body, "headers": dict(resp.headers)}, elapsed

    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        body = e.read() if hasattr(e, 'read') else b""
        return {"status": e.code, "body": body, "error": str(e)}, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": 0, "body": b"", "error": str(e)}, elapsed


def generate_test_wav(duration_s=2, sample_rate=16000, frequency=440):
    """Generate a simple sine wave WAV file for STT testing."""
    import math
    n_samples = int(sample_rate * duration_s)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # Generate a tone that sounds like speech-ish noise
        val = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack('<h', val))

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(samples))
    return tmp.name


# ---------------------------------------------------------------------------
# TEST 1: Whisper STT
# ---------------------------------------------------------------------------
def test_whisper():
    section("TEST 1: WHISPER STT (Speech-to-Text)")
    log(INFO, f"URL: {WHISPER_BASE}")

    # 1a. Health check
    log(INFO, "Checking health endpoint...")
    resp, ms = timed_request("GET", f"{WHISPER_BASE}/health")
    if resp and resp["status"] == 200:
        log(PASS, f"Health OK", f"{ms:.0f}ms")
        results.append(("Whisper Health", True))
    else:
        err = resp.get("error", "Unknown") if resp else "Connection refused"
        log(FAIL, f"Health FAILED", f"{err}")
        results.append(("Whisper Health", False))
        return

    # 1b. Model info (OpenAI-compatible)
    log(INFO, "Checking available models...")
    resp, ms = timed_request("GET", f"{WHISPER_BASE}/v1/models")
    if resp and resp["status"] == 200:
        try:
            models = json.loads(resp["body"])
            model_ids = [m.get("id", "?") for m in models.get("data", [])]
            log(PASS, f"Models available", f"{model_ids} ({ms:.0f}ms)")
        except:
            log(PASS, f"Models endpoint OK", f"{ms:.0f}ms")
        results.append(("Whisper Models", True))
    else:
        log(WARN, "Models endpoint not available (non-critical)")
        results.append(("Whisper Models", None))

    # 1c. Actual transcription test
    log(INFO, "Testing transcription with synthetic audio...")
    wav_path = generate_test_wav(duration_s=1, frequency=440)
    try:
        import urllib.request
        boundary = "----TestBoundary12345"
        body_parts = []
        body_parts.append(f"--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="file"; filename="test.wav"\r\n'.encode())
        body_parts.append(b'Content-Type: audio/wav\r\n\r\n')
        with open(wav_path, "rb") as f:
            body_parts.append(f.read())
        body_parts.append(f"\r\n--{boundary}\r\n".encode())
        body_parts.append(f'Content-Disposition: form-data; name="model"\r\n\r\n'.encode())
        body_parts.append(b"whisper-1")
        body_parts.append(f"\r\n--{boundary}--\r\n".encode())

        data = b"".join(body_parts)
        resp, ms = timed_request(
            "POST",
            f"{WHISPER_BASE}/v1/audio/transcriptions",
            data=data,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        if resp and resp["status"] == 200:
            try:
                result = json.loads(resp["body"])
                text = result.get("text", "(empty)")
            except:
                text = resp["body"].decode("utf-8", errors="replace")[:100]
            log(PASS, f"Transcription OK", f'"{text}" ({ms:.0f}ms)')
            results.append(("Whisper Transcription", True))
        else:
            err = resp.get("error", "Unknown") if resp else "No response"
            log(FAIL, f"Transcription FAILED", f"{err} ({ms:.0f}ms)")
            results.append(("Whisper Transcription", False))
    except Exception as e:
        log(FAIL, f"Transcription error", f"{e}")
        results.append(("Whisper Transcription", False))
    finally:
        os.unlink(wav_path)


# ---------------------------------------------------------------------------
# TEST 2: Ollama LLM
# ---------------------------------------------------------------------------
def test_ollama():
    section("TEST 2: OLLAMA LLM (Large Language Model)")
    log(INFO, f"URL: {OLLAMA_BASE}")
    log(INFO, f"Model: {LLM_MODEL}")

    # 2a. Health / version check
    log(INFO, "Checking Ollama server...")
    resp, ms = timed_request("GET", f"{OLLAMA_BASE}/api/version")
    if resp and resp["status"] == 200:
        try:
            ver = json.loads(resp["body"]).get("version", "?")
            log(PASS, f"Ollama server OK", f"v{ver} ({ms:.0f}ms)")
        except:
            log(PASS, f"Ollama server OK", f"{ms:.0f}ms")
        results.append(("Ollama Server", True))
    else:
        # Try just the root
        resp2, ms2 = timed_request("GET", f"{OLLAMA_BASE}")
        if resp2 and resp2["status"] == 200:
            log(PASS, f"Ollama server OK", f"{ms2:.0f}ms")
            results.append(("Ollama Server", True))
        else:
            err = resp.get("error", "Connection refused") if resp else "Connection refused"
            log(FAIL, f"Ollama server FAILED", f"{err}")
            results.append(("Ollama Server", False))
            return

    # 2b. Check model is available
    log(INFO, f"Checking if {LLM_MODEL} is loaded...")
    resp, ms = timed_request("GET", f"{OLLAMA_BASE}/api/tags")
    if resp and resp["status"] == 200:
        try:
            tags = json.loads(resp["body"])
            models = [m["name"] for m in tags.get("models", [])]
            if LLM_MODEL in models or any(LLM_MODEL in m for m in models):
                log(PASS, f"Model '{LLM_MODEL}' found", f"Available models: {models}")
                results.append(("Ollama Model", True))
            else:
                log(FAIL, f"Model '{LLM_MODEL}' NOT found", f"Available: {models}")
                results.append(("Ollama Model", False))
                return
        except Exception as e:
            log(WARN, f"Could not parse model list", f"{e}")
            results.append(("Ollama Model", None))
    else:
        log(FAIL, "Could not list models")
        results.append(("Ollama Model", False))
        return

    # 2c. Actual generation test
    log(INFO, f"Testing generation with {LLM_MODEL}...")
    payload = json.dumps({
        "model": LLM_MODEL,
        "prompt": "Say 'Hello, I am working!' in exactly 5 words.",
        "stream": False,
        "options": {"num_predict": 20}
    }).encode()
    resp, ms = timed_request(
        "POST",
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    if resp and resp["status"] == 200:
        try:
            result = json.loads(resp["body"])
            text = result.get("response", "(empty)")[:100]
            log(PASS, f"Generation OK", f'"{text}" ({ms:.0f}ms)')
        except:
            log(PASS, f"Generation OK", f"{ms:.0f}ms")
        results.append(("Ollama Generation", True))
    else:
        err = resp.get("error", "Unknown") if resp else "No response"
        log(FAIL, f"Generation FAILED", f"{err} ({ms:.0f}ms)")
        results.append(("Ollama Generation", False))

    # 2d. Test OpenAI-compatible endpoint (what Pipecat uses)
    log(INFO, "Testing OpenAI-compatible chat endpoint...")
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": "Say hello in one sentence."}],
        "max_tokens": 20,
        "stream": False
    }).encode()
    resp, ms = timed_request(
        "POST",
        f"{OLLAMA_BASE}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    if resp and resp["status"] == 200:
        try:
            result = json.loads(resp["body"])
            text = result["choices"][0]["message"]["content"][:100]
            log(PASS, f"OpenAI-compat OK", f'"{text}" ({ms:.0f}ms)')
        except Exception as e:
            log(PASS, f"OpenAI-compat OK", f"{ms:.0f}ms (parse issue: {e})")
        results.append(("Ollama OpenAI API", True))
    else:
        err = resp.get("error", "Unknown") if resp else "No response"
        log(FAIL, f"OpenAI-compat FAILED", f"{err}")
        results.append(("Ollama OpenAI API", False))


# ---------------------------------------------------------------------------
# TEST 3: Piper TTS (Skipped - running locally)
# ---------------------------------------------------------------------------
def test_piper():
    # Kokoro runs in-process now, so no HTTP test possible
    pass


# ---------------------------------------------------------------------------
# TEST 4: Bot Server
# ---------------------------------------------------------------------------
def test_bot():
    section("TEST 4: PIPECAT BOT (FastAPI Server)")
    log(INFO, f"URL: {BOT_URL}")

    # 4a. Root page
    log(INFO, "Checking main page...")
    resp, ms = timed_request("GET", f"{BOT_URL}/")
    if resp and resp["status"] == 200:
        body_str = resp["body"].decode("utf-8", errors="replace")
        has_html = "<html" in body_str.lower() or "<!doctype" in body_str.lower()
        log(PASS, f"Main page OK", f"HTML={'Yes' if has_html else 'No'}, {len(resp['body'])} bytes ({ms:.0f}ms)")
        results.append(("Bot Main Page", True))
    else:
        err = resp.get("error", "Connection refused") if resp else "Connection refused"
        log(FAIL, f"Main page FAILED", f"{err}")
        log(INFO, "If the bot isn't running yet, start it with start.bat first.")
        results.append(("Bot Main Page", False))
        return

    # 4b. Config API
    log(INFO, "Checking config API...")
    resp, ms = timed_request("GET", f"{BOT_URL}/api/config")
    if resp and resp["status"] == 200:
        try:
            config = json.loads(resp["body"])
            category = config.get("newsCategory", "?")
            style = config.get("anchorStyle", "?")
            log(PASS, f"Config API OK", f"category={category}, style={style} ({ms:.0f}ms)")
        except:
            log(PASS, f"Config API OK", f"{ms:.0f}ms")
        results.append(("Bot Config API", True))
    else:
        log(FAIL, "Config API FAILED")
        results.append(("Bot Config API", False))

    # 4c. News API
    log(INFO, "Checking news API...")
    resp, ms = timed_request("GET", f"{BOT_URL}/api/news?category=headlines")
    if resp and resp["status"] == 200:
        try:
            news = json.loads(resp["body"])
            articles = news.get("articles", [])
            log(PASS, f"News API OK", f"{len(articles)} articles ({ms:.0f}ms)")
            if articles:
                log(INFO, f"  First headline: \"{articles[0].get('title', '?')[:60]}\"")
        except:
            log(PASS, f"News API OK", f"{ms:.0f}ms")
        results.append(("Bot News API", True))
    else:
        log(FAIL, "News API FAILED")
        results.append(("Bot News API", False))

    # 4d. WebRTC offer endpoint (just check it exists, don't actually connect)
    log(INFO, "Checking WebRTC offer endpoint exists...")
    # Send a minimal invalid offer to see if endpoint responds
    payload = json.dumps({"sdp": "test", "type": "offer"}).encode()
    resp, ms = timed_request(
        "POST",
        f"{BOT_URL}/api/offer",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    if resp:
        # Any response means the endpoint exists (even 500 is OK here)
        status = resp["status"]
        if status == 500 or status == 400:
            log(PASS, f"WebRTC endpoint exists", f"Status {status} (expected for invalid SDP) ({ms:.0f}ms)")
            results.append(("Bot WebRTC Endpoint", True))
        elif status == 200:
            log(PASS, f"WebRTC endpoint OK", f"{ms:.0f}ms")
            results.append(("Bot WebRTC Endpoint", True))
        else:
            log(WARN, f"WebRTC endpoint returned {status}", f"{ms:.0f}ms")
            results.append(("Bot WebRTC Endpoint", None))
    else:
        log(FAIL, "WebRTC endpoint FAILED")
        results.append(("Bot WebRTC Endpoint", False))


# ---------------------------------------------------------------------------
# TEST 5: End-to-End Pipeline Check
# ---------------------------------------------------------------------------
def test_e2e():
    section("TEST 5: END-TO-END PIPELINE VALIDATION")

    log(INFO, "Checking all services are connected...")

    services = {
        "Whisper STT":  f"{WHISPER_BASE}/health",
        "Ollama LLM":   f"{OLLAMA_BASE}",
        "Pipecat Bot":  f"{BOT_URL}/",
    }

    all_up = True
    for name, url in services.items():
        resp, ms = timed_request("GET", url)
        if resp and resp["status"] == 200:
            log(PASS, f"{name} is UP", f"{ms:.0f}ms")
        else:
            log(FAIL, f"{name} is DOWN")
            all_up = False

    if all_up:
        log(PASS, "ALL SERVICES RUNNING -- Pipeline is ready!")
        results.append(("E2E All Services", True))
    else:
        log(FAIL, "Some services are DOWN -- Pipeline incomplete")
        results.append(("E2E All Services", False))

    # Check Docker containers
    log(INFO, "")
    log(INFO, "Docker container status:")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n"):
            log(INFO, f"  {line}")
    except Exception as e:
        log(WARN, f"Could not check Docker: {e}")


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
def print_summary():
    section("DIAGNOSTIC SUMMARY")

    passed = sum(1 for _, v in results if v is True)
    failed = sum(1 for _, v in results if v is False)
    warned = sum(1 for _, v in results if v is None)
    total = len(results)

    print()
    for name, status in results:
        if status is True:
            icon = PASS
        elif status is False:
            icon = FAIL
        else:
            icon = WARN
        print(f"    {icon}  {name}")

    print()
    print(f"  ----------------------------------------------")
    print(f"  Results: {passed} passed, {failed} failed, {warned} warnings / {total} total")
    print()

    if failed == 0:
        print(f"  ALL TESTS PASSED! Open http://localhost:{os.getenv('BOT_PORT', '7860')} in your browser.")
        print(f"     Click 'Start Talking' and ask about the news!")
    else:
        print(f"  Some tests failed. Fix the issues above and re-run.")
        print(f"     Run: python test_services.py")

    print()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print()
    print("  +============================================================+")
    print("  |                                                            |")
    print("  |   NEWS ANCHOR VOICE AI -- SERVICE DIAGNOSTICS              |")
    print("  |                                                            |")
    print("  |   Testing: Whisper - Ollama - Pipecat Bot (Kokoro Local)   |")
    print("  |                                                            |")
    print("  +============================================================+")

    start = time.perf_counter()

    try:
        test_whisper()
    except Exception as e:
        log(FAIL, f"Whisper test crashed: {e}")
        traceback.print_exc()

    try:
        test_ollama()
    except Exception as e:
        log(FAIL, f"Ollama test crashed: {e}")
        traceback.print_exc()

    try:
        test_piper()
    except Exception as e:
        log(FAIL, f"Piper test crashed: {e}")
        traceback.print_exc()

    try:
        test_bot()
    except Exception as e:
        log(FAIL, f"Bot test crashed: {e}")
        traceback.print_exc()

    try:
        test_e2e()
    except Exception as e:
        log(FAIL, f"E2E test crashed: {e}")
        traceback.print_exc()

    elapsed = (time.perf_counter() - start)
    print(f"\n  Total diagnostic time: {elapsed:.1f}s")

    print_summary()
