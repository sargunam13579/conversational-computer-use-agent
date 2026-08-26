# NEXUS Installation Guide

This guide provides comprehensive, step-by-step instructions for installing and setting up the **NEXUS Autonomous AI Agent** on Windows, Linux, and macOS.

---

## 1. System Requirements

### Hardware
- **Processor**: Intel Core i5 / AMD Ryzen 5 or higher (Apple Silicon M1/M2/M3 on macOS)
- **RAM**: Minimum 8 GB (16 GB recommended for local vector embeddings and local LLM models)
- **Disk Space**: 2 GB free disk space
- **Audio Hardware**: Working microphone and speakers/headphones for voice interaction

### Software
- **Operating System**: Windows 10/11 (64-bit), Ubuntu 22.04+ (or equivalent Linux distro), macOS 13+ (Ventura)
- **Python**: Python 3.11 or Python 3.12 (Python 3.12.6+ recommended)
- **Package Manager**: `pip`, `venv`, or `uv`
- **Optional**: Android SDK Platform-Tools (`adb`) for Android device control

---

## 2. Quick Start Installation

### Step 1: Clone the Repository
```powershell
git clone https://github.com/nexus-ai/nexus.git
cd nexus
```

### Step 2: Create and Activate Virtual Environment
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```powershell
# Install core and all optional packages (voice, automation, android, vision, dev)
pip install -e ".[all,dev]"
```

---

## 3. Configuration & API Keys

### Step 1: Create Environment Configuration
Copy the example environment configuration:
```powershell
cp .env.example .env
```

### Step 2: Configure LLM & Voice Provider Keys
Open `.env` in your editor and configure your preferred providers:

```ini
# --- Assistant Identity ---
NEXUS_ASSISTANT_NAME=Nexus
NEXUS_USER_NAME=Shanmuga

# --- LLM Providers (Configure at least one) ---
# Google Gemini (Recommended primary)
NEXUS_GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI (GPT-4o / GPT-4o-mini)
NEXUS_OPENAI_API_KEY=your_openai_api_key_here

# Anthropic (Claude 3.5 Sonnet)
NEXUS_ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Ollama (Local offline inference)
NEXUS_OLLAMA_BASE_URL=http://localhost:11434

# --- Voice & Speech Providers ---
# Deepgram STT (Ultra-fast real-time speech-to-text)
NEXUS_DEEPGRAM_API_KEY=your_deepgram_api_key_here

# ElevenLabs TTS (Ultra-realistic natural voices)
NEXUS_ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Local TTS Engine (edge-tts / pyttsx3)
NEXUS_VOICE_TTS_ENGINE=edge-tts
NEXUS_VOICE_STT_ENGINE=vosk
```

---

## 4. Optional Component Setup

### A. Android Device Control (ADB)
1. Enable **Developer Options** and **USB Debugging** on your Android device.
2. Connect your device via USB or Wireless ADB:
```powershell
adb devices
```
3. NEXUS will automatically discover and pair with connected devices.

### B. Offline Speech Models (Vosk / Whisper)
For 100% offline speech recognition:
1. Download a lightweight Vosk model:
```powershell
# Small English model (~40MB)
python -m nexus.voice.download_models --model small-en
```

---

## 5. Starting NEXUS

### Interactive CLI Mode
```powershell
nexus cli
# or via python module
python -m nexus.cli
```

### Background REST & WebSocket Server
```powershell
nexus serve --port 8000
```
Interactive API documentation will be available at: [http://localhost:8000/docs](http://localhost:8000/docs).

### Voice-First Mode
```powershell
nexus voice
```

---

## 6. Verifying Installation

Run the complete test suite to ensure all subsystems are operating properly:
```powershell
pytest
```
Expected output: `253 passed` (or higher).
