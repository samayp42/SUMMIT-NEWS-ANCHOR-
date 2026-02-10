# 📰 News Anchor Voice AI - Session 5
## India AI Summit 2025 - Pipecat Voice AI Workshop

Build a **Voice-to-Voice AI News Reporter** that listens to your questions, fetches real-time news, and responds with natural speech — all running locally on Intel AI PC!

![Voice AI](https://img.shields.io/badge/AI-Voice%20Agent-red)
![Pipecat](https://img.shields.io/badge/Framework-Pipecat-blue)
![Local First](https://img.shields.io/badge/Privacy-Local%20Only-green)

---

## 🎯 What Makes This Different

| Previous Sessions | Session 5 |
|-------------------|-----------|
| Text input/output | **Voice input/output** |
| Type and read | **Speak and listen** |
| Single modality | **Multi-modal (STT + LLM + TTS)** |

**This is the first voice-to-voice AI session!**

---

## 🏗️ Architecture

```
🎤 Your Voice
    │
    ▼
┌─────────────────┐
│   WHISPER STT   │  (Speech-to-Text)
│   (Local)       │  Your voice → Text
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────┐
│   OLLAMA LLM    │◄──►│  NEWS API   │
│   (Local)       │    │  (Internet) │
└────────┬────────┘    └─────────────┘
         │
         ▼
┌─────────────────┐
│   PIPER TTS     │  (Text-to-Speech)
│   (Local)       │  Text → AI Voice
└────────┬────────┘
         │
         ▼
🔊 AI Speaks Back
```

---

## 🚀 Quick Start

### 1. Ensure Docker Services are Running

```bash
docker-compose up -d
```

### 2. Pull the LLM Model (if not already done)

```bash
docker exec -it workshop-ollama ollama pull llama3.2:1b
```

### 3. (Optional) Set News API Key

Get a free key from [newsapi.org](https://newsapi.org/) and add to `.env`:

```bash
cp .env.example .env
# Edit .env and add your NEWS_API_KEY
```

> **Note:** Mock headlines will be used if no API key is set. Perfect for offline demos!

### 4. Run the News Anchor Bot

```bash
# Using uv (recommended)
uv run bot_news_anchor.py

# Or using python
python bot_news_anchor.py
```

### 5. Open the UI

Navigate to: **http://localhost:7860/**

Click "Start Talking" and ask about the news! 🎙️

---

## 🎤 Sample Voice Commands

Try saying:

| You Say | AI Responds |
|---------|-------------|
| "What are the top headlines today?" | Summary of current top stories |
| "Tell me about technology news" | Latest tech updates |
| "How are the markets doing?" | Business and market summary |
| "Any sports updates?" | Latest sports news |
| "What's happening in the world?" | International news briefing |
| "Tell me more about that first story" | Expanded details |

---

## 🎛️ Features

### 📂 News Categories
Switch between different news types:
- 📰 Headlines (Top Stories)
- 💻 Technology
- 📈 Business & Markets
- ⚽ Sports
- 🎬 Entertainment
- 🔬 Science

### 🎭 Anchor Personalities
Choose your news anchor style:
- 👔 **Professional** - Clear, authoritative reporting
- 😊 **Casual** - Friendly, conversational updates
- 🎉 **Enthusiastic** - Energetic morning show style

### ⚡ Real-Time Updates
- Live news fetching from NewsAPI
- Instant category switching
- Real-time prompt updates

### 📊 Performance Metrics
- STT Latency (Listening)
- LLM Latency (Thinking)
- TTS Latency (Speaking)

---

## 📁 Project Structure

```
workshop/
├── bot_news_anchor.py     # Main News Anchor bot
├── news_service.py        # News API integration
├── ui/
│   ├── index_news.html    # News Anchor UI
│   ├── app_news.js        # News Anchor controller
│   └── styles_news.css    # News theme styles
├── knowledge_base/
│   ├── news_reporting.txt     # Journalism basics
│   └── india_news_context.txt # India-specific context
├── docker-compose.yml     # Docker services
└── requirements.txt       # Python dependencies
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEWS_API_KEY` | NewsAPI.org API key | (uses mock data) |
| `LLM_MODEL` | Ollama model | `llama3.2:1b` |
| `TTS_VOICE` | Piper voice | `en_US-lessac-medium` |
| `BOT_PORT` | Server port | `7860` |

### Custom Instructions

Add custom behavior in the Settings panel:
- "Focus on positive news"
- "Always mention India-related implications"
- "Use more technical vocabulary"

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| No audio output | Check browser permissions, speaker volume |
| Microphone not working | Check browser mic permissions |
| News not loading | Check internet connection, API key |
| Slow responses | Ensure Docker has enough resources |
| LLM timeout | Run `ollama pull llama3.2:1b` again |

### Check Docker Services

```bash
docker ps
# Should show: workshop-whisper, workshop-ollama, workshop-piper
```

---

## 🎓 Learning Outcomes

After this session, you will understand:

1. ✅ Voice AI pipeline architecture (STT → LLM → TTS)
2. ✅ Pipecat framework for voice applications
3. ✅ Real-time API integration with voice AI
4. ✅ Building conversational voice agents
5. ✅ Privacy benefits of local voice AI

---

## 💡 Use Cases for Voice AI

| Domain | Application |
|--------|-------------|
| **News & Media** | Personal news anchor, briefings |
| **Accessibility** | Voice UI for visually impaired |
| **Smart Home** | Voice-controlled assistants |
| **Customer Service** | Voice support agents |
| **Automotive** | In-car voice interfaces |
| **Elderly Care** | Companion bots, reminders |

---

## 📚 Resources

- [Pipecat Documentation](https://docs.pipecat.ai)
- [Ollama Models](https://ollama.ai/library)
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Piper TTS](https://github.com/rhasspy/piper)
- [NewsAPI](https://newsapi.org/)

---

## 🤝 Credits

Built for **India AI Summit 2025** Intel Workshop

- **Framework**: Pipecat by Daily
- **STT**: Faster Whisper
- **LLM**: Ollama with Llama 3.2
- **TTS**: Piper
- **News**: NewsAPI.org

---

Made with 🎙️ for voice AI education
