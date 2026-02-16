"""
News Anchor Voice AI Agent
===========================
India AI Impact Summit 2026 - Session 5: Pipecat Voice AI

A real-time voice AI news reporter that:
- Listens to your spoken questions (Whisper STT)
- Understands your intent (Ollama LLM via native /api/chat)
- Fetches real-time news from APIs
- Responds with natural speech (Kokoro TTS)

Run with: python bot_news_anchor.py
Open: http://localhost:7860/
"""

import asyncio
import os
import sys
import json
import time
import aiohttp
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import (
    Frame,
    LLMMessagesFrame,
    LLMContextFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    LLMUpdateSettingsFrame,
)

from loguru import logger
from dotenv import load_dotenv


# Pipecat Imports
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)

# Services
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService

# Audio / VAD
from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams

# Transport
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

# Local imports
from news_service import (
    get_current_news_sync,
    create_news_context_prompt,
    fetch_live_news,
    update_news_cache,
    NEWS_CATEGORIES
)


# ============================================================
# CUSTOM OLLAMA LLM SERVICE — Native /api/chat (fast, no OpenAI overhead)
# ============================================================

class OllamaDirectLLMService(FrameProcessor):
    """Direct Ollama LLM using native /api/chat endpoint for maximum speed.

    Bypasses the OpenAI-compatible /v1/chat/completions endpoint entirely.
    Uses aiohttp for streaming NDJSON responses with minimal overhead.
    """

    def __init__(
        self,
        *,
        model: str = "gemma3:4b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
        num_predict: int = 80,
        num_ctx: int = 2048,
    ):
        super().__init__()
        self._model = model
        # Strip /v1 suffix if present — we use the native API
        self._base_url = base_url.rstrip("/").replace("/v1", "")
        self._temperature = temperature
        self._num_predict = num_predict
        self._num_ctx = num_ctx
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, sock_connect=5)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def cleanup(self):
        if self._session and not self._session.closed:
            await self._session.close()
        await super().cleanup()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        context = None
        if isinstance(frame, LLMContextFrame):
            context = frame.context
        elif isinstance(frame, LLMMessagesFrame):
            context = frame
        elif isinstance(frame, LLMUpdateSettingsFrame):
            settings = frame.settings
            if "temperature" in settings:
                self._temperature = settings["temperature"]
            if "num_predict" in settings:
                self._num_predict = settings["num_predict"]
            return
        else:
            await self.push_frame(frame, direction)
            return

        if context:
            await self.push_frame(LLMFullResponseStartFrame())
            try:
                await self._stream_ollama_chat(context)
            except Exception as e:
                logger.error(f"Ollama LLM error: {e}")
            finally:
                await self.push_frame(LLMFullResponseEndFrame())

    async def _stream_ollama_chat(self, context):
        """Stream tokens from Ollama native /api/chat endpoint."""
        await self._ensure_session()

        # Extract messages from context
        if isinstance(context, LLMContext):
            messages = context.get_messages()
        elif hasattr(context, "messages"):
            messages = context.messages
        else:
            messages = [{"role": "user", "content": str(context)}]

        # Clean messages for Ollama native API (only role + content)
        clean_messages = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                clean_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        payload = {
            "model": self._model,
            "messages": clean_messages,
            "stream": True,
            "options": {
                "temperature": self._temperature,
                "num_predict": self._num_predict,
                "num_ctx": self._num_ctx,
            }
        }

        url = f"{self._base_url}/api/chat"
        t0 = time.monotonic()
        first_token = True

        async with self._session.post(url, json=payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"Ollama /api/chat returned {resp.status}: {error_text}")
                return

            async for line in resp.content:
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if data.get("done", False):
                    elapsed = time.monotonic() - t0
                    logger.debug(f"Ollama complete in {elapsed:.2f}s")
                    break

                token = data.get("message", {}).get("content", "")
                if token:
                    if first_token:
                        ttfb = time.monotonic() - t0
                        logger.info(f"LLM TTFB: {ttfb:.3f}s")
                        first_token = False
                    await self.push_frame(LLMTextFrame(token))


# Load environment variables
load_dotenv()

logger.remove()
logger.add(sys.stderr, level="DEBUG")

