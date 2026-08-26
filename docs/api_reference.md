# NEXUS REST & WebSocket API Reference

The NEXUS backend provides a comprehensive REST and WebSocket API for client applications, browser extensions, mobile companions, and voice peripherals.

Base URL: `http://localhost:8000/api`
Interactive Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`

---

## 1. Core Endpoints

### `GET /api/health`
Healthcheck diagnostic endpoint.
- **Response**: `{"status": "ok", "version": "0.1.0", "uptime_seconds": 120.4, "active_tasks": 0}`

### `POST /api/chat`
Send a single message or multi-turn conversational turn.
- **Request Body**:
  ```json
  {
    "message": "Find latest resume and send to my phone",
    "session_id": "optional_session_uuid",
    "stream": false
  }
  ```
- **Response**:
  ```json
  {
    "response": "Found resume and initiated transfer to your phone.",
    "session_id": "session_uuid",
    "tier_used": "smart"
  }
  ```

---

## 2. Multi-Step Task Endpoints (`/api/tasks`)

### `POST /api/tasks`
Submit a high-level goal for decomposition and execution.
- **Request Body**:
  ```json
  {
    "goal": "Find my resume, convert to PDF, rename it Shanmuga_Resume, and send to my phone",
    "execute_now": true
  }
  ```
- **Response**:
  ```json
  {
    "plan": {
      "plan_id": "plan_948210fe",
      "total_steps": 6,
      "status": "completed"
    },
    "execution": {
      "success": true,
      "steps_executed": 6,
      "duration_seconds": 2.45
    }
  }
  ```

### `GET /api/tasks`
List all historical and active multi-step plans.

### `GET /api/tasks/{task_id}`
Get detailed status and step-by-step progress for a task.

### `POST /api/tasks/{task_id}/cancel`
Cancel an active task gracefully.

### `POST /api/tasks/emergency/stop`
Trigger an immediate hard emergency stop across all running tasks.

---

## 3. Permissions Endpoints (`/api/permissions`)

### `GET /api/permissions`
List all capability permission scopes (`microphone`, `camera`, `screen_capture`, `file_access`, `notifications`, `accessibility`, `device_control`) and their grant status.

### `POST /api/permissions/grant`
Grant a permission scope.
- **Request Body**: `{"scope": "camera"}`

### `POST /api/permissions/revoke`
Revoke a permission scope.
- **Request Body**: `{"scope": "camera"}`

### `POST /api/permissions/reset`
Reset all permission scopes to default granted state.

---

## 4. Device Pairing Endpoints (`/api/pairing`)

### `POST /api/pairing/initiate`
Initiate pairing handshake and generate a time-limited 6-digit PIN.
- **Request Body**: `{"device_name": "Pixel 8", "device_type": "phone"}`
- **Response**: `{"session_id": "sess_89f02", "pin": "849201", "expires_in_seconds": 300}`

### `POST /api/pairing/verify`
Verify 6-digit PIN and receive permanent device token.
- **Request Body**: `{"session_id": "sess_89f02", "pin": "849201"}`
- **Response**: `{"success": true, "device_id": "dev_phone_001", "device_token": "token_xyz"}`

### `GET /api/pairing/devices`
List all authorized paired devices.

### `DELETE /api/pairing/devices/{device_id}`
Revoke access for a paired device.

---

## 5. Accessibility & Custom Commands (`/api/accessibility`)

### `GET /api/accessibility/commands`
List all configured custom voice shortcuts and compound macros.

### `POST /api/accessibility/commands`
Register a new custom voice command.
- **Request Body**:
  ```json
  {
    "phrase": "focus mode",
    "actions": ["set volume 10", "close browser tabs", "mute notifications"],
    "description": "Deep work mode"
  }
  ```

### `DELETE /api/accessibility/commands/{phrase}`
Remove a custom voice command.

### `POST /api/accessibility/audio/earcon`
Play a test audio earcon chime (`wake`, `success`, `error`, `confirmation`, `emergency_stop`).

---

## 6. Voice & Audio WebSocket

### `WS /api/voice/stream`
Full-duplex low-latency audio streaming for real-time STT and TTS streaming.
- **Audio Format**: 16kHz, 16-bit Mono Linear PCM.
