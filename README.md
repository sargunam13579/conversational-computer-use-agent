# NEXUS — Voice-First, Cross-Device Autonomous Personal AI Agent

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-276%20passed-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checking](https://img.shields.io/badge/type%20checker-pyright%20%7C%20mypy-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **NEXUS** is an autonomous, hands-free personal AI agent engineered to understand complex user goals, plan multi-step workflows, control desktop applications and Android mobile devices, and operate seamlessly across your personal ecosystem with military-grade safety guards.

---

## 🌟 Key Capabilities

- 🤖 **Autonomous Multi-Step Planning**: Understands high-level compound goals, decomposes them into dependency-ordered graphs, handles retries, variable passing (`{{step_1.output}}`), and automated result verification.
- 🎙️ **Voice-First & Hands-Free**: Low-latency voice loop with wake word detection (*"Nexus"*), dynamic renaming (*"Call yourself Jarvis"*), and non-visual audio feedback (earcons).
- 💻 **Complete Laptop Control**: 64 OS automation tools for window management, document conversion, audio control, application launching, and screen understanding.
- 📱 **Android Mobile Control**: Remote control via ADB, touch gestures, screen taps, app management, and bi-directional cross-device file transfer.
- 🌐 **Browser Automation**: Full Playwright automation for navigating web pages, filling forms, and extracting live web content.
- 🧠 **Unified 6-Tier Memory**: Working, Short-Term, Long-Term, Episodic, Semantic (ChromaDB vector store), and Procedural memory with automated preference learning.
- 🔒 **Defense-in-Depth Security**: Granular permission scopes (view/revoke), AES-GCM encrypted secret vault, PIN-based device pairing, and dangerous command blockers.
- ⚡ **Offline Mode Fallback**: Deterministic local command execution (app launching, volume control, status queries, emergency stop) when internet or cloud LLMs are unavailable.
- 🚨 **Universal Kill Switch**: Emergency stop command (*"NEXUS STOP"*) instantly halts all background tasks, sub-agents, and hardware actions.

---

## 🚀 Quick Start

### 1. Installation
```powershell
# Clone the repository
git clone https://github.com/nexus-ai/nexus.git
cd nexus

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package with all dependencies
pip install -e ".[all,dev]"
```

### 2. Configuration
```powershell
cp .env.example .env
# Configure your preferred LLM and Speech API keys in .env
```

### 3. Launching NEXUS
```powershell
# Interactive CLI mode
nexus cli

# Voice-first hands-free mode
nexus voice

# Background REST & WebSocket Server (Swagger at http://localhost:8000/docs)
nexus serve --port 8000
```

---

## 📚 Complete Documentation Suite

- 📖 [**Installation Guide**](docs/installation.md) — Comprehensive setup instructions for Windows, Linux, and macOS.
- 📖 [**User Guide**](docs/user_guide.md) — Daily usage, voice commands, multi-step examples, and macros.
- 📖 [**Developer Guide**](docs/developer_guide.md) — Architecture, creating custom tools, and event-bus development.
- 📖 [**API Reference**](docs/api_reference.md) — Complete REST and WebSocket endpoint specifications.
- 📖 [**Security Documentation**](docs/security.md) — Threat model, permission scopes, encryption, and audit logs.
- 📖 [**Architecture Documentation**](docs/architecture.md) — Deep dive into core subsystems, data flows, and concurrency.
- 📖 [**Troubleshooting Guide**](docs/troubleshooting.md) — Diagnostic checklists, error solutions, and recovery steps.

---

## 🏗️ System Architecture

```
User Voice / Text / API
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                       NexusBrain                            │
│  ┌─────────────────┐ ┌──────────────────┐ ┌───────────────┐ │
│  │ Identity / Wake │ │ Permissions Guard│ │ Offline Engine│ │
│  └─────────────────┘ └──────────────────┘ └───────────────┘ │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌───────────────────────────┐ ┌──────────────────────────┐
   │ Autonomous Task Planner   │ │  Multi-Model Router      │
   │ - Goal Decomposition      │ │  - Gemini 2.0 Flash/Pro  │
   │ - Dynamic Tool Selection  │ │  - Claude 3.5 Sonnet     │
   │ - Plan Execution Engine   │ │  - GPT-4o / GPT-4o-mini  │
   │ - Verification & Retries  │ │  - Local Ollama          │
   └────────────┬──────────────┘ └────────────┬─────────────┘
                │                             │
                └──────────────┬──────────────┘
                               ▼
        ┌───────────────────────────────────────────┐
        │       Unified Execution Sub-Agents        │
        │ ┌──────────────┐ ┌─────────────┐ ┌──────┐ │
        │ │ Laptop Agent │ │Android Agent│ │Vision│ │
        │ └──────────────┘ └─────────────┘ └──────┘ │
        └───────────────────────────────────────────┘
```

---

## 🧪 Testing & Verification

NEXUS includes 12 comprehensive test suites covering all 17 feature areas:

```powershell
# Run the entire test suite (276+ tests)
pytest

# Static analysis and linting
ruff check .
npx pyright
mypy src
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
