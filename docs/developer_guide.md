# NEXUS Developer Guide

This guide is intended for engineers contributing to or extending the NEXUS codebase.

---

## 1. Project Architecture & Directory Layout

```
nexus/
├── config/                 # Default YAML settings (default.yaml)
├── src/
│   └── nexus/
│       ├── accessibility/  # Earcons, custom macros, screen reader formatters
│       ├── agents/         # Sub-agents (LaptopAgent, AndroidAgent)
│       ├── api/            # FastAPI REST & WebSocket routers, middleware
│       ├── automation/     # Desktop UI automation (pyautogui, accessibility trees)
│       ├── browser/        # Playwright browser automation
│       ├── comms/          # Cross-device WebSocket protocol
│       ├── core/           # NexusBrain, ModelRouter, ToolRegistry, Orchestrator
│       ├── database/       # SQLite / SQLAlchemy models, engines, migrations
│       ├── devices/        # Unified Device Manager (laptop, android, remote)
│       ├── llm/            # Multi-model LLM provider adapters (Gemini, OpenAI, Anthropic, Ollama)
│       ├── memory/         # Unified 6-tier memory manager, ChromaDB vector store
│       ├── planning/       # Autonomous TaskPlanner, ToolSelector, ExecutionEngine
│       ├── security/       # Cryptographic vault, device pairing, permissions, terminal safety
│       ├── tools/          # Extensible Tool Base & 60+ system tools
│       ├── utils/          # EventBus, async logging, cancellation tokens
│       ├── vision/         # Screen capture, OCR, visual element detection
│       └── voice/          # VAD, STT (Deepgram/Vosk), TTS (ElevenLabs/edge-tts), Wake word
├── tests/                  # 12 test suites (276+ pytest cases)
└── docs/                   # Documentation suite
```

---

## 2. Development Setup

### Virtual Environment & Dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[all,dev]"
```

### Static Analysis & Type Checking
We maintain a zero-diagnostic policy across the codebase:
```powershell
# Fast linting and import sorting
ruff check .

# Static type checking
npx pyright
mypy src
```

### Running Tests
```powershell
# Run all unit and integration tests
pytest -v

# Run with test coverage report
pytest --cov=nexus --cov-report=term-missing
```

---

## 3. Creating Custom Tools

To add a new tool to NEXUS, subclass `BaseTool` in `src/nexus/tools/`:

```python
from typing import Any
from nexus.tools.base import BaseTool, RiskLevel, ToolResult

class CustomDataTool(BaseTool):
    name = "custom_data_lookup"
    description = "Lookup records from external database."
    risk_level = RiskLevel.LOW

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str) -> ToolResult:
        try:
            data = await perform_lookup(query)
            return ToolResult(success=True, output=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

Register the tool in `src/nexus/core/brain.py` or with `ToolRegistry.register(CustomDataTool())`.

---

## 4. Event Bus Architecture

NEXUS uses an asynchronous publish-subscribe `EventBus` (`src/nexus/utils/events.py`) to broadcast state changes across decoupled subsystems without circular dependencies:

```python
from nexus.utils.events import get_event_bus

bus = get_event_bus()

# Subscribe to events
async def on_task_progress(event):
    print(f"Task {event.payload['plan_id']} progress: {event.payload['percent']}%")

bus.subscribe("task.progress", on_task_progress)

# Emit event
await bus.emit("task.progress", {"plan_id": "plan_123", "percent": 50.0})
```

---

## 5. Coding Guidelines

- **Type Annotations**: All public functions and methods must have complete PEP 484 type annotations.
- **Asynchronous Execution**: Long-running or I/O operations must be `async def`.
- **Error Handling**: Catch specific exceptions and log with structured loggers (`get_logger(__name__)`). Never let unhandled exceptions crash background event loops.
