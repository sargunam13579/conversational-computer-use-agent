import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { api } from '../services/api';

export type VoiceStateType = 'idle' | 'listening' | 'processing' | 'speaking';
export type VoiceStyleType = 'auto' | 'tamil_indian' | 'english';

export interface AvailableVoiceInfo {
  id: string;
  name: string;
  lang: string;
  gender?: string;
  isNeural?: boolean;
}

interface VoiceContextType {
  voiceState: VoiceStateType;
  isListening: boolean;
  isSpeaking: boolean;
  isProcessing: boolean;
  voiceModeEnabled: boolean;
  autoVoiceResponse: boolean;
  recognitionLang: string;
  setRecognitionLang: (lang: string) => void;
  voiceStyle: VoiceStyleType;
  selectedVoiceName: string;
  availableVoices: AvailableVoiceInfo[];
  transcript: string;
  interimTranscript: string;
  error: string | null;
  activeTurnId: number;
  setVoiceStyle: (style: VoiceStyleType) => void;
  setSelectedVoiceName: (voiceName: string) => void;
  setAutoVoiceResponse: (enabled: boolean) => void;
  setVoiceModeEnabled: (enabled: boolean) => void;
  toggleVoiceMode: () => void;
  startListening: (onFinalTranscript?: (text: string) => void, lang?: string) => void;
  startContinuousListening: () => void;
  stopListening: () => void;
  speakText: (text: string, onEnd?: () => void) => Promise<void>;
  speakInstant: (text: string, onEnd?: () => void) => void;
  speakAssistantResponse: (
    text: string,
    turnId: number,
    onEnd?: () => void,
    onStart?: (durationSec?: number) => void
  ) => Promise<void>;
  cancelCurrentSpeech: (reason?: string) => void;
  stopSpeaking: () => void;
  testVoice: (voiceName?: string) => Promise<void>;
  getNextTurnId: () => number;
  getCurrentTurnId: () => number;
  invalidateTurn: () => number;
  registerTranscriptHandler: (handler: (text: string) => void) => () => void;
  setProcessing: (processing: boolean) => void;
}

const VoiceContext = createContext<VoiceContextType | undefined>(undefined);

const LOCAL_STORAGE_VOICE_KEY = 'nexus_preferred_voice_name';

// Curated list of pristine, crystal-clear studio Neural voices (zero robotic clicks/glitches)
export const DEFAULT_NEURAL_VOICES: AvailableVoiceInfo[] = [
  {
    id: 'en-IN-PrabhatNeural',
    name: 'Indian Men Breeze (Natural Expressive - Prabhat)',
    lang: 'en-IN',
    gender: 'Male',
    isNeural: true,
  },
  {
    id: 'en-US-AndrewNeural',
    name: 'Breeze Male (Natural Expressive - Studio Male)',
    lang: 'en-US',
    gender: 'Male',
    isNeural: true,
  },
  {
    id: 'en-IN-MadhurNeural',
    name: 'Madhur (Natural Neural - Indian English Male)',
    lang: 'en-IN',
    gender: 'Male',
    isNeural: true,
  },
  {
    id: 'en-US-AvaNeural',
    name: 'Breeze Female (Natural Conversational Studio)',
    lang: 'en-US',
    gender: 'Female',
    isNeural: true,
  },
  {
    id: 'en-US-EmmaNeural',
    name: 'Emma (Natural Conversational - Soft Breeze)',
    lang: 'en-US',
    gender: 'Female',
    isNeural: true,
  },
  {
    id: 'en-US-JennyNeural',
    name: 'Jenny (Natural Neural - Crystal Clear US)',
    lang: 'en-US',
    gender: 'Female',
    isNeural: true,
  },
  {
    id: 'en-US-AriaNeural',
    name: 'Aria (Natural Neural - Expressive US)',
    lang: 'en-US',
    gender: 'Female',
    isNeural: true,
  },
  {
    id: 'en-IN-NeerjaNeural',
    name: 'Neerja (Natural Neural - Indian English)',
    lang: 'en-IN',
    gender: 'Female',
    isNeural: true,
  },
  {
    id: 'ta-IN-PallaviNeural',
    name: 'Pallavi (Tamil Natural Neural)',
    lang: 'ta-IN',
    gender: 'Female',
    isNeural: true,
  },
];

