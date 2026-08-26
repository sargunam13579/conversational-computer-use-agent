# NEXUS User Guide

Welcome to **NEXUS**, your voice-first, multimodal, cross-device personal AI agent.

---

## 1. Getting Started

### Starting the Agent
You can interact with NEXUS in three primary modes:

```powershell
# 1. Interactive CLI (Text & Rich UI)
nexus cli

# 2. Voice-First Mode (Continuous hands-free voice loop)
nexus voice

# 3. Background REST & WebSocket Server
nexus serve --port 8000
```

---

## 2. Voice & Hands-Free Interaction

### Default Wake Word & Naming
- **Wake Word**: Say *"Nexus"* followed by your command.
- **Renaming the Assistant**:
  Say: *"Nexus, call yourself Jarvis"* or *"Nexus, change your name to Aria"*.
  NEXUS will ask for confirmation: *"Do you want me to change my name to Jarvis?"*
  Reply: *"Yes"*.

### Audio Feedback (Earcons)
NEXUS provides non-visual auditory feedback:
- **Ascending Tone**: Wake word recognized / listening.
- **Melodic Chime**: Task or command completed successfully.
- **Low Tone**: Error or retry in progress.
- **Alert Beep**: Risky action requires confirmation.
- **Warble Tone**: Emergency stop triggered.

---

## 3. Autonomous Multi-Step Planning

NEXUS can understand complex, multi-step user goals, decompose them into steps, select tools, and execute them safely:

### Example Goal:
> *"Nexus, find my latest resume, convert it to PDF, rename it Shanmuga_Resume, and send it to my phone."*

### What NEXUS Does:
1. **[Step 1] Find Files**: Searches user workspace for resume documents (`*.docx`, `*.pdf`).
2. **[Step 2] Identify Latest**: Inspects file modification timestamps to select the most recent version.
3. **[Step 3] Convert Format**: Converts `.docx` to `.pdf`.
4. **[Step 4] Rename File**: Renames output artifact to `Shanmuga_Resume.pdf`.
5. **[Step 5] Cross-Device Transfer**: Transfers the file to your paired Android phone via ADB / secure socket.
6. **[Step 6] Verification**: Validates delivery and file integrity.

---

## 4. Emergency Stop & Cancellation

Safety and user control are fundamental in NEXUS:

- **Soft Task Cancellation**:
  - Voice: *"Nexus stop"* or *"Cancel current task"*
  - Halts safe-to-stop actions at the current step.
- **Hard Emergency Stop (Kill Switch)**:
  - Voice / Text: **`"NEXUS STOP"`** or **`"EMERGENCY STOP"`**
  - Instantly aborts all active planning threads, terminates running background sub-processes, and stops hardware interactions immediately.

---

## 5. Permissions & Security

NEXUS implements granular capability scopes:
- `microphone`: Audio listening and voice recording
- `camera`: Camera capture and visual OCR
- `screen_capture`: Screen analysis and multimodal vision
- `file_access`: Local file reading, writing, and conversion
- `notifications`: System alert banners
- `accessibility`: UI tree inspection and input automation
- `device_control`: Android ADB and cross-device actions

### Viewing & Revoking Permissions:
```powershell
# Via CLI
nexus permissions list
nexus permissions revoke camera
nexus permissions grant camera

# Via REST API
curl -X POST http://localhost:8000/api/permissions/revoke -H "Content-Type: application/json" -d '{"scope": "camera"}'
```

---

## 6. Device Pairing (Cross-Device)

Pair your Android phone or secondary laptop with NEXUS:

1. Initiate pairing:
   ```powershell
   nexus pairing initiate --device "Pixel 8"
   # Output: PIN: 849201 (Valid for 5 minutes)
   ```
2. On your phone / client app:
   Submit PIN `849201` to authorize the connection and establish end-to-end encrypted communication.
3. Manage paired devices:
   ```powershell
   nexus pairing list
   nexus pairing revoke <device_id>
   ```

---

## 7. Custom Voice Commands & Macros

Define custom voice shortcuts for frequent multi-step workflows:

```powershell
# Example: Create "Focus Mode" shortcut
nexus accessibility create-command --phrase "focus mode" --actions "set volume 10, close browser tabs, mute notifications"
```
Whenever you say *"Nexus, enter focus mode"*, NEXUS will execute all specified actions automatically.

---

## 8. Offline Mode Fallback

When disconnected from the internet or if cloud LLM endpoints are unreachable, NEXUS automatically falls back to local deterministic execution:
- Open desktop applications (*"open notepad"*, *"open chrome"*)
- Adjust volume (*"set volume to 50"*, *"mute audio"*)
- Check battery and system status (*"battery status"*)
- List and search local workspace files
- Immediate emergency stop execution
