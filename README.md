# 📰 NewsBot Studio — AI News Anchor

> A **Voice-to-Voice AI News Reporter** that listens, fetches live news, and speaks back — running 100% locally on your machine.

![Voice AI](https://img.shields.io/badge/AI-Voice%20Agent-red)
![Pipecat](https://img.shields.io/badge/Framework-Pipecat-blue)
![Local First](https://img.shields.io/badge/Privacy-100%25%20Local-green)
![Intel](https://img.shields.io/badge/Optimized-Intel%20AI%20PC-0071C5)

---

## ✨ What It Does

You **speak** to an AI News Anchor. It **listens**, **thinks**, and **speaks back** with the latest news — all in real-time, all running locally.

```
🎤 You speak  →  🧠 AI understands  →  📰 Fetches news  →  🔊 Speaks back
```

**No cloud APIs. No subscriptions. No data leaving your machine.**

---

## 🏗️ Architecture

```
🎤 Your Microphone
     │
     ▼
┌──────────────────┐
│  Faster-Whisper   │   Speech → Text (local, GPU-accelerated)
│  STT (base)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐    ┌─────────────────┐
│  Ollama LLM       │◄──►│ Google News RSS  │
│  (gemma3:4b)      │    │ (Free, live)    │
└────────┬─────────┘    └─────────────────┘
         │
         ▼
┌──────────────────┐
│  Kokoro TTS       │   Text → Natural Speech (local)
│  (af_heart voice) │
└────────┬─────────┘
         │
         ▼
🔊 AI Speaks Back
```

All services connected via **Pipecat AI** pipeline with **WebRTC** transport.

---

## 🚀 Getting Started

### Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.10+** | Runtime | [python.org](https://www.python.org/downloads/) |
| **Ollama** | Local LLM | [ollama.ai](https://ollama.ai/) |
| **Docker Desktop** | Whisper STT (fallback) | [docker.com](https://www.docker.com/) |
| **Git** | Clone this repo | [git-scm.com](https://git-scm.com/) |

### Step 1 — Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/SUMMIT-NEWS-ANCHOR-.git
cd SUMMIT-NEWS-ANCHOR-
```

Create a virtual environment:

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Step 2 — Pull the LLM Model

```bash
ollama pull gemma3:4b
```

> First pull downloads ~2.5 GB. After that it's cached locally.

### Step 3 — Configure (Optional)

```bash
copy .env.example .env
```

Edit `.env` if you want to customize:

```env
OLLAMA_URL=http://127.0.0.1:11434/v1
LLM_MODEL=gemma3:4b
BOT_PORT=7860
```

> **News API key is NOT required.** The bot fetches live news from Google News RSS for free. Mock headlines are used as fallback when offline.

### Step 4 — One-Click Start

**Windows:**
```bash
start.bat
```

**Manual start:**
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start the bot
python bot_news_anchor.py
```

### Step 5 — Open the Studio

Navigate to: **[http://localhost:7860](http://localhost:7860)**

Click **"Go Live"** and start talking! 🎙️

---

## 🎤 What to Say

| You Say | AI Responds |
|---------|-------------|
| "What are the top headlines?" | Summary of current top stories |
| "Tell me about tech news" | Latest technology updates |
| "How are the markets?" | Business and startup news |
| "Any sports updates?" | Cricket, IPL, sports highlights |
| "Tell me more about that story" | Expanded details |
| "What's happening in science?" | ISRO, research, discoveries |

---

## 🖥️ Studio Interface

The UI is a **broadcast control room** with three panels:

| Panel | What It Shows |
|-------|---------------|
| **Left Sidebar** | Navigation, connection status, Go Live button |
| **Center Stage** | AI Anchor orb (animates when speaking), live transcript, breaking news ticker |
| **Right Wire Panel** | Category filters (Top/Tech/Biz/Sport), live headlines, latency metrics |

**Features:**
- 🎨 Clean Apple-inspired light theme
- ◉ Animated AI orb with pulsing rings
- 📊 Real-time latency monitoring (STT / LLM / TTS)
- 📡 Live news wire with category switching
- 🔴 ON AIR badge activates on connection
- 📺 Breaking news ticker at the bottom

---

## 📁 Project Structure

```
SUMMIT-NEWS-ANCHOR-/
├── bot_news_anchor.py      # Main bot — pipeline, routes, prompts
├── news_service.py         # News fetching (RSS + mock fallback)
├── start.bat               # One-click startup script (Windows)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore rules
├── docker-compose.yml      # Docker services (optional)
├── news_data.json          # Cached news data (auto-generated)
│
└── ui/
    ├── index_news.html     # Studio UI (HTML + inline CSS)
    ├── app_news.js         # Frontend controller (WebRTC, RTVI)
    └── rtvi-client.js      # RTVI client library
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434/v1` |
| `LLM_MODEL` | Which Ollama model to use | `gemma3:4b` |
| `BOT_PORT` | Web server port | `7860` |
| `NEWS_API_KEY` | NewsAPI.org key (optional fallback) | *(empty — uses RSS)* |

### Anchor Personalities

Switch in the Control Room tab:

| Style | Behavior |
|-------|----------|
| 👔 **Pro** | Clear, authoritative, breaking-news tone |
| ☕ **Chill** | Friendly, conversational updates |
| ⚡ **Hype** | Energetic, morning-show energy |

### Custom Directives

Type anything in the "Directive Override" box:
- *"Speak like a 1920s radio announcer"*
- *"Focus only on AI and startup news"*
- *"Be sarcastic about everything"*

---

## 🔧 Tech Stack

| Component | Technology | Runs On |
|-----------|------------|---------|
| **Speech-to-Text** | Faster-Whisper (`base` model) | Local (auto-detects GPU) |
| **LLM** | Ollama + Gemma 3 4B | Local |
| **Text-to-Speech** | Kokoro TTS (`af_heart` voice, 82M params) | Local (OpenVINO/CUDA/CPU) |
| **Pipeline** | Pipecat AI | Local |
| **Transport** | WebRTC (SmallWebRTCTransport) | Browser ↔ Server |
| **News Source** | Google News RSS (free, unlimited) | Internet |
| **Fallback News** | Curated mock headlines | Offline |
| **Frontend** | Vanilla HTML/CSS/JS | Browser |
| **Server** | FastAPI + Uvicorn | Local |
| **VAD** | Silero VAD (400ms silence detection) | Local |

### Intel AI PC Optimizations

- **Kokoro TTS** auto-detects `OpenVINOExecutionProvider` for Intel Arc GPUs
- **Faster-Whisper** uses `auto` device selection (CUDA/CPU)
- Zero-cloud architecture — everything stays on your machine

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `500 Internal Server Error` | Make sure `ui/index_news.html` exists in the `ui/` folder |
| No audio output | Check browser speaker permissions, try Chrome |
| Microphone not detected | Allow microphone access in browser, check system settings |
| News says "Syncing..." forever | Check internet connection; offline mode uses mock headlines |
| Ollama not found | Install from [ollama.ai](https://ollama.ai/), run `ollama serve` |
| Model not found | Run `ollama pull gemma3:4b` |
| Slow first response | Kokoro TTS downloads ~300MB model on first run, subsequent runs are instant |
| `onnxruntime` errors | Try `pip install onnxruntime` (CPU) or `pip install onnxruntime-openvino` (Intel) |

---

## 📚 Resources

- [Pipecat AI Documentation](https://docs.pipecat.ai)
- [Ollama Models Library](https://ollama.ai/library)
- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Kokoro TTS](https://huggingface.co/hexgrad/Kokoro-82M)
- [Google News RSS](https://news.google.com/rss)

---

## 🤝 Credits

Built for **India AI Impact Summit 2026** — Intel AI Workshop, Session 5

| Role | Technology |
|------|------------|
| Pipeline Framework | [Pipecat AI](https://github.com/pipecat-ai/pipecat) by Daily |
| Speech-to-Text | [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) |
| Language Model | [Ollama](https://ollama.ai/) + Gemma 3 4B |
| Text-to-Speech | [Kokoro TTS](https://huggingface.co/hexgrad/Kokoro-82M) |
| News Data | Google News RSS |

---

Made with 🎙️ for voice AI education
