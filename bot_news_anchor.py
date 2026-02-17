"""
News Anchor Voice AI Agent
===========================
India AI Impact Summit 2026 - Session 5: Pipecat Voice AI

A real-time voice AI news reporter that:
- Listens to your spoken questions (Whisper STT)
- Understands your intent (Ollama LLM)
- Fetches real-time news from APIs
- Responds with natural speech (Piper TTS)

Run with: python bot_news_anchor.py
Open: http://localhost:7860/
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from loguru import logger
from dotenv import load_dotenv

# Pipecat Imports
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams

# Services
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService

# Context aggregation (universal, non-deprecated API for pipecat >=0.0.102)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.frames.frames import LLMRunFrame, TTSSpeakFrame

# Audio / VAD
from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams

# Transport
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

# NOTE: RTVIProcessor + RTVIObserver are auto-added by PipelineTask in pipecat 0.0.102.
# Do NOT import or add them manually — it causes duplicate event firing.

# Local imports
from news_service import (
    get_current_news_sync, 
    create_news_context_prompt, 
    fetch_live_news,
    update_news_cache,
    NEWS_CATEGORIES
)

# Load environment variables
load_dotenv()

logger.remove()

def _vad_spam_filter(record):
    """Filter out the extremely noisy VAD set_params log lines."""
    return "pipecat.audio.vad" not in record["name"]

logger.add(sys.stderr, level="INFO", filter=_vad_spam_filter)
logger.add("log.txt", level="DEBUG", rotation="5 MB", retention="3 days", filter=_vad_spam_filter)

# ============================================================
# PRE-LOAD AI MODELS (one-time cost at server startup)
# ============================================================
# Models are loaded ONCE here instead of on every "Go Live" click.
# This moves the 10-15s model loading cost to server boot time.

logger.info("⏳ Pre-loading AI models (one-time startup cost)...")

_shared_stt = None
_shared_tts = None

try:
    _shared_stt = WhisperSTTService(model="tiny", device="cpu", compute_type="int8", no_speech_prob=0.4)
    logger.info("  ✓ Whisper STT loaded")
except Exception as e:
    logger.error(f"  ✗ Whisper STT failed to pre-load: {e}")

try:
    _shared_tts = KokoroTTSService(voice_id="af_heart")
    logger.info("  ✓ Kokoro TTS loaded")
except Exception as e:
    logger.error(f"  ✗ Kokoro TTS failed to pre-load: {e}")

logger.info("✅ AI models pre-loaded! Go Live will be fast.")

# Peer connection tracking for WebRTC lifecycle management
pcs_map: Dict[str, SmallWebRTCConnection] = {}


async def _warmup_ollama():
    """Pre-warm Ollama so the LLM model is loaded into VRAM before first request."""
    try:
        import aiohttp
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm up Ollama. Shutdown: clean up peer connections."""
    await _warmup_ollama()
    yield
    coros = [pc.disconnect() for pc in pcs_map.values()]
    await asyncio.gather(*coros)
    pcs_map.clear()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount UI
ui_path = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=ui_path), name="ui")


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

INTERACTION RULES:
- ALWAYS end every response with a short engaging question to keep the conversation going.
- Examples: "Want to hear more?", "Shall I dive deeper into this?", "What topic interests you next?"
- This is a live real-time conversation. Keep it flowing naturally.
- When the user responds, acknowledge briefly then deliver the next update.

STYLE:
- Crisp.
- Deliver news with speed and accuracy.
- Use SHORT, PUNCHY SENTENCES. Avoid complex clauses.
- Pause frequently (use periods).
- Like a breaking news ticker tape spoken aloud.
- If user asks a question, answer immediately with facts.
- Always end with a question to invite the user to respond.
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


def update_prompt_if_needed(context_aggregator):
    """Update context's system prompt if config changed.
    
    Works with LLMContextAggregatorPair from pipecat's universal API.
    The user aggregator holds the LLM context with messages.
    """
    new_prompt = build_system_prompt()
    try:
        context = context_aggregator.user()._context
        if context.messages and context.messages[0]["role"] == "system":
            context.messages[0]["content"] = new_prompt
            logger.info("📝 News Anchor prompt updated!")
    except Exception as e:
        logger.warning(f"Could not update prompt via context_aggregator: {e}")


# ============================================================
# BOT PIPELINE
# ============================================================

