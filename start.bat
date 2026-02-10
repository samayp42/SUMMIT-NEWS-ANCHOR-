@echo off
setlocal EnableDelayedExpansion

:: Navigate to this script's directory (handles spaces & brackets in path)
cd /d "%~dp0"

title NEWS ANCHOR VOICE AI
color 0B

echo.
echo  ================================================================
echo  =                                                              =
echo  =   NEWS ANCHOR VOICE AI - ONE CLICK STARTUP                  =
echo  =   India AI Summit 2025 - Session 5                          =
echo  =                                                              =
echo  =   [1] Ollama LLM    gemma3:4b       Terminal   Port 11434   =
echo  =   [2] Whisper STT   tiny            Docker     Port 8000    =
echo  =   [3] Kokoro TTS    af_heart        In-Process (Local)   =
echo  =   [4] Pipecat Bot   FastAPI         Terminal   Port 7860    =
echo  =                                                              =
echo  ================================================================
echo.

:: ============================================================
:: STEP 0: Python Environment
:: ============================================================
echo [SETUP] Checking Python environment...
if exist "venv\Scripts\activate.bat" (
    echo         Found existing venv.
    call "venv\Scripts\activate.bat"
) else (
    echo         Creating virtual environment...
    python -m venv venv
    call "venv\Scripts\activate.bat"
    echo         Installing dependencies...
    pip install -r requirements.txt
)
echo         Environment ready.
echo.

:: ============================================================
:: STEP 1: Ollama LLM (Native Terminal)
:: ============================================================
echo [1/4] Ollama LLM Server...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "!ERRORLEVEL!"=="0" (
    echo       Already running.
) else (
    echo       Starting Ollama...
    start "Ollama LLM" cmd /k "title Ollama LLM - gemma3:4b && color 0A && ollama serve"
    timeout /t 5 >nul
)

:: Check model
echo       Checking gemma3:4b model...
ollama list 2>nul | find /I "gemma3:4b" >nul
if "!ERRORLEVEL!"=="0" (
    echo       Model ready.
) else (
    echo       Pulling gemma3:4b... (first time only, please wait)
    ollama pull gemma3:4b
    echo       Model downloaded.
)
echo.

:: ============================================================
:: STEP 2: Whisper STT (Docker)
:: ============================================================
echo [2/4] Whisper STT Server (Docker)...

:: Check if Docker is available
docker info >nul 2>&1
if "!ERRORLEVEL!" NEQ "0" (
    echo       ERROR: Docker is not running!
    echo       Please start Docker Desktop and try again.
    pause
    exit /b 1
)

:: Remove old container if exists, start fresh
docker rm -f workshop-whisper >nul 2>&1

echo       Starting Whisper container...
docker run -d --name workshop-whisper -p 8000:8000 ^
    -e "WHISPER__MODEL=tiny" ^
    -e "WHISPER__INFERENCE_DEVICE=cpu" ^
    -e "WHISPER__COMPUTE_TYPE=int8" ^
    -e "WHISPER__MODEL_TTL=-1" ^
    fedirz/faster-whisper-server:latest-cpu >nul 2>&1

if "!ERRORLEVEL!"=="0" (
    echo       Whisper container started on port 8000.
) else (
    echo       Whisper may already be running, checking...
)

:: Wait for Whisper to be ready
echo       Waiting for Whisper to load model...
timeout /t 10 >nul
echo       Whisper STT ready.
echo.

:: ============================================================
:: STEP 3: Kokoro TTS (In-Process)
:: ============================================================
echo [3/4] Kokoro TTS (Preparing)...

:: Stop Piper container if running (cleanup)
docker rm -f workshop-piper >nul 2>&1

echo       Kokoro TTS runs inside the bot.
echo       First run will download ~300MB model automatically.
echo       Voice: af_heart (High Quality American Female)
echo.

:: ============================================================
:: STEP 4: Launch Pipecat Bot
:: ============================================================
echo [4/4] Starting Pipecat News Anchor Bot...
echo.

set WHISPER_URL=http://localhost:8000/v1
set OLLAMA_URL=http://localhost:11434/v1
set LLM_MODEL=gemma3:4b
set BOT_PORT=7860

echo  ================================================================
echo.
echo    ALL SERVICES READY!
echo.
echo    Browser:  http://localhost:7860
echo.
echo    Pipeline: Mic - Whisper(8000) - Gemma3(11434) - Kokoro - Speaker
echo.
echo  ================================================================
echo.

timeout /t 2 >nul
python bot_news_anchor.py

echo.
echo  Bot stopped.
pause