# ============================================================
# PRE-LOAD AI MODELS (one-time cost at server startup)
# ============================================================
# Models are loaded ONCE here instead of on every "Go Live" click.
# This moves the 10-15s model loading cost to server boot time.

logger.info("⏳ Pre-loading AI models (one-time startup cost)...")

_shared_stt = None
_shared_tts = None
_shared_vad_analyzer = None

try:
    _shared_stt = WhisperSTTService(model="tiny", device="auto", no_speech_prob=0.4)
    logger.info("  ✓ Whisper STT loaded")
except Exception as e:
    logger.error(f"  ✗ Whisper STT failed to pre-load: {e}")

try:
    _shared_tts = KokoroTTSService(voice_id="af_heart")
    logger.info("  ✓ Kokoro TTS loaded")
except Exception as e:
    logger.error(f"  ✗ Kokoro TTS failed to pre-load: {e}")

try:
    _shared_vad_analyzer = SileroVADAnalyzer(params=VADParams(
        stop_secs=0.3,
        start_secs=0.05,
        confidence=0.4,
        min_volume=0.2
    ))
    logger.info("  ✓ Silero VAD loaded")
except Exception as e:
    logger.error(f"  ✗ Silero VAD failed to pre-load: {e}")

logger.info("✅ All AI models pre-loaded! Go Live will be fast.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount UI
ui_path = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=ui_path), name="ui")