async def run_bot_impl(connection):
    """Create and run the Pipecat pipeline for News Anchor.

    Pipecat 0.0.102 architecture:
    - VAD inside LLMUserAggregatorParams (TransportParams.vad_analyzer is deprecated)
    - PipelineTask auto-adds RTVIProcessor + RTVIObserver (do NOT add manually)
    - SmallWebRTCTransport events: on_client_connected, on_client_disconnected
    - Greeting triggered via LLMRunFrame() through the user aggregator
    """

    # Transport — no VAD here (deprecated in 0.0.102, moved to LLMUserAggregatorParams)
    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            audio_out_sample_rate=24000,
            audio_in_sample_rate=16000,
        ),
    )

    # STT — use pre-loaded Whisper model (instant) or fallback to fresh load
    if _shared_stt is not None:
        stt = _shared_stt
    else:
        logger.warning("Pre-loaded STT not available, loading fresh...")
        stt = WhisperSTTService(model="tiny", device="cpu", compute_type="int8", no_speech_prob=0.4)

    # LLM (Ollama) — lightweight HTTP client, created fresh to pick up config changes
    llm = OLLamaLLMService(
        model=os.getenv("LLM_MODEL", "gemma3:4b"),
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        params=OLLamaLLMService.InputParams(
            temperature=Config.llm_params.get("temperature", 0.3),
            max_tokens=Config.llm_params.get("max_tokens", 100),
        )
    )

    # TTS — use pre-loaded Kokoro model (instant) or fallback to fresh load
    if _shared_tts is not None:
        tts = _shared_tts
    else:
        logger.warning("Pre-loaded TTS not available, loading fresh...")
        tts = KokoroTTSService(voice_id="af_heart")

    # VAD — placed in LLMUserAggregatorParams (the non-deprecated location in 0.0.102)
    vad = SileroVADAnalyzer(params=VADParams(
        stop_secs=0.3,
        start_secs=0.05,
        confidence=0.5,
        min_volume=0.3,
    ))

    # Context with initial system prompt (per-connection)
    messages = [{"role": "system", "content": build_system_prompt()}]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad),
    )

    global global_context
    global_context = context_aggregator

    # Pipeline — input → stt → user_agg → llm → tts → output → assistant_agg
    # NOTE: No manual RTVIProcessor here. PipelineTask auto-prepends one.
    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # --- Lifecycle event handlers ---
    # PipelineTask auto-registers on_client_ready to call set_bot_ready().
    # We add a SECOND handler to also trigger the greeting.

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        """Client is connected and ready — instant TTS greeting then LLM news summary."""
        logger.info("Client ready — sending instant greeting + news summary")
        greeting = get_time_greeting()
        # Instant fixed greeting via TTS (no LLM latency)
        await task.queue_frames([
            TTSSpeakFrame(
                text=f"Good {greeting}! Welcome to NewsBot, your live AI news anchor. "
                     f"Here are today's top stories."
            ),
            # Then trigger LLM for the actual news summary
            LLMRunFrame(),
        ])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, webrtc_connection):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
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
async def sdp_offer(request: Request, background_tasks: BackgroundTasks):
    """Handle WebRTC offer for voice connection.
    
    Follows the pipecat reference pattern:
    - Tracks peer connections in pcs_map for lifecycle management
    - Uses BackgroundTasks (not asyncio.create_task) for proper cleanup
    - Supports reconnection via pc_id
    """
    data = await request.json()
    pc_id = data.get("pc_id")

    if pc_id and pc_id in pcs_map:
        # Reconnection to existing session
        pipecat_connection = pcs_map[pc_id]
        logger.info(f"Reusing existing connection for pc_id: {pc_id}")
        await pipecat_connection.renegotiate(
            sdp=data["sdp"],
            type=data["type"],
            restart_pc=data.get("restart_pc", False),
        )
    else:
        # New connection
        pipecat_connection = SmallWebRTCConnection()
        await pipecat_connection.initialize(sdp=data["sdp"], type=data["type"])

        @pipecat_connection.event_handler("closed")
        async def handle_disconnected(webrtc_connection: SmallWebRTCConnection):
            logger.info(f"Discarding peer connection for pc_id: {webrtc_connection.pc_id}")
            pcs_map.pop(webrtc_connection.pc_id, None)

        background_tasks.add_task(run_bot_impl, pipecat_connection)

    answer = pipecat_connection.get_answer()
    pcs_map[answer["pc_id"]] = pipecat_connection
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
