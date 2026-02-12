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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import (
    TextFrame, 
    TranscriptionFrame, 
    LLMMessagesFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    StartFrame,
    EndFrame
)

from loguru import logger
from dotenv import load_dotenv


# Pipecat Imports
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.frames.frames import LLMMessagesFrame, EndFrame, StartFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.aggregators.sentence import SentenceAggregator

import time

class TimingLogger(FrameProcessor):
    """Log frames to debug latency."""
    def __init__(self, prefix=""):
        super().__init__()
        self.prefix = prefix
        self.last_time = time.time()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        
        # Log INTERESTING events (ignore raw audio flood)
        if isinstance(frame, (TranscriptionFrame, TextFrame, LLMMessagesFrame)):
            content = str(frame)
            if hasattr(frame, "text"): content = frame.text
            logger.debug(f"⏱️ [{self.prefix}] {type(frame).__name__}: {content[:100]}...")
            
        elif isinstance(frame, (TTSStartedFrame, TTSStoppedFrame, StartFrame, EndFrame)):
             logger.debug(f"⏱️ [{self.prefix}] ⚡ EVENT: {type(frame).__name__}")
            
        await self.push_frame(frame, direction)



# Services
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import WhisperSTTService

# Audio / VAD
from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams
from pipecat.audio.vad.vad_analyzer import VADAnalyzer
from pipecat.processors.audio.vad_processor import VADProcessor

# Transport
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

# Frameworks
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIConfig

# Local imports
from news_service import (
    get_current_news_sync, 
    create_news_context_prompt, 
    fetch_live_news,
    update_news_cache,
    NEWS_CATEGORIES
)

# Custom Turn Analyzer (fallback if not available)
sys.path.append(os.path.join(os.path.dirname(__file__), '../local-bot'))
try:
    from bot_local import LocalSmartTurnAnalyzerV3
except ImportError:
    from pipecat.processors.aggregators.llm_response import LLMUserResponseAggregator
    class LocalSmartTurnAnalyzerV3(LLMUserResponseAggregator):
        pass


# Check for GPU/ONNX support
try:
    import onnxruntime as ort
    logger.debug(f"🚀 ONNX Runtime Providers: {ort.get_available_providers()}")
except ImportError:
    logger.warning("ONNX Runtime not found")

class FlexibleKokoroTTSService(KokoroTTSService):
    """Kokoro TTS with device selection and local model support."""
    def __init__(self, device: str = None, repo_id: str = "hexgrad/Kokoro-82M", **kwargs):
        super().__init__(**kwargs)
        if device or repo_id:
             logger.info(f"🔄 Re-initializing Kokoro pipeline on device: {device} | Repo: {repo_id}")
             try:
                 from kokoro import KPipeline
                 self._pipeline = KPipeline(lang_code=self._lang_code, repo_id=repo_id, device=device)
             except Exception as e:
                 logger.error(f"Failed to init Kokoro pipeline: {e}")

# Load environment variables
load_dotenv()

logger.remove()
logger.add(sys.stderr, level="DEBUG")

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
    """Create and run the Pipecat pipeline for News Anchor."""
    
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

    # Speech-to-Text (Local Faster-Whisper)
    # Using 'tiny' for maximum speed and responsiveness
    stt = WhisperSTTService(
        model="tiny",
        device="auto", 
        no_speech_prob=0.4
    )
    
    # ... (LLM setup remains same) ...
    # LLM (Ollama local) — streaming enabled for sentence-by-sentence TTS
    llm = OLLamaLLMService(
        model=os.getenv("LLM_MODEL", "gemma3:4b"),
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        params=OLLamaLLMService.InputParams(
            temperature=Config.llm_params.get("temperature", 0.3),
            max_tokens=Config.llm_params.get("max_tokens", 100),
        )
    )

    # Text-to-Speech (Kokoro - Local 82M Model)
    # Using standard service - it handles caching automatically
    tts = KokoroTTSService(
        voice_id="af_heart", 
    )

    # VAD Analyzer (Optimized for fast cut-off)
    # min_volume=0.2 avoids recording background noise as speech
    # stop_secs=0.3 ensures it stops listening quickly when you finish
    vad_analyzer = SileroVADAnalyzer(params=VADParams(
        stop_secs=0.3,
        start_secs=0.05,
        confidence=0.4,
        min_volume=0.2
    ))
    vad = VADProcessor(vad_analyzer=vad_analyzer)

    # Context with initial system prompt
    messages = [{"role": "system", "content": build_system_prompt()}]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    global global_context
    global_context = context

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
    
    # Sentence aggregator for smooth TTS
    # Splits on punctuation to stream audio sentence-by-sentence
    sentence_aggregator = SentenceAggregator()

    runner = PipelineRunner()
    
    task = PipelineTask(
        pipeline=Pipeline([
            transport.input(),
            vad,
            rtvi,
            TimingLogger("1. Mic Input"),
            stt,
            TimingLogger("2. After STT"),
            context_aggregator.user(),
            llm,
            TimingLogger("3. After LLM"),
            sentence_aggregator,
            tts,
            TimingLogger("4. After TTS"),
            transport.output(),
            context_aggregator.assistant()
        ]),
        params=PipelineParams(allow_interruptions=True)
    )

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