@app.on_event("startup")
async def warmup_ollama():
    """Pre-warm Ollama so the LLM model is loaded into VRAM before first request.
    Without this, the first voice interaction waits 10-30s for model loading."""
    try:
        import aiohttp
        # Use native Ollama API for warmup
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
        base_url = ollama_url.replace("/v1", "").rstrip("/")
        logger.info(f"⏳ Warming up Ollama LLM at {base_url}...")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/api/generate",
                json={
                    "model": os.getenv("LLM_MODEL", "gemma3:4b"),
                    "prompt": "hi",
                    "stream": False
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    logger.info("  ✓ Ollama LLM warmed up (model loaded in VRAM)")
                else:
                    logger.warning(f"  Ollama warmup got status {resp.status}")
    except Exception as e:
        logger.warning(f"  Ollama warmup failed (is Ollama running?): {e}")


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """Configuration state for the News Anchor bot."""

    # Current news category
    news_category = "headlines"

    # News cache (refreshed periodically)
    cached_news = {}
    last_news_update = None

    # Features
    features = {
        "live_news": True,      # Fetch real news from API
        "mock_fallback": True,  # Use mock data if API fails
        "detailed_mode": False  # Provide longer explanations
    }

    # Custom instruction overlay
    custom_prompt = ""

    # LLM parameters
    llm_params = {
        "temperature": 0.3,  # Slightly creative for natural speech
        "max_tokens": 100    # Longer for news summaries
    }

    # Anchor personality (can be customized)
    anchor_style = "professional"  # professional, casual, enthusiastic

    @classmethod
    def get_news(cls, category: str = None):
        """Get current news for specified category."""
        cat = category or cls.news_category
        return get_current_news_sync(cat)

    @classmethod
    async def refresh_news(cls, category: str = None):
        """Refresh news from API."""
        cat = category or cls.news_category
        await update_news_cache(cat)
        cls.last_news_update = datetime.now()


# Global context for real-time updates
global_context = None


# ============================================================
# NEWS ANCHOR IDENTITY
# ============================================================

ANCHOR_PERSONALITIES = {
    "professional": """
VOICE & STYLE:
- Speak like a professional news anchor
- Clear, articulate, and authoritative
- Use formal but accessible language
- Structure updates with "First...", "Additionally...", "Finally..."
""",
    "casual": """
VOICE & STYLE:
- Speak like a friendly neighborhood news reporter
- Warm, conversational, and approachable
- Use everyday language
- Add personal touches like "Interesting development here..."
""",
    "enthusiastic": """
VOICE & STYLE:
- Speak like an energetic morning show host
- Upbeat, dynamic, and engaging
- Show excitement about interesting stories
- Use phrases like "Exciting news!", "You'll love this..."
"""
}

CORE_ANCHOR_PROMPT = """
IDENTITY:
You represent "NewsBot" - a fast, direct AI News Anchor.

MISSION:
- Deliver news with speed and accuracy.
- NO filler phrases ("Sure", "I can help", "Let me check").
- Get STRAIGHT to the headline.
- Maximum 2-3 sentences per update.
- Use active voice. Be punchy.
- NEVER READ DATES, TIMES, OR URLS. (e.g. "Fri, 16 Jan 2026").
- Summarize the story, don't read the headline verbatim.
- "According to [Source]..." is good.

STYLE:
- Crisp.
- Deliver news with speed and accuracy.
- Use SHORT, PUNCHY SENTENCES. Avoid complex clauses.
- Pause frequently (use periods).
- Like a breaking news ticker tape spoken aloud.
- If user asks a question, answer immediately with facts.
"""

def get_time_greeting() -> str:
    """Get appropriate greeting based on time of day."""
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


def build_system_prompt() -> str:
    """Build the complete system prompt for the News Anchor."""

    # 1. Core identity
    prompt = CORE_ANCHOR_PROMPT

    # 2. Personality style
    style = ANCHOR_PERSONALITIES.get(Config.anchor_style, ANCHOR_PERSONALITIES["professional"])
    prompt += f"\n{style}\n"

    # 3. Custom instructions (if any)
    if Config.custom_prompt and len(Config.custom_prompt.strip()) > 0:
        prompt += f"\nCUSTOM DIRECTIVE:\n{Config.custom_prompt}\n"

    # 4. Live news context
    if Config.features.get("live_news", True):
        news_context = create_news_context_prompt(Config.news_category)
        prompt += f"\n{news_context}\n"

    # 5. Time context
    now = datetime.now()
    prompt += f"\nCURRENT TIME: {now.strftime('%B %d, %Y at %I:%M %p')}\n"
    prompt += f"Use this for time-appropriate greetings (Good {get_time_greeting()}!)\n"

    return prompt


def update_prompt_if_needed(context: LLMContext):
    """Update context's system prompt if config changed."""
    new_prompt = build_system_prompt()
    if context.messages and context.messages[0]["role"] == "system":
        context.messages[0]["content"] = new_prompt
        logger.info("📝 News Anchor prompt updated!")


# ============================================================
# BOT PIPELINE
# ============================================================

async def run_bot_impl(connection):
    """Create and run the Pipecat pipeline for News Anchor.

    Uses pre-loaded STT/TTS/VAD models for instant startup.
    Only transport, context, and LLM are created per-connection.
    """

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            video_out_enabled=False,
            video_in_enabled=False,
            audio_out_sample_rate=24000,
            audio_in_sample_rate=16000,
        )
    )

    # STT — use pre-loaded Whisper model (instant) or fallback to fresh load
    if _shared_stt is not None:
        stt = _shared_stt
    else:
        logger.warning("Pre-loaded STT not available, loading fresh...")
        stt = WhisperSTTService(model="tiny", device="auto", no_speech_prob=0.4)

    # LLM (Ollama) — Direct native /api/chat, no OpenAI overhead
    llm = OllamaDirectLLMService(
        model=os.getenv("LLM_MODEL", "gemma3:4b"),
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        temperature=Config.llm_params.get("temperature", 0.3),
        num_predict=Config.llm_params.get("max_tokens", 80),
        num_ctx=2048,
    )

    # TTS — use pre-loaded Kokoro model (instant) or fallback to fresh load
    if _shared_tts is not None:
        tts = _shared_tts
    else:
        logger.warning("Pre-loaded TTS not available, loading fresh...")
        tts = KokoroTTSService(voice_id="af_heart")

    # VAD — use pre-loaded analyzer or create fresh
    if _shared_vad_analyzer is not None:
        vad_analyzer = _shared_vad_analyzer
    else:
        logger.warning("Pre-loaded VAD not available, loading fresh...")
        vad_analyzer = SileroVADAnalyzer(params=VADParams(
            stop_secs=0.3, start_secs=0.05, confidence=0.4, min_volume=0.2
        ))

    # Context with initial system prompt (per-connection)
    messages = [{"role": "system", "content": build_system_prompt()}]
    context = LLMContext(messages)

    # VAD integrated into user aggregator — this is critical for turn detection.
    # Without vad_analyzer here, the aggregator never knows when you stop speaking
    # and never triggers the LLM.
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad_analyzer),
    )

    global global_context
    global_context = context

    runner = PipelineRunner(handle_sigint=False)

    task = PipelineTask(
        pipeline=Pipeline([
            transport.input(),       # WebRTC audio in
            stt,                     # Whisper STT
            user_aggregator,         # Accumulates user speech, triggers LLM on turn end
            llm,                     # Ollama native /api/chat
            tts,                     # Kokoro TTS (handles sentence aggregation internally)
            transport.output(),      # WebRTC audio out
            assistant_aggregator,    # Tracks assistant responses for context
        ]),
        params=PipelineParams(allow_interruptions=True)
    )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    await runner.run(task)


