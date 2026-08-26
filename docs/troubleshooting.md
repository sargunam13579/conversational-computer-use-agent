# NEXUS Troubleshooting Guide

Common issues, diagnostic checks, and resolution steps for NEXUS.

---

## 1. Diagnostics & Health Check

Run the built-in diagnostic test suite to pinpoint subsystem failures:

```powershell
# Run full diagnostic suite
pytest -v

# Check API health
curl http://localhost:8000/api/health
```

---

## 2. Audio & Speech Issues

### Problem: Wake word is not triggering or microphone is silent
- **Cause 1: Missing audio drivers / microphone permission**
  - Verify your microphone is enabled in Windows / OS Settings.
  - Test audio capture with: `python -m nexus.voice.test_mic`
- **Cause 2: Revoked `microphone` scope**
  - Check permission scopes: `nexus permissions list`
  - Grant microphone: `nexus permissions grant microphone`
- **Cause 3: Missing `sounddevice` or PortAudio library**
  - Windows: `pip install sounddevice`
  - Linux: `sudo apt install libportaudio2`

### Problem: TTS voice is silent or slow
- **Cause 1**: If using ElevenLabs, check that `NEXUS_ELEVENLABS_API_KEY` is set and has active character quota.
- **Cause 2**: If offline, ensure `edge-tts` or `pyttsx3` is installed. Fallback to `pyttsx3` if no network is available.

---

## 3. LLM & API Key Issues

### Problem: `RuntimeError: No LLM providers available`
- **Cause**: No API keys are configured in `.env` and Ollama is not running.
- **Fix**:
  1. Add at least one valid key to `.env`:
     ```ini
     NEXUS_GEMINI_API_KEY=AIzaSy...
     ```
  2. Or start local Ollama server:
     ```powershell
     ollama run llama3
     ```

---

## 4. Android Device Control (ADB) Issues

### Problem: `Device not found` or `ADB bridge offline`
- **Cause 1**: Device unauthorized or USB debugging disabled.
- **Fix**:
  1. Unlock your phone and accept the "Allow USB debugging" prompt.
  2. Run `adb devices` in PowerShell to confirm device is listed as `device` (not `unauthorized`).
  3. Ensure `adb.exe` is in your system `PATH`.

---

## 5. Dangerous Command & Permission Errors

### Problem: `Command blocked: Root or system drive deletion is prohibited`
- **Cause**: NEXUS detected a blocked catastrophic command pattern (such as `format`, `rmdir /s /q c:\`, or fork bombs).
- **Fix**: This is an intentional security safeguard. Adjust the command to target specific safe workspace directories instead of whole drives.

### Problem: `Tool blocked due to revoked capability scope`
- **Cause**: The capability scope required by the tool (e.g. `camera`, `file_access`, `device_control`) has been revoked.
- **Fix**: Grant the scope via CLI or REST API:
  ```powershell
  nexus permissions grant <scope_name>
  ```
