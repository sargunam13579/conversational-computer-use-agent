"""
NEXUS Accessibility Package.

Provides hands-free voice-first navigation, earcons & audio feedback,
custom voice shortcuts & macros, and screen reader verbal formatters.
"""

from nexus.accessibility.audio_feedback import AudioFeedbackManager, EarconType
from nexus.accessibility.custom_commands import CustomCommand, CustomCommandManager
from nexus.accessibility.voice_navigation import VoiceNavigationEngine

__all__ = [
    "AudioFeedbackManager",
    "EarconType",
    "CustomCommand",
    "CustomCommandManager",
    "VoiceNavigationEngine",
]