# ============================================================
# API ROUTES
# ============================================================

@app.get("/")
async def get_client():
    """Serve the main UI."""
    return FileResponse(ui_path / "index_news.html")


@app.get("/api/config")
async def get_config():
    """Return current configuration."""
    return {
        "newsCategory": Config.news_category,
        "features": Config.features,
        "llmParams": Config.llm_params,
        "anchorStyle": Config.anchor_style,
        "customPrompt": Config.custom_prompt,
        "categories": NEWS_CATEGORIES,
        "lastNewsUpdate": Config.last_news_update.isoformat() if Config.last_news_update else None
    }


@app.post("/api/config")
async def update_config(request: Request):
    """Update configuration."""
    data = await request.json()

    if "newsCategory" in data:
        Config.news_category = data["newsCategory"]
        # Refresh news for this category
        await Config.refresh_news(data["newsCategory"])

    if "customPrompt" in data:
        Config.custom_prompt = data["customPrompt"]

    if "features" in data:
        Config.features.update(data["features"])

    if "llmParams" in data:
        Config.llm_params.update(data["llmParams"])

    if "anchorStyle" in data:
        if data["anchorStyle"] in ANCHOR_PERSONALITIES:
            Config.anchor_style = data["anchorStyle"]

    # Real-time prompt update
    if global_context:
        try:
            update_prompt_if_needed(global_context)
            logger.info("⚡ Real-time prompt update triggered!")
        except Exception as e:
            logger.error(f"Failed to update context: {e}")

    return {
        "status": "ok",
        "config": {
            "newsCategory": Config.news_category,
            "anchorStyle": Config.anchor_style,
            "features": Config.features
        }
    }


@app.get("/api/news")
async def get_news(category: str = "headlines"):
    """Get news for a category — always tries fresh fetch first."""
    articles = []
    source = "mock"

    if Config.features.get("live_news"):
        try:
            articles = await fetch_live_news(category)
            if articles:
                source = "live"
                # Update cache for future use
                await update_news_cache(category)
                Config.last_news_update = datetime.now()
        except Exception as e:
            logger.warning(f"Live news fetch failed: {e}")

    if not articles:
        articles = get_current_news_sync(category)
        source = "cache/mock"

    logger.info(f"📰 Serving {len(articles)} articles [{source}] for '{category}'")

    return {
        "category": category,
        "articles": articles,
        "timestamp": datetime.now().isoformat(),
        "source": source
    }


@app.post("/api/news/refresh")
async def refresh_news(request: Request):
    """Manually refresh news cache."""
    data = await request.json()
    category = data.get("category", Config.news_category)

    await Config.refresh_news(category)

    return {
        "status": "ok",
        "category": category,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/offer")
async def sdp_offer(request: Request):
    """Handle WebRTC offer for voice connection."""
    data = await request.json()
    sdp = data['sdp']
    type = data['type']

    # Create new WebRTC connection
    conn = SmallWebRTCConnection()

    # Initialize with the incoming offer
    await conn.initialize(sdp, type)

    # Get the answer
    answer = conn.get_answer()

    # Start the bot pipeline in the background
    asyncio.create_task(run_bot_impl(conn))

    return answer


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BOT_PORT", 7860))

    logger.info(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   📰 NEWS ANCHOR VOICE AI                                 ║
    ║   India AI Impact Summit 2026 - Session 5                        ║
    ║                                                           ║
    ║   Open: http://localhost:{port}/                          ║
    ║                                                           ║
    ║   Voice Pipeline:                                         ║
    ║   🎤 STT (Whisper) → 🧠 LLM (Ollama) → 🗣️ TTS (Kokoro)    ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host="0.0.0.0", port=port)
