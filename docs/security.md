# NEXUS Security & Privacy Architecture

Security, user agency, privacy, and system safety are foundational principles of the **NEXUS** agent architecture.

---

## 1. Threat Model & Defense-in-Depth

NEXUS operates as an autonomous agent with local system access, device control, and network connectivity. To prevent misuse, unauthorized data extraction, and catastrophic system damage, NEXUS enforces multiple security layers:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Voice & API Authentication (PIN, Tokens, Rate Limits)    │
├─────────────────────────────────────────────────────────────┤
│ 2. Granular Permission Scopes (View & Revoke)               │
├─────────────────────────────────────────────────────────────┤
│ 3. Dangerous Command Blocker & Sandbox Classifier          │
├─────────────────────────────────────────────────────────────┤
│ 4. Two-Phase Confirmation Guard for High-Risk Actions        │
├─────────────────────────────────────────────────────────────┤
│ 5. AES-GCM Encrypted Secret Vault (Keys & Credentials)      │
├─────────────────────────────────────────────────────────────┤
│ 6. Global Kill Switch & Emergency Stop                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Granular Permission Scopes

NEXUS isolates hardware and sensitive system capabilities into distinct permission scopes:

| Scope | Description | Associated Tools | Default |
|---|---|---|---|
| `microphone` | Audio recording & continuous STT | `voice_record`, `speech_to_text` | Granted |
| `camera` | Webcam capture & visual OCR | `capture_camera`, `take_photo` | Granted |
| `screen_capture`| Desktop screen capture & vision | `screen_capture`, `screen_ocr` | Granted |
| `file_access` | Reading, writing, and deleting files | `find_files`, `read_file`, `write_file` | Granted |
| `notifications`| Desktop alert banners | `send_notification` | Granted |
| `accessibility`| Synthetic keyboard/mouse inputs | `click_element`, `type_text`, `press_hotkey` | Granted |
| `device_control`| Android ADB & cross-device tools | `android_adb`, `transfer_file` | Granted |

### Revocation Guarantee
When a scope is revoked, the tool executor instantly rejects any tool invocation requiring that capability with `PermissionAction.DENY` before any execution occurs.

---

## 3. Dangerous Terminal Command Protection

All shell and PowerShell commands pass through the `TerminalSecurityClassifier` (`src/nexus/security/terminal_security.py`) prior to execution:

### Strictly Blocked Commands (`BLOCKED`)
- Disk formatting (`format c:`, `diskpart`, `bcdedit`)
- Fork bombs (`:(){ :|:& };:`, `%0|%0`)
- Root recursive deletions (`rm -rf /`, `rd /s /q c:\`)
- Arbitrary dynamic script downloads (`curl ... | iex`, `Set-ExecutionPolicy Unrestricted`)

### High-Risk Commands Requiring Explicit Confirmation (`CONFIRM`)
- Service stops/restarts (`net stop`, `Stop-Service`)
- Registry modifications (`Set-ItemProperty HKLM:...`)
- System power actions (`shutdown`, `Restart-Computer`)

---

## 4. Cryptographic Secret Vault

Sensitive credentials (Gemini, OpenAI, Anthropic, Deepgram, and ElevenLabs API keys) are stored in an encrypted vault (`~/.nexus/vault.enc`):
- **Cipher**: AES-256-GCM authenticated encryption.
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations and per-vault salt.
- **Key Storage**: Master key stored in restricted permissions file `~/.nexus/keys/master.key` (POSIX `0600`).

---

## 5. Device Pairing & Handshake

To prevent unauthorized devices on the local network from sending commands to NEXUS:
1. Devices must initiate a pairing handshake.
2. A random, time-limited 6-digit numeric PIN is generated and displayed on the host.
3. The connecting device must present the PIN within 300 seconds.
4. Upon validation, a cryptographically secure 256-bit device authorization token is issued.
5. Users can view and revoke paired devices at any time.

---

## 6. Audit Logging

Every tool execution, permission check, security block, authentication event, and device pairing is recorded in the append-only audit trail (`src/nexus/security/audit.py` and SQLite `audit_log` table) for forensic review and full transparency.