/**
 * Pristine speech text cleaner:
 * Eliminates all markdown syntax, bullets, asterisks, hashtags, isolated dots,
 * and weird punctuation that cause speech synthesizers to pronounce "dot", "bullet", or make click sounds.
 */
export function cleanTextForSpeech(text: string): string {
  if (!text) return '';
  return text
    // Remove multi-line code blocks
    .replace(/```[\s\S]*?```/g, '')
    // Remove inline code tags
    .replace(/`([^`]+)`/g, '$1')
    // Remove markdown links [label](url) -> label
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Strip URLs
    .replace(/https?:\/\/\S+/g, '')
    // Strip all emojis and unicode pictographs
    .replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F1E6}-\u{1F1FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}]/gu, '')
    .replace(/\p{Extended_Pictographic}/gu, '')
    // Remove JSON structures
    .replace(/\{[^{}]*\}/g, '')
    // Strip markdown formatting symbols (asterisks, hashtags, underscores, bullets, brackets, tildes, slashes, pipes)
    .replace(/[*_#~^|\\[\]<>{}=+]/g, ' ')
    // Replace multiple dots / ellipses (...) with a single period
    .replace(/\.{2,}/g, '. ')
    // Remove isolated single dots surrounded by whitespace (prevents saying "dot")
    .replace(/\s+\.\s+/g, ' ')
    // Remove leading list numbers/bullets e.g. "1. ", "2. ", "- ", "• "
    .replace(/^\s*(\d+\.|[-•–—])\s*/gm, '')
    // Clean up double quotes and stray symbols
    .replace(/["'`]/g, '')
    // Clean up punctuation spacing
    .replace(/\s+([,.!?])/g, '$1 ')
    // Collapse multiple whitespaces and newlines into a single clean space
    .replace(/\s+/g, ' ')
    .trim();
}

/** Check if text contains pure Tamil Unicode script (U+0B80 to U+0BFF) */
export function containsTamilScript(text: string): boolean {
  if (!text) return false;
  return /[\u0B80-\u0BFF]/.test(text);
}

