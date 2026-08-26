"""
NEXUS CLI — Interactive Terminal Interface.

A beautiful terminal-based chat interface using Rich and prompt_toolkit.
Supports both text and voice interaction modes.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nexus.core.brain import NexusBrain
from nexus.core.config import get_settings
from nexus.utils.logging import (
    console,
    print_error,
    print_success,
    print_system,
    print_warning,
)

# Special commands
COMMANDS = {
    "/quit": "Exit NEXUS",
    "/exit": "Exit NEXUS",
    "/reset": "Reset conversation",
    "/tools": "List available tools",
    "/help": "Show help",
    "/clear": "Clear screen",
    "/identity": "Show assistant identity and wake words",
    "/name": "Show or change assistant name (e.g., /name Aria)",
    "/wake-word": "Show or change primary wake word (e.g., /wake-word Aria)",
    "/alias": "Manage aliases (e.g., /alias add Ari, /alias remove Ari, /alias list)",
    "/voice": "Toggle voice mode on/off",
    "/voice-mode": "Switch voice mode (voice+text / voice-only / text-only)",
    "/voice-config": "Show voice configuration",
    "/voice-speed": "Set speaking speed (e.g., /voice-speed 1.2)",
    "/voice-voice": "Set TTS voice (e.g., /voice-voice en-US-GuyNeural)",
    "/laptop": "Show laptop agent status & hardware diagnostics",
    "/screenshot": "Capture a screenshot of the screen",
    "/volume": "Set or mute volume (e.g., /volume 50, /volume mute)",
    "/apps": "Manage apps (e.g., /apps list, /apps search chrome)",
    "/lock": "Lock the laptop screen immediately",
    "/screen": "Analyze and describe what is currently on screen",
    "/ocr": "Read all visible text on the screen",
    "/locate": "Locate a UI element on screen (e.g. /locate Run)",
    "/privacy": "View or set screen privacy mode (e.g. /privacy allow_session, /privacy deny)",
    "/browse": "Open browser or navigate to a URL (e.g. /browse https://github.com)",
    "/websearch": "Search the web in browser and summarize results (e.g. /websearch Java interview)",
    "/tabs": "List open browser tabs",
    "/download": "Download a file to Documents folder (e.g. /download https://example.com/doc.pdf)",
    "/memory": "View stored memory records",
    "/remember": "Store a user preference or fact (e.g. /remember java_projects = D:/Projects)",
    "/forget": "Delete a stored memory by key (e.g. /forget java_projects)",
    "/clearmemory": "Clear all memory records",
    "/context": "View active task context and resolved entities",
    "/android": "Show connected Android device status & permissions",
    "/pair": "Generate a pairing code and QR code for Android phone",
    "/notify": "View notifications received from connected phone",
    "/mobile": "Execute command on Android phone (e.g. /mobile flashlight on, /mobile Spotify)",
    "/devices": "List all devices in ecosystem and their status (ONLINE, OFFLINE, CONNECTING, BUSY)",
    "/handoff": "Handoff active task to another device (e.g. /handoff phone)",
    "/transfer": "Transfer file to another device (e.g. /transfer report.pdf to phone)",
    "/revoke": "Revoke device access and invalidate credentials (e.g. /revoke phone)",
    "/computer-use": "Execute an autonomous visual computer-use goal (e.g. /computer-use Open Notepad and write poem)",
    "/act": "Alias for /computer-use",
    "/steer": "Inject live guidance into running computer-use task (e.g. /steer Click the blue button instead)",
}


def _print_banner() -> None:
    """Print the NEXUS startup banner."""
    banner = Text()
    banner.append("╔═══════════════════════════════════════════════════╗\n", style="bold cyan")
    banner.append("║                                                   ║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗   ", style="bold white")
    banner.append("║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝   ", style="bold white")
    banner.append("║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗   ", style="bold white")
    banner.append("║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║   ", style="bold white")
    banner.append("║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║   ", style="bold white")
    banner.append("║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ", style="bold white")
    banner.append("║\n", style="bold cyan")
    banner.append("║                                                   ║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     Voice-First Personal AI Agent                  ", style="dim white")
    banner.append("║\n", style="bold cyan")
    banner.append("║", style="bold cyan")
    banner.append("     Type /help for commands · /quit to exit        ", style="dim white")
    banner.append("║\n", style="bold cyan")
    banner.append("╚═══════════════════════════════════════════════════╝", style="bold cyan")

    console.print(banner)
    console.print()


def _print_help() -> None:
    """Print the help panel."""
    help_text = ""
    for cmd, desc in COMMANDS.items():
        help_text += f"  [bold cyan]{cmd:<16}[/] {desc}\n"
    help_text += "\n  [dim]Or just type naturally to talk to NEXUS![/]"

    console.print(
        Panel(
            help_text,
            title="[bold]Commands[/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def _print_voice_config(brain: NexusBrain) -> None:
    """Print the current voice configuration."""
    if brain.voice_pipeline is None:
        settings = get_settings().voice
        table = Table(
            title="Voice Configuration (pipeline not started)",
            border_style="magenta",
        )
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Enabled", str(settings.enabled))
        table.add_row("STT Provider", settings.stt_provider)
        table.add_row("TTS Provider", settings.tts_provider)
        table.add_row("Interaction Mode", settings.interaction_mode)
        table.add_row("Language", settings.language)
        table.add_row("TTS Voice", settings.tts.voice)
        table.add_row("TTS Speed", str(settings.tts.speed))
        table.add_row("Interrupt Enabled", str(settings.interrupt_enabled))
        table.add_row("Silence Threshold", f"{settings.silence_threshold_ms}ms")
        table.add_row("VAD Threshold", str(settings.vad.threshold))
        console.print(table)
    else:
        status = brain.voice_pipeline.get_status()
        table = Table(title="Voice Pipeline Status", border_style="green")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        for key, value in status.items():
            table.add_row(key.replace("_", " ").title(), str(value))
        console.print(table)


async def _toggle_voice(brain: NexusBrain) -> None:
    """Toggle the voice pipeline on/off."""
    if brain.is_voice_active:
        await brain.stop_voice()
        print_success("🎙️ Voice mode OFF")
    else:
        try:
            await brain.start_voice()
            print_success("🎙️ Voice mode ON — listening for speech...")
        except Exception as e:
            print_error(f"Could not start voice: {e}")
            print_warning(
                "Ensure you have a microphone connected and voice "
                "dependencies installed: pip install nexus-agent[voice]"
            )


def _print_identity(brain: NexusBrain) -> None:
    """Print the assistant identity and wake words."""
    identity = brain.identity
    table = Table(title="Assistant Identity & Wake Words", border_style="cyan")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Assistant Name", identity.name)
    table.add_row("User Name", identity.user_name)
    table.add_row("Primary Wake Word", identity.wake_word)
    table.add_row("Aliases", ", ".join(identity.aliases) if identity.aliases else "(none)")
    table.add_row("All Trigger Names", ", ".join(identity.all_wake_words))
    table.add_row("Prefixes", ", ".join(identity.config.wake_word_prefixes))
    table.add_row("Require Wake Word", str(identity.config.require_wake_word))
    if brain.confirmation.has_pending and brain.confirmation.pending_action:
        table.add_row("Pending Confirmation", brain.confirmation.pending_action.prompt_message)
    console.print(table)


async def _cycle_voice_mode(brain: NexusBrain) -> None:
    """Cycle through voice interaction modes."""
    modes = ["voice_and_text", "voice_only", "text_only"]
    mode_labels = {
        "voice_and_text": "🎙️+⌨️  Voice + Text",
        "voice_only": "🎙️  Voice Only",
        "text_only": "⌨️  Text Only",
    }

    if brain.voice_pipeline is None:
        print_warning("Voice pipeline is not running. Use /voice to start it first.")
        return

    current = brain.voice_pipeline.interaction_mode.value
    idx = modes.index(current) if current in modes else 0
    new_mode = modes[(idx + 1) % len(modes)]
    brain.voice_pipeline.interaction_mode = new_mode
    print_success(f"Voice mode: {mode_labels.get(new_mode, new_mode)}")


async def _handle_command(
    cmd_name: str,
    cmd_parts: list[str],
    brain: NexusBrain,
    settings: Any,
) -> bool:
    """
    Dispatch interactive slash commands.

    Returns:
        False to exit the CLI loop, True to continue.
    """
    if cmd_name in ("/quit", "/exit"):
        if brain.is_voice_active:
            await brain.stop_voice()
            print_system("Voice pipeline stopped")
        print_system("Goodbye! 👋")
        return False

    elif cmd_name == "/reset":
        brain.reset_conversation()
        print_success("Conversation reset")

    elif cmd_name == "/tools":
        tools = brain.available_tools
        console.print(
            Panel(
                "\n".join(f"  • {t}" for t in tools),
                title=f"[bold]Available Tools ({len(tools)})[/]",
                border_style="magenta",
            )
        )

    elif cmd_name == "/help":
        _print_help()

    elif cmd_name == "/clear":
        console.clear()
        _print_banner()

    elif cmd_name == "/voice":
        await _toggle_voice(brain)

    elif cmd_name == "/voice-mode":
        await _cycle_voice_mode(brain)

    elif cmd_name == "/voice-config":
        _print_voice_config(brain)

    elif cmd_name == "/voice-speed":
        if len(cmd_parts) > 1:
            try:
                speed = float(cmd_parts[1])
                if brain.voice_pipeline:
                    brain.voice_pipeline.tts_engine.speed = speed
                    print_success(f"Speaking speed set to {speed:.1f}x")
                else:
                    settings.voice.tts.speed = speed
                    print_success(f"Default speaking speed set to {speed:.1f}x")
            except ValueError:
                print_error("Invalid speed. Use a number like 1.0, 1.2, 0.8")
        else:
            print_error("Usage: /voice-speed <0.5-2.0>")

    elif cmd_name == "/voice-voice":
        if len(cmd_parts) > 1:
            voice_name = cmd_parts[1].strip()
            if brain.voice_pipeline:
                brain.voice_pipeline.tts_engine.voice = voice_name
            settings.voice.tts.voice = voice_name
            print_success(f"Voice set to: {voice_name}")
        else:
            print_error("Usage: /voice-voice <voice_name>")

    elif cmd_name == "/identity":
        _print_identity(brain)

    elif cmd_name == "/name":
        if len(cmd_parts) > 1:
            new_name = cmd_parts[1].strip()
            resp = brain.request_name_change(new_name)
            print_system(f"🤖 {resp}")
        else:
            print_system(f"Current assistant name: [bold cyan]{brain.name}[/]")
            print_system("To change: /name <new_name>")

    elif cmd_name == "/wake-word":
        if len(cmd_parts) > 1:
            new_ww = cmd_parts[1].strip()
            brain.identity.set_wake_word(new_ww)
            if brain.voice_pipeline:
                brain.voice_pipeline.wake_word_detector.update_wake_words(
                    primary=new_ww,
                    aliases=brain.identity.aliases,
                )
            print_success(f"Primary wake word set to: '{new_ww}'")
        else:
            print_system(f"Primary wake word: [bold cyan]{brain.identity.wake_word}[/]")
            print_system("To change: /wake-word <word>")

    elif cmd_name == "/alias":
        if len(cmd_parts) > 1:
            sub_parts = cmd_parts[1].split(maxsplit=1)
            sub_cmd = sub_parts[0].lower()
            alias_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

            if sub_cmd == "add" and alias_arg:
                if brain.identity.add_alias(alias_arg):
                    if brain.voice_pipeline:
                        brain.voice_pipeline.wake_word_detector.update_wake_words(
                            primary=brain.identity.wake_word,
                            aliases=brain.identity.aliases,
                        )
                    print_success(f"Added alias: '{alias_arg}'")
                else:
                    print_warning(f"Alias '{alias_arg}' already exists.")
            elif sub_cmd == "remove" and alias_arg:
                if brain.identity.remove_alias(alias_arg):
                    if brain.voice_pipeline:
                        brain.voice_pipeline.wake_word_detector.update_wake_words(
                            primary=brain.identity.wake_word,
                            aliases=brain.identity.aliases,
                        )
                    print_success(f"Removed alias: '{alias_arg}'")
                else:
                    print_warning(f"Alias '{alias_arg}' not found.")
            elif sub_cmd == "list":
                aliases = brain.identity.aliases
                alias_list = ", ".join(aliases) if aliases else "(none)"
                print_system(f"Active aliases: {alias_list}")
            else:
                print_error("Usage: /alias [add <name> | remove <name> | list]")
        else:
            aliases = brain.identity.aliases
            alias_list = ", ".join(aliases) if aliases else "(none)"
            print_system(f"Active aliases: {alias_list}")
            print_system("Usage: /alias add <name>, /alias remove <name>, /alias list")

    elif cmd_name == "/laptop":
        if brain.laptop_agent:
            status = brain.laptop_agent.get_status()
            table = Table(title="Laptop Agent Diagnostics", border_style="cyan")
            table.add_column("Diagnostic", style="cyan")
            table.add_column("Value", style="white")
            table.add_row("Device ID", status.device_id)
            table.add_row("Hostname", status.hostname)
            table.add_row("OS", status.os_info)
            table.add_row("CPU Utilization", f"{status.cpu_percent}%")
            table.add_row("RAM Utilization", f"{status.ram_percent}%")
            table.add_row("Battery", status.battery_info)
            table.add_row("Tools Loaded", str(len(status.available_tools)))
            console.print(table)
        else:
            print_warning("Laptop Agent is not active or disabled.")

    elif cmd_name == "/screenshot":
        if brain.laptop_agent:
            res = await brain.laptop_agent.execute_tool("screenshot", {})
            if res.success:
                print_success(f"📸 {res.output}")
            else:
                print_error(f"Screenshot failed: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/volume":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                vol_arg = cmd_parts[1].strip().lower()
                if vol_arg in ("mute", "unmute"):
                    res = await brain.laptop_agent.execute_tool(
                        "volume_control", {"action": vol_arg}
                    )
                elif vol_arg.isdigit():
                    res = await brain.laptop_agent.execute_tool(
                        "volume_control", {"action": "set", "level": int(vol_arg)}
                    )
                else:
                    print_error("Usage: /volume <0-100> | /volume mute | /volume unmute")
                    return True
                if res.success:
                    print_success(f"🔊 {res.output}")
                else:
                    print_error(f"Volume error: {res.error}")
            else:
                res = await brain.laptop_agent.execute_tool("volume_control", {"action": "get"})
                print_system(res.output)
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/apps":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                sub = cmd_parts[1].strip()
                if sub.startswith("search"):
                    q = sub.replace("search", "", 1).strip()
                    res = await brain.laptop_agent.execute_tool("search_applications", {"query": q})
                    print_system(res.output)
                elif sub == "list":
                    res = await brain.laptop_agent.execute_tool("list_applications", {})
                    print_system(res.output)
                else:
                    print_error("Usage: /apps list | /apps search <query>")
            else:
                res = await brain.laptop_agent.execute_tool("list_applications", {})
                print_system(res.output)
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/lock":
        if brain.laptop_agent:
            res = await brain.laptop_agent.execute_tool("lock_screen", {})
            if res.success:
                print_success(f"🔒 {res.output}")
            else:
                print_error(f"Lock failed: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/screen":
        if brain.laptop_agent:
            print_system("🔍 Analyzing screen...")
            res = await brain.laptop_agent.execute_tool("describe_screen", {})
            if res.success:
                console.print(
                    Panel(res.output, title="[bold cyan]Screen Description[/]", border_style="cyan")
                )
            else:
                print_error(f"Screen analysis failed: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/ocr":
        if brain.laptop_agent:
            print_system("📖 Reading visible text from screen...")
            res = await brain.laptop_agent.execute_tool("read_screen_text", {})
            if res.success:
                console.print(
                    Panel(res.output, title="[bold green]OCR Text[/]", border_style="green")
                )
            else:
                print_error(f"OCR failed: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/locate":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                elem_query = cmd_parts[1].strip()
                res = await brain.laptop_agent.execute_tool(
                    "locate_ui_element", {"element_name": elem_query}
                )
                if res.success:
                    print_success(f"📍 {res.output}")
                else:
                    print_warning(f"Not found: {res.output}")
            else:
                print_error("Usage: /locate <element_name> (e.g. /locate Run)")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/browse":
        if brain.laptop_agent:
            url_target = cmd_parts[1].strip() if len(cmd_parts) > 1 else None
            print_system(f"🌐 Opening browser{f' at {url_target}' if url_target else ''}...")
            res = await brain.laptop_agent.execute_tool(
                "open_browser", {"url": url_target} if url_target else {}
            )
            if res.success:
                print_success(res.output)
            else:
                print_error(f"Browser open failed: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/websearch":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                query = cmd_parts[1].strip()
                print_system(f"🔍 Searching web for '{query}'...")
                res = await brain.laptop_agent.execute_tool(
                    "execute_multistep_task", {"task_type": "search_and_read", "query": query}
                )
                if res.success:
                    console.print(
                        Panel(
                            res.output,
                            title="[bold cyan]Web Search Results[/]",
                            border_style="cyan",
                        )
                    )
                else:
                    print_error(f"Search failed: {res.error or res.output}")
            else:
                print_error("Usage: /websearch <query>")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/tabs":
        if brain.laptop_agent:
            res = await brain.laptop_agent.execute_tool("manage_web_tabs", {"action": "list"})
            if res.success:
                print_system(res.output)
            else:
                print_error(f"Tab query failed: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/download":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                dl_target = cmd_parts[1].strip()
                print_system(f"📥 Downloading '{dl_target}'...")
                res = await brain.laptop_agent.execute_tool(
                    "download_web_file",
                    {"target": dl_target, "destination_folder": "Documents"},
                )
                if res.success:
                    print_success(f"✅ {res.output}")
                else:
                    print_error(f"Download failed: {res.error}")
            else:
                print_error("Usage: /download <url_or_target>")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/memory":
        mem_res = await brain.memory_manager.search_memory(limit=50)
        if not mem_res:
            print_system("No memories currently stored.")
        else:
            table = Table(title="🧠 Stored NEXUS Memories", border_style="cyan")
            table.add_column("Category", style="magenta")
            table.add_column("Key", style="bold green")
            table.add_column("Value", style="white")
            for m in mem_res:
                table.add_row(m.category.value, m.key, str(m.value))
            console.print(table)

    elif cmd_name == "/remember":
        if len(cmd_parts) > 1 and "=" in cmd_parts[1]:
            k, v = cmd_parts[1].split("=", 1)
            rec = await brain.memory_manager.store_memory(key=k.strip(), value=v.strip())
            if rec:
                print_success(f"🧠 Remembered: [bold]{rec.key}[/] = {rec.value}")
            else:
                print_error("Memory storage is disabled.")
        else:
            print_error("Usage: /remember <key> = <value>")

    elif cmd_name == "/forget":
        if len(cmd_parts) > 1:
            target_key = cmd_parts[1].strip()
            deleted = await brain.memory_manager.delete_memory(target_key)
            if deleted:
                print_success(f"🗑️ Deleted memory '{target_key}'")
            else:
                print_error(f"Memory '{target_key}' not found.")
        else:
            print_error("Usage: /forget <key>")

    elif cmd_name == "/clearmemory":
        count = await brain.memory_manager.clear_memory()
        print_success(f"🧹 Cleared {count} memory record(s).")

    elif cmd_name == "/context":
        ctx_prompt = await brain.memory_manager.resolver.build_context_prompt()
        console.print(
            Panel(
                ctx_prompt or "No active context available.",
                title="[bold cyan]Active Context State[/]",
                border_style="cyan",
            )
        )

    elif cmd_name == "/android":
        if brain.laptop_agent:
            res = await brain.laptop_agent.execute_tool(
                "android_device_action", {"action": "get_battery"}
            )
            if res.success:
                print_system(f"📱 Connected Android Device Status:\n{res.output}")
            else:
                print_error(f"Android status query failed: {res.error or res.output}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/pair":
        from nexus.agents.android.security import AndroidSecurityManager

        sec = AndroidSecurityManager()
        code = sec.generate_pairing_code()
        console.print(
            Panel(
                f"[bold green]Pairing Code: {code}[/]\n\n"
                f"Enter this code on your Android NEXUS app to establish secure connection.\n"
                f"Pairing Link: nexus://pair?code={code}\n"
                f"Expires in 5 minutes.",
                title="[bold cyan]📱 Android Device Pairing[/]",
                border_style="cyan",
            )
        )

    elif cmd_name == "/notify":
        if brain.laptop_agent:
            res = await brain.laptop_agent.execute_tool("android_read_notifications", {"limit": 10})
            if res.success:
                console.print(
                    Panel(
                        res.output,
                        title="[bold cyan]📱 Phone Notifications[/]",
                        border_style="cyan",
                    )
                )
            else:
                print_error(f"Failed to read notifications: {res.error}")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/mobile":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                subcmd = cmd_parts[1].strip()
                if "flashlight" in subcmd.lower():
                    action = "flashlight_on" if "on" in subcmd.lower() else "flashlight_off"
                    res = await brain.laptop_agent.execute_tool(
                        "android_device_action", {"action": action}
                    )
                else:
                    res = await brain.laptop_agent.execute_tool(
                        "android_launch_app", {"app_name": subcmd}
                    )

                if res.success:
                    print_success(res.output)
                else:
                    print_error(f"Mobile action failed: {res.error or res.output}")
            else:
                print_error("Usage: /mobile <app_name | flashlight on/off>")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/devices":
        devs = brain.device_manager.list_devices()
        table = Table(title="🌐 NEXUS Unified Device Ecosystem", border_style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Name", style="green")
        table.add_column("Type", style="magenta")
        table.add_column("Device ID", style="white")
        table.add_column("OS / Platform", style="cyan")

        status_icons = {
            "ONLINE": "🟢 ONLINE",
            "OFFLINE": "🔴 OFFLINE",
            "CONNECTING": "🟡 CONNECTING",
            "BUSY": "🟣 BUSY",
        }
        for d in devs:
            st_label = status_icons.get(d.status.value, d.status.value)
            table.add_row(st_label, d.name, d.device_type.value, d.device_id, d.os_info)
        console.print(table)

    elif cmd_name == "/handoff":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                target = cmd_parts[1].strip()
                res = await brain.laptop_agent.execute_tool(
                    "handoff_task",
                    {"target_device": target, "task_description": "Migrated active session"},
                )
                if res.success:
                    print_success(res.output)
                else:
                    print_error(f"Task handoff failed: {res.error or res.output}")
            else:
                print_error("Usage: /handoff <device_name>")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/transfer":
        if brain.laptop_agent:
            if len(cmd_parts) > 1 and " to " in cmd_parts[1]:
                fpath, target = cmd_parts[1].split(" to ", 1)
                res = await brain.laptop_agent.execute_tool(
                    "transfer_file_cross_device",
                    {"file_path": fpath.strip(), "target_device": target.strip()},
                )
                if res.success:
                    print_success(res.output)
                else:
                    print_error(f"Transfer failed: {res.error or res.output}")
            else:
                print_error("Usage: /transfer <file_path> to <target_device>")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name == "/revoke":
        if brain.laptop_agent:
            if len(cmd_parts) > 1:
                target = cmd_parts[1].strip()
                res = await brain.laptop_agent.execute_tool(
                    "manage_device_access",
                    {"action": "revoke", "device_id": target},
                )
                if res.success:
                    print_success(res.output)
                else:
                    print_error(f"Revocation failed: {res.error or res.output}")
            else:
                print_error("Usage: /revoke <device_id_or_name>")
        else:
            print_warning("Laptop Agent is not available.")

    elif cmd_name in ("/computer-use", "/act", "/computer", "/cu"):
        if len(cmd_parts) > 1:
            goal = cmd_parts[1].strip()
            print_system(f"🚀 Starting Conversational Computer-Use Goal: [bold cyan]{goal}[/]")
            if brain.computer_use_agent:
                res = await brain.computer_use_agent.run_goal(goal=goal)
                st = res.get("status", "unknown")
                steps_count = res.get("steps_executed", 0)
                narration = res.get("narration") or "Task execution complete."
                
                # Render steps table
                history = res.get("history", [])
                if history:
                    table = Table(title=f"Execution Steps ({len(history)})", border_style="cyan")
                    table.add_column("#", style="bold green", width=4)
                    table.add_column("Action", style="cyan", width=15)
                    table.add_column("Thought", style="white")
                    table.add_column("Time", style="dim", width=8)
                    for s in history:
                        table.add_row(
                            str(s.get("step")),
                            str(s.get("action")),
                            str(s.get("thought")),
                            f"{s.get('elapsed_seconds', 0)}s",
                        )
                    console.print(table)
                
                if st == "completed":
                    print_success(f"🎉 {narration} (Completed in {steps_count} steps)")
                elif st == "waiting_user":
                    print_warning(f"❓ Agent Question: {res.get('question')}")
                else:
                    print_warning(f"Status: {st} ({res.get('error', 'Stopped')})")
            else:
                print_error("Computer-Use Agent not available on this system.")
        else:
            print_error("Usage: /computer-use <goal> (e.g. /computer-use Open Notepad and write summary)")

    elif cmd_name == "/steer":
        if len(cmd_parts) > 1:
            instruction = cmd_parts[1].strip()
            if brain.computer_use_agent:
                await brain.computer_use_agent.steer(instruction)
                print_success(f"🧭 Steered agent: '{instruction}'")
            else:
                print_error("Computer-Use Agent not active.")
        else:
            print_error("Usage: /steer <instruction>")

    else:
        print_error(f"Unknown command: {cmd_name}. Type /help for available commands.")

    return True


async def run_cli() -> None:
    """Run the interactive CLI chat loop."""
    settings = get_settings()

    _print_banner()

    # Initialize the brain
    print_system("Initializing NEXUS...")
    brain = NexusBrain(settings)

    try:
        await brain.initialize()
        print_success(
            f"Ready! ({len(brain.available_tools)} tools loaded, "
            f"providers: {', '.join(brain._router.available_providers) or 'none'})"
        )
    except Exception as e:
        print_error(f"Initialization failed: {e}")
        print_warning("NEXUS will run with limited capabilities.")

    # Auto-start voice if enabled in settings
    if settings.voice.enabled:
        try:
            await brain.start_voice()
            print_success("🎙️ Voice mode enabled — listening for speech...")
        except Exception as e:
            print_warning(f"Voice auto-start failed: {e}")

    console.print()

    # Set up prompt session with history
    session: PromptSession[str] = PromptSession(
        history=InMemoryHistory(),
    )

    # Main chat loop
    while True:
        try:
            # Show voice indicator in prompt if active
            if brain.is_voice_active:
                prompt_html = HTML(
                    "<ansibrightcyan><b>You </b></ansibrightcyan>"
                    "<ansigreen>🎙️</ansigreen>"
                    "<ansibrightcyan><b> › </b></ansibrightcyan>"
                )
            else:
                prompt_html = HTML("<ansibrightcyan><b>You › </b></ansibrightcyan>")

            # Get user input
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                functools.partial(session.prompt, prompt_html),
            )

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle special slash commands
            if user_input.startswith("/"):
                cmd_parts = user_input.lower().split(maxsplit=1)
                cmd_name = cmd_parts[0]
                should_continue = await _handle_command(cmd_name, cmd_parts, brain, settings)
                if not should_continue:
                    break
                continue

            # Process through the brain (text input → text response)
            console.print()
            response = await brain.process(user_input)

            # Display the response
            console.print()
            console.print(
                Panel(
                    Markdown(response),
                    title=f"[bold cyan]{brain.name}[/]",
                    border_style="cyan",
                    padding=(1, 2),
                )
            )
            console.print()

        except KeyboardInterrupt:
            console.print()
            print_system("Use /quit to exit")
            continue
        except EOFError:
            if brain.is_voice_active:
                await brain.stop_voice()
            print_system("Goodbye! 👋")
            break
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            console.print_exception()
