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
  speakInstant: (
    text: string,
    onEnd?: () => void,
    onProgress?: (revealedText: string) => void
  ) => void;
  speakAssistantResponse: (
    text: string,
    turnId: number,
    onEnd?: () => void,
    onStart?: (durationSec?: number) => void,
    onProgress?: (revealedText: string) => void
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

/**
 * Downsamples Float32Array PCM from input sampleRate (e.g. 48000Hz) to targetRate (16000Hz).
 */
export function downsampleBuffer(buffer: Float32Array, inputRate: number, targetRate = 16000): Float32Array {
  if (inputRate === targetRate || inputRate <= 0) return buffer;
  const sampleRateRatio = inputRate / targetRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);

  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }

  return result;
}

/**
 * Encodes Float32Array PCM audio buffer into standard 16-bit Mono WAV Blob.
 */
export function encodeWavBlob(samples: Float32Array, sampleRate = 16000): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // Mono channel
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // Byte rate
  view.setUint16(32, 2, true); // Block align
  view.setUint16(34, 16, true); // 16-bit samples
  writeStr(36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([view], { type: 'audio/wav' });
}

export const VoiceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [voiceState, setVoiceState] = useState<VoiceStateType>('idle');
  const [voiceModeEnabled, setVoiceModeEnabledState] = useState<boolean>(false);
  const [autoVoiceResponse, setAutoVoiceResponse] = useState<boolean>(true);
  const [recognitionLang, setRecognitionLangState] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('nexus_recognition_lang') || 'ta-IN';
    }
    return 'ta-IN';
  });
  const recognitionLangRef = useRef<string>(recognitionLang);
  const [voiceStyle, setVoiceStyleState] = useState<VoiceStyleType>('auto');
  const [selectedVoiceName, setSelectedVoiceNameState] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(LOCAL_STORAGE_VOICE_KEY);
      if (stored && stored !== 'en-US-JennyNeural' && stored !== 'en-US-AvaNeural') return stored;
      return 'en-IN-PrabhatNeural';
    }
    return 'en-IN-PrabhatNeural';
  });
  const [availableVoices, setAvailableVoices] = useState<AvailableVoiceInfo[]>(DEFAULT_NEURAL_VOICES);
  const [transcript, setTranscript] = useState<string>('');
  const [interimTranscript, setInterimTranscript] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const setRecognitionLang = useCallback((lang: string) => {
    recognitionLangRef.current = lang;
    setRecognitionLangState(lang);
    if (typeof window !== 'undefined') {
      localStorage.setItem('nexus_recognition_lang', lang);
    }
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

  // Web Audio VAD & Direct WAV Stream Recording (Works in Electron, Chrome, Edge)
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioBufferChunksRef = useRef<Float32Array[]>([]);
  const isAudioSpeakingDetectedRef = useRef<boolean>(false);
  const silenceDetectionTimerRef = useRef<any>(null);
  const isTranscribingBackendRef = useRef<boolean>(false);

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

  const stopAudioVADRecorder = useCallback(() => {
    if (silenceDetectionTimerRef.current) {
      clearTimeout(silenceDetectionTimerRef.current);
      silenceDetectionTimerRef.current = null;
    }
    if (scriptProcessorRef.current) {
      try {
        scriptProcessorRef.current.disconnect();
      } catch {
        // ignore
      }
      scriptProcessorRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try {
        audioContextRef.current.close();
      } catch {
        // ignore
      }
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      try {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      } catch {
        // ignore
      }
      mediaStreamRef.current = null;
    }
    audioBufferChunksRef.current = [];
    isAudioSpeakingDetectedRef.current = false;
  }, []);

  const startContinuousListening = useCallback(() => {
    voiceModeEnabledRef.current = true;
    setVoiceModeEnabledState(true);

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    isProcessingRef.current = false;

    const dispatchFinalTranscript = (spokenText: string) => {
      const cleanText = spokenText.trim();
      if (!cleanText) return;

      const now = Date.now();
      // Deduplication guard against rapid identical transcripts
      if (
        cleanText === lastProcessedTranscriptRef.current.text &&
        now - lastProcessedTranscriptRef.current.time < 2000
      ) {
        console.log('[VOICE] Ignoring duplicate transcript:', cleanText);
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
      setError(null);

      // Stop current recognition so old results aren't accumulated for the next sentence
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }

      if (transcriptHandlerRef.current) {
        try {
          transcriptHandlerRef.current(cleanText);
        } catch (handlerErr) {
          console.error('[VOICE] Transcript handler error:', handlerErr);
        }
      }
    };

    // 1. Start Hardware Microphone AudioContext VAD (100% Reliable in Electron and Chrome)
    if (typeof navigator !== 'undefined' && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.mediaDevices
        .getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        })
        .then(async (stream) => {
          mediaStreamRef.current = stream;
          try {
            const AudioContextClass =
              window.AudioContext || (window as any).webkitAudioContext;
            if (!AudioContextClass) return;

            // Close existing AudioContext if open
            if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
              try {
                audioContextRef.current.close();
              } catch {
                // ignore
              }
            }

            const audioCtx = new AudioContextClass({ sampleRate: 16000 });
            audioContextRef.current = audioCtx;

            if (audioCtx.state === 'suspended') {
              await audioCtx.resume();
            }

            const source = audioCtx.createMediaStreamSource(stream);
            const scriptNode = audioCtx.createScriptProcessor(4096, 1, 1);
            scriptProcessorRef.current = scriptNode;

            isRecognitionActiveRef.current = true;
            setVoiceState('listening');
            console.log('[VOICE] Hardware microphone active & listening');

            scriptNode.onaudioprocess = (e) => {
              if (audioCtx.state === 'suspended') {
                audioCtx.resume().catch(() => {});
              }
              if (isSpeakingRef.current || isProcessingRef.current || isTranscribingBackendRef.current) {
                return;
              }

              const inputData = e.inputBuffer.getChannelData(0);
              let sum = 0;
              for (let i = 0; i < inputData.length; i++) {
                sum += inputData[i] * inputData[i];
              }
              const rms = Math.sqrt(sum / inputData.length);

              // Sound detected above noise floor (0.008 catches natural, soft human speech)
              if (rms > 0.008) {
                if (!isAudioSpeakingDetectedRef.current) {
                  isAudioSpeakingDetectedRef.current = true;
                }
                audioBufferChunksRef.current.push(new Float32Array(inputData));

                if (silenceDetectionTimerRef.current) {
                  clearTimeout(silenceDetectionTimerRef.current);
                  silenceDetectionTimerRef.current = null;
                }
              } else if (isAudioSpeakingDetectedRef.current) {
                // Trailing speech buffer to capture ending syllables
                audioBufferChunksRef.current.push(new Float32Array(inputData));

                if (!silenceDetectionTimerRef.current) {
                  silenceDetectionTimerRef.current = setTimeout(async () => {
                    isAudioSpeakingDetectedRef.current = false;
                    silenceDetectionTimerRef.current = null;

                    const chunks = audioBufferChunksRef.current;
                    audioBufferChunksRef.current = [];

                    // Need at least ~0.25s of audio to be a real utterance
                    if (chunks.length < 2) {
                      setInterimTranscript('');
                      return;
                    }

                    const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);
                    const merged = new Float32Array(totalLength);
                    let offset = 0;
                    for (const c of chunks) {
                      merged.set(c, offset);
                      offset += c.length;
                    }

                    try {
                      isTranscribingBackendRef.current = true;
                      const targetRate = 16000;
                      const downsampled = downsampleBuffer(merged, audioCtx.sampleRate, targetRate);
                      const wavBlob = encodeWavBlob(downsampled, targetRate);
                      const targetLang = recognitionLangRef.current || 'en-IN';
                      const res = await api.transcribeAudio(wavBlob, targetLang);

                      if (res && res.text && res.text.trim()) {
                        console.log('[VOICE VAD] Backend STT result:', res.text);
                        dispatchFinalTranscript(res.text.trim());
                      } else {
                        setInterimTranscript('');
                      }
                    } catch (err) {
                      console.debug('[VOICE VAD] Transcription notice:', err);
                      setInterimTranscript('');
                    } finally {
                      isTranscribingBackendRef.current = false;
                    }
                  }, 750);
                }
              }
            };

            source.connect(scriptNode);
            scriptNode.connect(audioCtx.destination);
          } catch (audioCtxErr) {
            console.warn('[VOICE] AudioContext initialization notice:', audioCtxErr);
          }
        })
        .catch((err) => {
          console.warn('[VOICE] Mic permission access error:', err);
        });
    }

    // 2. Start Web Speech API Recognition in parallel
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        if (recognitionRef.current) {
          try {
            recognitionRef.current.onstart = null;
            recognitionRef.current.onresult = null;
            recognitionRef.current.onerror = null;
            recognitionRef.current.onend = null;
            recognitionRef.current.abort();
          } catch {
            // ignore
          }
        }

        const recognition = new SpeechRecognition();
        recognitionRef.current = recognition;
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = recognitionLangRef.current || 'en-IN';

        recognition.onstart = () => {
          isRecognitionActiveRef.current = true;
          isProcessingRef.current = false;
          setVoiceState('listening');
          setError(null);
          console.log('[VOICE] Live microphone active (lang: ' + recognition.lang + ')');
        };

        recognition.onresult = (event: any) => {
          if (isSpeakingRef.current) {
            console.log('[VOICE] User speaking over assistant -> interrupting speech');
            cancelCurrentSpeech('barge_in');
          }

          let accumulatedFinal = '';
          let accumulatedInterim = '';

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
            console.log('[VOICE] Live speech detected:', combinedTranscript);

            if (silenceTimerRef.current) {
              clearTimeout(silenceTimerRef.current);
            }

            // Natural human pause threshold (750ms): prevents premature cutoff of multi-word phrases like "hello jarvis"
            silenceTimerRef.current = setTimeout(() => {
              if (combinedTranscript.length > 0) {
                console.log('[VOICE] Speech pause detected -> committing speech:', combinedTranscript);
                dispatchFinalTranscript(combinedTranscript);
              }
            }, 750);
          }
        };

        recognition.onerror = (event: any) => {
          console.log('[VOICE] Recognition notice / error:', event.error);
          if (event.error === 'no-speech' || event.error === 'aborted') {
            if (voiceModeEnabledRef.current) {
              setTimeout(() => {
                if (startContinuousListeningRef.current) {
                  startContinuousListeningRef.current();
                }
              }, 100);
            }
            return;
          }
          if (event.error === 'not-allowed') {
            setError('Microphone permission was denied. Please allow microphone access in your browser settings.');
            setVoiceModeEnabled(false);
            isRecognitionActiveRef.current = false;
            setVoiceState('idle');
            return;
          }
        };

        recognition.onend = () => {
          isRecognitionActiveRef.current = false;

          if (voiceModeEnabledRef.current) {
            if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
            restartTimerRef.current = setTimeout(() => {
              if (startContinuousListeningRef.current) {
                startContinuousListeningRef.current();
              }
            }, 100);
          } else {
            setVoiceState('idle');
          }
        };

        recognition.start();
      } catch (err: any) {
        isRecognitionActiveRef.current = false;
        console.warn('Could not start recognition:', err);
      }
    } else {
      isRecognitionActiveRef.current = true;
      setVoiceState('listening');
    }
  }, [cancelCurrentSpeech]);

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
    stopAudioVADRecorder();
    isRecognitionActiveRef.current = false;
    setVoiceState((prev) => (prev === 'listening' ? 'idle' : prev));
  }, [stopAudioVADRecorder]);

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
      onStart?: (durationSec?: number) => void,
      onProgress?: (revealedText: string) => void
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

      let chosenVoiceId = selectedVoiceNameRef.current || 'en-US-AvaNeural';
      if (containsTamilScript(cleanSpoken)) {
        if (chosenVoiceId.startsWith('ta-')) {
          // Use chosen Tamil voice directly
        } else if (/ava|jenny|emma|neerja|pallavi|female/i.test(chosenVoiceId)) {
          chosenVoiceId = 'ta-IN-PallaviNeural';
        } else {
          chosenVoiceId = 'ta-IN-ValluvarNeural';
        }
      }
      console.log(`[TTS START] turnId=${turnId} voice="${chosenVoiceId}" text="${cleanSpoken.slice(0, 70)}"`);

      const rawWords = text.trim().split(/\s+/);

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

        if (onProgress) {
          onProgress(text);
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

      // Try Backend High-Definition Edge Neural TTS first with a 2.2s race timeout (so it never blocks user)
      let backendSuccess = false;
      try {
        const synthPromise = api.synthesizeSpeech(cleanSpoken, chosenVoiceId, 0.92);
        const timeoutPromise = new Promise<Blob | null>((resolve) => setTimeout(() => resolve(null), 2200));
        const audioBlob = await Promise.race([synthPromise, timeoutPromise]);

        if (audioBlob && audioBlob.size > 100) {
          if (turnId !== activeTurnIdRef.current) {
            console.warn(`[STALE AUDIO DROPPED] turnId=${turnId}`);
            return;
          }

          const audioUrl = URL.createObjectURL(audioBlob);
          activeAudioUrlRef.current = audioUrl;

          const audio = new Audio(audioUrl);
          activeAudioRef.current = audio;

          let progressInterval: any = null;

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

            // Simultaneous word-by-word streaming in exact sync with audio playback
            if (onProgress && rawWords.length > 0) {
              onProgress(rawWords[0]);
              const duration = (audio.duration && !isNaN(audio.duration) && audio.duration > 0)
                ? audio.duration
                : rawWords.length * 0.35;

              progressInterval = setInterval(() => {
                if (audio.paused || audio.ended) {
                  clearInterval(progressInterval);
                  onProgress(text);
                  return;
                }
                const ratio = Math.min(1, Math.max(0, audio.currentTime / duration));
                const wordCount = Math.min(rawWords.length, Math.max(1, Math.ceil(ratio * rawWords.length)));
                onProgress(rawWords.slice(0, wordCount).join(' '));
              }, 40);
            }
          };

          audio.onended = () => {
            if (progressInterval) clearInterval(progressInterval);
            handleSpeechComplete();
          };

          audio.onerror = (err) => {
            if (progressInterval) clearInterval(progressInterval);
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

      // Fallback: Browser Web Speech Synthesis (0ms start delay & native word boundary event)
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
            utterance.rate = 0.95;
            utterance.pitch = 1.0;

            utterance.onstart = () => {
              if (turnId !== activeTurnIdRef.current) {
                window.speechSynthesis.cancel();
                return;
              }
              isSpeakingRef.current = true;
              setVoiceState('speaking');
              if (onProgress && rawWords.length > 0) {
                onProgress(rawWords[0]);
              }
              if (onStart) {
                try {
                  const estSec = cleanSpoken.split(' ').length * 0.28;
                  onStart(estSec);
                } catch (startErr) {
                  console.warn('onStart error:', startErr);
                }
              }
            };

            // Hardware-level word-by-word boundary synchronization!
            utterance.onboundary = (event: any) => {
              if (event.name === 'word' && onProgress) {
                const charIndex = event.charIndex ?? 0;
                const charLength = event.charLength ?? 0;
                const revealed = text.slice(0, Math.min(text.length, charIndex + charLength + 1)).trim();
                if (revealed) {
                  onProgress(revealed);
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
    (text: string, onEnd?: () => void, onProgress?: (revealedText: string) => void) => {
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

          const rawWords = text.trim().split(/\s+/);
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

          const estimatedDurationMs = Math.min(15000, Math.max(1800, cleanSpoken.split(' ').length * 350 + 800));
          let speechCompleted = false;

          const finishSpeech = (isCanceled = false) => {
            if (speechCompleted) return;
            speechCompleted = true;
            isSpeakingRef.current = false;
            activeUtteranceRef.current = null;
            (window as any).__nexus_active_utterance = null;
            if (onProgress) {
              onProgress(text);
            }
            if (onEnd && !isCanceled) {
              try {
                onEnd();
              } catch (e) {
                console.warn('speakInstant onEnd error:', e);
              }
            }
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

          utterance.onstart = () => {
            isSpeakingRef.current = true;
            setVoiceState('speaking');
            if (onProgress && rawWords.length > 0) {
              onProgress(rawWords[0]);
            }
          };

          utterance.onboundary = (event: any) => {
            if (event.name === 'word' && onProgress) {
              const charIndex = event.charIndex ?? 0;
              const charLength = event.charLength ?? 0;
              const revealed = text.slice(0, Math.min(text.length, charIndex + charLength + 1)).trim();
              if (revealed) {
                onProgress(revealed);
              }
            }
          };

          utterance.onend = () => {
            finishSpeech(false);
          };

          utterance.onerror = (e) => {
            const isCanceled = e.error === 'canceled' || e.error === 'interrupted';
            if (!isCanceled) {
              console.warn('speakInstant error:', e);
            }
            finishSpeech(isCanceled);
          };

          // Watchdog timer in case Chromium speech synthesis drops onend
          setTimeout(() => {
            if (!speechCompleted && isSpeakingRef.current) {
              console.log('[VOICE] speakInstant watchdog fired -> clearing speech lock');
              finishSpeech(false);
            }
          }, estimatedDurationMs);

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
      const testText = "Hello Sargunam, Seyal AI voice system is active with crystal clear studio audio.";
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