export const VoiceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [voiceState, setVoiceState] = useState<VoiceStateType>('idle');
  const [voiceModeEnabled, setVoiceModeEnabledState] = useState<boolean>(false);
  const [autoVoiceResponse, setAutoVoiceResponse] = useState<boolean>(true);
  const [recognitionLang, setRecognitionLangState] = useState<string>('ta-IN');
  const recognitionLangRef = useRef<string>('ta-IN');
  const [voiceStyle, setVoiceStyleState] = useState<VoiceStyleType>('auto');
  const [selectedVoiceName, setSelectedVoiceNameState] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(LOCAL_STORAGE_VOICE_KEY);
      if (stored && stored !== 'en-US-JennyNeural' && stored !== 'en-US-AvaNeural') return stored;
      return 'ta-IN-PallaviNeural';
    }
    return 'ta-IN-PallaviNeural';
  });
  const [availableVoices, setAvailableVoices] = useState<AvailableVoiceInfo[]>(DEFAULT_NEURAL_VOICES);
  const [transcript, setTranscript] = useState<string>('');
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const setRecognitionLang = useCallback((lang: string) => {
    recognitionLangRef.current = lang;
    setRecognitionLangState(lang);
    if (recognitionRef.current && isRecognitionActiveRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
  }, []);

  const recognitionRef = useRef<any>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);
  const activeAudioUrlRef = useRef<string | null>(null);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const transcriptHandlerRef = useRef<((text: string) => void) | null>(null);
  const silenceTimerRef = useRef<any>(null);

  // Turn management: single source of truth for request synchronization
  const activeTurnIdRef = useRef<number>(0);
  const [activeTurnId, setActiveTurnId] = useState<number>(0);

  const getNextTurnId = useCallback(() => {
    activeTurnIdRef.current += 1;
    setActiveTurnId(activeTurnIdRef.current);
    return activeTurnIdRef.current;
  }, []);

  const getCurrentTurnId = useCallback(() => {
    return activeTurnIdRef.current;
  }, []);

  const invalidateTurn = useCallback(() => {
    activeTurnIdRef.current += 1;
    setActiveTurnId(activeTurnIdRef.current);
    return activeTurnIdRef.current;
  }, []);

  // Synchronization refs to eliminate state race conditions across rapid speech cycles
  const voiceModeEnabledRef = useRef<boolean>(false);
  const selectedVoiceNameRef = useRef<string>(selectedVoiceName);
  const isSpeakingRef = useRef<boolean>(false);
  const isProcessingRef = useRef<boolean>(false);
  const isRecognitionActiveRef = useRef<boolean>(false);
  const restartTimerRef = useRef<any>(null);
  const lastProcessedTranscriptRef = useRef<{ text: string; time: number }>({ text: '', time: 0 });

  const setSelectedVoiceName = useCallback((voiceName: string) => {
    selectedVoiceNameRef.current = voiceName;
    setSelectedVoiceNameState(voiceName);
    if (typeof window !== 'undefined') {
      if (voiceName) {
        localStorage.setItem(LOCAL_STORAGE_VOICE_KEY, voiceName);
      } else {
        localStorage.removeItem(LOCAL_STORAGE_VOICE_KEY);
      }
    }
  }, []);

  const setVoiceStyle = useCallback((style: VoiceStyleType) => {
    setVoiceStyleState(style);
  }, []);

  const setVoiceModeEnabled = useCallback((enabled: boolean) => {
    voiceModeEnabledRef.current = enabled;
    setVoiceModeEnabledState(enabled);
    if (!enabled) {
      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
      isRecognitionActiveRef.current = false;
      setVoiceState((prev) => (prev === 'listening' ? 'idle' : prev));
    }
  }, []);

  const toggleVoiceMode = useCallback(() => {
    setVoiceModeEnabled(!voiceModeEnabledRef.current);
  }, [setVoiceModeEnabled]);

  const setProcessing = useCallback((processing: boolean) => {
    isProcessingRef.current = processing;
    if (processing) {
      setVoiceState('processing');
    } else if (isSpeakingRef.current) {
      setVoiceState('speaking');
    } else if (voiceModeEnabledRef.current && isRecognitionActiveRef.current) {
      setVoiceState('listening');
    } else {
      setVoiceState('idle');
    }
  }, []);

  const registerTranscriptHandler = useCallback((handler: (text: string) => void) => {
    transcriptHandlerRef.current = handler;
    return () => {
      if (transcriptHandlerRef.current === handler) {
        transcriptHandlerRef.current = null;
      }
    };
  }, []);

  // Pre-load available voices from browser & merge with Neural voices
  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      const loadBrowserVoices = () => {
        const browserVoices = window.speechSynthesis.getVoices() || [];
        const browserMapped: AvailableVoiceInfo[] = browserVoices.map((v) => ({
          id: v.name,
          name: `${v.name} (${v.lang})`,
          lang: v.lang,
          gender: 'Neutral',
          isNeural: v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Google'),
        }));

        // Combine Neural defaults + Browser local voices
        const combined = [...DEFAULT_NEURAL_VOICES];
        for (const bv of browserMapped) {
          if (!combined.some((c) => c.id === bv.id)) {
            combined.push(bv);
          }
        }
        setAvailableVoices(combined);
      };

      loadBrowserVoices();
      window.speechSynthesis.onvoiceschanged = loadBrowserVoices;
    }
  }, []);

  const cancelCurrentSpeech = useCallback((reason = 'manual') => {
    console.log(`[TTS CANCELLED] reason=${reason} turnId=${activeTurnIdRef.current}`);
    isSpeakingRef.current = false;

    // 1. Stop HTML5 audio
    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.pause();
        activeAudioRef.current.currentTime = 0;
      } catch {
        // ignore
      }
      activeAudioRef.current = null;
    }

    if (activeAudioUrlRef.current) {
      try {
        URL.revokeObjectURL(activeAudioUrlRef.current);
      } catch {
        // ignore
      }
      activeAudioUrlRef.current = null;
    }

    // 2. Stop browser speechSynthesis
    if (activeUtteranceRef.current) {
      try {
        activeUtteranceRef.current.onend = null;
        activeUtteranceRef.current.onerror = null;
      } catch {
        // ignore
      }
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore
      }
    }
    activeUtteranceRef.current = null;
    (window as any).__nexus_active_utterance = null;

    if (!isProcessingRef.current) {
      setVoiceState((prev) => (prev === 'speaking' ? (voiceModeEnabledRef.current ? 'listening' : 'idle') : prev));
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    cancelCurrentSpeech('stop_request');
  }, [cancelCurrentSpeech]);

  const startContinuousListeningRef = useRef<() => void>(() => { });

  const startContinuousListening = useCallback(() => {
    if (!voiceModeEnabledRef.current) return;
    if (isSpeakingRef.current) return;
    if (isRecognitionActiveRef.current) return;

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError('Live voice recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    try {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }

      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = recognitionLangRef.current || 'ta-IN';

      const dispatchFinalTranscript = (spokenText: string) => {
        const cleanText = spokenText.trim();
        if (!cleanText) return;

        const now = Date.now();
        // Deduplication guard against rapid identical transcripts
        if (
          cleanText === lastProcessedTranscriptRef.current.text &&
          now - lastProcessedTranscriptRef.current.time < 2500
        ) {
          console.log('[VOICE] Ignoring duplicate transcript:', cleanText);
          return;
        }

        // If currently processing a request, ignore subsequent final triggers to prevent duplicate messages
        if (isProcessingRef.current) {
          console.log('[VOICE] Processing lock active, ignoring input:', cleanText);
          return;
        }

        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }

        lastProcessedTranscriptRef.current = { text: cleanText, time: now };
        console.log('[VOICE] Final transcript accepted & dispatching:', cleanText);
        setTranscript(cleanText);
        setInterimTranscript('');

        // Transition to processing state
        isProcessingRef.current = true;
        setVoiceState('processing');

        // Pause recognition while AI processes directive to eliminate mic feedback
        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch {
            // ignore
          }
        }
        isRecognitionActiveRef.current = false;

        if (transcriptHandlerRef.current) {
          transcriptHandlerRef.current(cleanText);
        }
      };

      recognition.onstart = () => {
        isRecognitionActiveRef.current = true;
        if (!isProcessingRef.current && !isSpeakingRef.current) {
          setVoiceState('listening');
        }
        setError(null);
        console.log('[VOICE] Live microphone active (lang: en-IN)');
      };

      recognition.onresult = (event: any) => {
        // Echo filter: If assistant is currently speaking aloud, ignore speaker audio
        if (isSpeakingRef.current) {
          return;
        }

        let accumulatedFinal = '';
        let accumulatedInterim = '';

        // Iterate through all results to capture full sentences and long multi-clause speech
        for (let i = 0; i < event.results.length; i++) {
          const res = event.results[i];
          const textChunk = res[0].transcript.trim();
          if (res.isFinal) {
            accumulatedFinal += (accumulatedFinal ? ' ' : '') + textChunk;
          } else {
            accumulatedInterim += (accumulatedInterim ? ' ' : '') + textChunk;
          }
        }

        const combinedTranscript = (
          accumulatedFinal + (accumulatedInterim ? (accumulatedFinal ? ' ' : '') + accumulatedInterim : '')
        ).trim();

        if (combinedTranscript.length > 0) {
          setInterimTranscript(combinedTranscript);

          // Reset silence timer on any speech progress
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
          }

          // Adaptive silence pause timer (800ms) to allow natural pauses while committing fast
          silenceTimerRef.current = setTimeout(() => {
            if (
              combinedTranscript.length > 0 &&
              !isProcessingRef.current &&
              !isSpeakingRef.current
            ) {
              console.log('[VOICE] Speech pause detected -> committing speech:', combinedTranscript);
              dispatchFinalTranscript(combinedTranscript);
            }
          }, 800);
        }

        // If browser finalized a chunk and no interim is left, auto-commit after a snappy 400ms buffer
        if (accumulatedFinal.length > 0 && accumulatedInterim.length === 0) {
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
          }
          silenceTimerRef.current = setTimeout(() => {
            if (!isProcessingRef.current && !isSpeakingRef.current) {
              dispatchFinalTranscript(accumulatedFinal);
            }
          }, 400);
        }
      };

      recognition.onerror = (event: any) => {
        if (event.error === 'no-speech' || event.error === 'aborted') {
          // Immediately restart if in continuous voice mode
          if (voiceModeEnabledRef.current && !isProcessingRef.current && !isSpeakingRef.current) {
            setTimeout(() => {
              if (startContinuousListeningRef.current) {
                startContinuousListeningRef.current();
              }
            }, 80);
          }
          return;
        }
        if (event.error === 'not-allowed') {
          setError('Microphone permission was denied. Please allow microphone access for live conversation.');
          setVoiceModeEnabled(false);
          return;
        }
        console.warn('Recognition notice:', event.error);
      };

      recognition.onend = () => {
        isRecognitionActiveRef.current = false;

        // Automatically resume listening immediately if continuous voice mode is ON and not speaking/processing
        if (voiceModeEnabledRef.current && !isProcessingRef.current && !isSpeakingRef.current) {
          if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
          restartTimerRef.current = setTimeout(() => {
            if (startContinuousListeningRef.current) {
              startContinuousListeningRef.current();
            }
          }, 80);
        } else if (!isSpeakingRef.current && !isProcessingRef.current) {
          setVoiceState('idle');
        }
      };

      recognition.start();
    } catch (err: any) {
      isRecognitionActiveRef.current = false;
      console.warn('Could not start recognition:', err);
    }
  }, [setVoiceModeEnabled]);

  useEffect(() => {
    startContinuousListeningRef.current = startContinuousListening;
  }, [startContinuousListening]);

  const stopListening = useCallback(() => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    isRecognitionActiveRef.current = false;
    setVoiceState((prev) => (prev === 'listening' ? 'idle' : prev));
  }, []);

  /**
   * High-Definition Neural Speech Synthesizer:
   * 1. Uses Edge-TTS Neural backend for pristine, studio-quality MP3 audio (zero clicking, zero robotic artifacts).
   * 2. Automatically falls back to high-grade browser SpeechSynthesis if offline.
   */
  const speakAssistantResponse = useCallback(
    async (
      text: string,
      turnId: number,
      onEnd?: () => void,
      onStart?: (durationSec?: number) => void
    ) => {
      // 1. Turn validation: check that this turn is still the active/latest request
      if (turnId !== activeTurnIdRef.current) {
        console.warn(`[STALE RESPONSE IGNORED] id=${turnId} activeTurnId=${activeTurnIdRef.current}`);
        if (onEnd) onEnd();
        return;
      }

      if (!text || !text.trim()) {
        if (onEnd) onEnd();
        return;
      }

      // 2. Clean text from all markdown, asterisks, emojis, and stray dots
      const cleanSpoken = cleanTextForSpeech(text);
      if (!cleanSpoken) {
        if (onEnd) onEnd();
        return;
      }

      // 3. Pause microphone to eliminate speaker feedback & false barge-ins
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
      isRecognitionActiveRef.current = false;

      // 4. Cancel any currently playing speech
      cancelCurrentSpeech('new_response');

      let chosenVoiceId = selectedVoiceNameRef.current || 'en-IN-PrabhatNeural';
      if (containsTamilScript(cleanSpoken)) {
        chosenVoiceId = 'ta-IN-ValluvarNeural';
      }
      console.log(`[TTS START] turnId=${turnId} voice="${chosenVoiceId}" text="${cleanSpoken.slice(0, 70)}"`);

      const handleSpeechComplete = () => {
        isSpeakingRef.current = false;
        activeAudioRef.current = null;
        activeUtteranceRef.current = null;
        (window as any).__nexus_active_utterance = null;

        if (activeAudioUrlRef.current) {
          try {
            URL.revokeObjectURL(activeAudioUrlRef.current);
          } catch {
            // ignore
          }
          activeAudioUrlRef.current = null;
        }

        if (onEnd) {
          try {
            onEnd();
          } catch (e) {
            console.error('onEnd callback error:', e);
          }
        }

        // Once speaking finishes, automatically resume live listening!
        if (voiceModeEnabledRef.current && !isProcessingRef.current) {
          setVoiceState('listening');
          setTimeout(() => {
            if (startContinuousListeningRef.current) {
              startContinuousListeningRef.current();
            }
          }, 120);
        } else if (!isProcessingRef.current) {
          setVoiceState('idle');
        }
      };

      // Try Backend High-Definition Edge Neural TTS first (studio quality, zero click noise)
      let backendSuccess = false;
      try {
        const audioBlob = await api.synthesizeSpeech(cleanSpoken, chosenVoiceId, 0.92);
        if (audioBlob && audioBlob.size > 100) {
          if (turnId !== activeTurnIdRef.current) {
            console.warn(`[STALE AUDIO DROPPED] turnId=${turnId}`);
            return;
          }

          const audioUrl = URL.createObjectURL(audioBlob);
          activeAudioUrlRef.current = audioUrl;

          const audio = new Audio(audioUrl);
          activeAudioRef.current = audio;

          audio.onplay = () => {
            isSpeakingRef.current = true;
            setVoiceState('speaking');
            if (onStart) {
              try {
                const estimatedSec = cleanSpoken.split(' ').length * 0.32;
                onStart(audio.duration && !isNaN(audio.duration) && audio.duration > 0 ? audio.duration : estimatedSec);
              } catch (startErr) {
                console.warn('onStart error:', startErr);
              }
            }
          };

          audio.onended = () => {
            handleSpeechComplete();
          };

          audio.onerror = (err) => {
            console.warn('Audio playback notice:', err);
            handleSpeechComplete();
          };

          isSpeakingRef.current = true;
          setVoiceState('speaking');
          await audio.play();
          backendSuccess = true;
        }
      } catch (synthErr) {
        console.warn('[TTS] Backend synthesis fallback to browser Web Speech API:', synthErr);
        backendSuccess = false;
      }

      // Fallback: Browser Web Speech Synthesis if backend audio was unavailable
      if (!backendSuccess) {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
          try {
            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(cleanSpoken);
            const rawVoices = window.speechSynthesis.getVoices() || [];

            // Match preferred browser voice
            const matchedVoice =
              rawVoices.find((v) => v.name === chosenVoiceId) ||
              rawVoices.find(
                (v) =>
                  v.lang.startsWith('en') &&
                  (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Google') || v.name.includes('Andrew') || v.name.includes('Brian') || v.name.includes('Guy'))
              ) ||
              rawVoices.find((v) => v.lang.startsWith('en')) ||
              rawVoices[0];

            if (matchedVoice) {
              utterance.voice = matchedVoice;
            }
            utterance.lang = matchedVoice?.lang || 'en-US';
            utterance.rate = 0.92;
            utterance.pitch = 1.0;

            utterance.onstart = () => {
              if (turnId !== activeTurnIdRef.current) {
                window.speechSynthesis.cancel();
                return;
              }
              isSpeakingRef.current = true;
              setVoiceState('speaking');
              if (onStart) {
                try {
                  const estSec = cleanSpoken.split(' ').length * 0.28;
                  onStart(estSec);
                } catch (startErr) {
                  console.warn('onStart error:', startErr);
                }
              }
            };

            utterance.onend = handleSpeechComplete;
            utterance.onerror = (e) => {
              if (e.error !== 'canceled' && e.error !== 'interrupted') {
                console.warn('SpeechSynthesis error event:', e.error);
              }
              handleSpeechComplete();
            };

            activeUtteranceRef.current = utterance;
            (window as any).__nexus_active_utterance = utterance;
            isSpeakingRef.current = true;
            setVoiceState('speaking');

            window.speechSynthesis.speak(utterance);
          } catch (err) {
            console.warn('Speech synthesis error:', err);
            handleSpeechComplete();
          }
        } else {
          handleSpeechComplete();
        }
      }
    },
    [cancelCurrentSpeech]
  );

  const speakText = useCallback(
    async (text: string, onEnd?: () => void) => {
      const turnId = getNextTurnId();
      await speakAssistantResponse(text, turnId, onEnd);
    },
    [getNextTurnId, speakAssistantResponse]
  );

  const speakInstant = useCallback(
    (text: string, onEnd?: () => void) => {
      if (!text || !text.trim()) {
        if (onEnd) onEnd();
        return;
      }
      cancelCurrentSpeech('instant_speech');
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        try {
          window.speechSynthesis.cancel();
          const cleanSpoken = cleanTextForSpeech(text);
          if (!cleanSpoken) {
            if (onEnd) onEnd();
            return;
          }

          const utterance = new SpeechSynthesisUtterance(cleanSpoken);
          const rawVoices = window.speechSynthesis.getVoices() || [];

          // Select the same high-quality natural voice consistently for all greetings and replies
          let matchedVoice: SpeechSynthesisVoice | undefined;
          const preferredName = selectedVoiceNameRef.current;
          matchedVoice =
            (preferredName ? rawVoices.find((v) => v.name.includes(preferredName) || v.name === preferredName) : undefined) ||
            rawVoices.find(
              (v) =>
                v.name.includes('Natural') ||
                v.name.includes('Neural') ||
                v.name.includes('Google') ||
                v.name.includes('Andrew') ||
                v.name.includes('Prabhat') ||
                v.name.includes('Brian') ||
                v.name.includes('India')
            ) ||
            rawVoices.find((v) => v.lang.startsWith('en') || v.lang.startsWith('ta')) ||
            rawVoices[0];

          if (matchedVoice) {
            utterance.voice = matchedVoice;
            utterance.lang = matchedVoice.lang || 'en-IN';
          } else {
            utterance.lang = 'en-IN';
          }
          utterance.rate = 1.02;
          utterance.pitch = 1.0;

          // Unlock processing state immediately so subsequent speech inputs are never blocked
          isProcessingRef.current = false;

          utterance.onstart = () => {
            isSpeakingRef.current = true;
            setVoiceState('speaking');
          };
          utterance.onend = () => {
            isSpeakingRef.current = false;
            activeUtteranceRef.current = null;
            (window as any).__nexus_active_utterance = null;
            if (onEnd) onEnd();
            if (voiceModeEnabledRef.current && !isProcessingRef.current) {
              setVoiceState('listening');
              setTimeout(() => {
                if (startContinuousListeningRef.current) {
                  startContinuousListeningRef.current();
                }
              }, 80);
            } else if (!isProcessingRef.current) {
              setVoiceState('idle');
            }
          };
          utterance.onerror = (e) => {
            const isCanceled = e.error === 'canceled' || e.error === 'interrupted';
            if (!isCanceled) {
              console.warn('speakInstant error:', e);
            }
            isSpeakingRef.current = false;
            activeUtteranceRef.current = null;
            (window as any).__nexus_active_utterance = null;
            if (onEnd && !isCanceled) onEnd();
            if (!isCanceled && voiceModeEnabledRef.current && !isProcessingRef.current) {
              setVoiceState('listening');
              setTimeout(() => {
                if (startContinuousListeningRef.current) {
                  startContinuousListeningRef.current();
                }
              }, 80);
            } else if (!isProcessingRef.current) {
              setVoiceState('idle');
            }
          };

          activeUtteranceRef.current = utterance;
          (window as any).__nexus_active_utterance = utterance;
          isSpeakingRef.current = true;
          setVoiceState('speaking');
          window.speechSynthesis.speak(utterance);
        } catch (e) {
          console.warn('speakInstant error:', e);
          isSpeakingRef.current = false;
          setVoiceState('idle');
          if (onEnd) onEnd();
        }
      } else {
        if (onEnd) onEnd();
      }
    },
    [cancelCurrentSpeech]
  );

  const testVoice = useCallback(
    async (voiceName?: string) => {
      const targetVoice = voiceName || selectedVoiceNameRef.current;
      const turnId = getNextTurnId();
      const testText = "Hello Sargunam, Nexus voice system is active with crystal clear studio audio.";
      if (targetVoice) {
        selectedVoiceNameRef.current = targetVoice;
      }
      await speakAssistantResponse(testText, turnId);
    },
    [getNextTurnId, speakAssistantResponse]
  );

  const startListeningLegacy = useCallback(
    (onFinalTranscript?: (text: string) => void, lang?: string) => {
      if (lang) {
        recognitionLangRef.current = lang;
        setRecognitionLangState(lang);
      }
      if (onFinalTranscript) {
        transcriptHandlerRef.current = onFinalTranscript;
      }
      setVoiceModeEnabled(true);
      startContinuousListening();
    },
    [setVoiceModeEnabled, startContinuousListening]
  );

  return (
    <VoiceContext.Provider
      value={{
        voiceState,
        isListening: voiceState === 'listening',
        isSpeaking: voiceState === 'speaking',
        isProcessing: voiceState === 'processing',
        voiceModeEnabled,
        autoVoiceResponse,
        recognitionLang,
        setRecognitionLang,
        voiceStyle,
        selectedVoiceName,
        availableVoices,
        transcript,
        interimTranscript,
        error,
        activeTurnId,
        setVoiceStyle,
        setSelectedVoiceName,
        setAutoVoiceResponse,
        setVoiceModeEnabled,
        toggleVoiceMode,
        startListening: startListeningLegacy,
        startContinuousListening,
        stopListening,
        speakText,
        speakInstant,
        speakAssistantResponse,
        cancelCurrentSpeech,
        stopSpeaking,
        testVoice,
        getNextTurnId,
        getCurrentTurnId,
        invalidateTurn,
        registerTranscriptHandler,
        setProcessing,
      }}
    >
      {children}
    </VoiceContext.Provider>
  );
};

export const useVoice = (): VoiceContextType => {
  const context = useContext(VoiceContext);
  if (!context) {
    throw new Error('useVoice must be used within a VoiceProvider');
  }
  return context;
};
