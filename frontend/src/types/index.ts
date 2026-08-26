export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  llm_providers: string[];
  tool_count: number;
  database_status: string;
  environment: string;
}

export interface IdentityResponse {
  assistant_name: string;
  user_name: string;
  wake_word: string;
  aliases: string[];
  all_wake_words: string[];
  require_wake_word: boolean;
  has_pending_confirmation: boolean;
  pending_action: string | null;
}

export interface NameChangeResponse {
  status: string;
  current_name: string;
  target_name: string;
  confirmation_prompt: string;
}

export interface ConfirmationResponse {
  status: string;
  message: string;
  confirmed: boolean;
}

export interface ToolCallInfo {
  name: string;
  arguments: Record<string, unknown>;
  result?: string | null;
  success?: boolean;
}

export interface MessageItem {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  model_used?: string | null;
  tool_calls?: ToolCallInfo[];
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  model_used?: string | null;
  tool_calls: ToolCallInfo[];
}

export interface ConversationSummary {
  id: string;
  summary: string | null;
  created_at: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  summary: string | null;
  created_at: string;
  messages: MessageItem[];
}

export interface LaptopToolSchema {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  category?: string;
}

export interface LaptopToolListResponse {
  count: number;
  tools: LaptopToolSchema[];
}

export interface LaptopStatusResponse {
  device_id: string;
  hostname: string;
  os: string;
  os_version: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  battery_percent: number | null;
  battery_plugged: boolean | null;
  ip_address: string;
  active_window: string | null;
  tools_available: number;
  timestamp: number;
}

export interface ToolExecutionResponse {
  request_id: string;
  tool_name: string;
  success: boolean;
  output: string;
  data: Record<string, unknown>;
  error: string | null;
  duration_seconds: number;
}

export interface VoiceConfigResponse {
  enabled: boolean;
  running: boolean;
  state: string;
  interaction_mode: string;
  language: string;
  stt_provider: string;
  tts_provider: string;
  tts_voice: string;
  tts_speed: number;
  interrupt_enabled: boolean;
  vad_uses_silero?: boolean;
}

export interface VoiceStatusResponse {
  pipeline: VoiceConfigResponse;
  available_voices: Array<{
    id?: string;
    name: string;
    ShortName?: string;
    Gender?: string;
    Locale?: string;
  }>;
}

export interface DeviceNode {
  device_id: string;
  name: string;
  alias: string | null;
  device_type: string;
  status: 'ONLINE' | 'OFFLINE' | 'CONNECTING' | 'BUSY';
  capabilities: string[];
  os_info: string;
  ip_address: string | null;
  last_heartbeat?: number;
}

export interface ActivityEvent {
  id: string;
  timestamp: string;
  type: 'chat' | 'tool_exec' | 'identity' | 'system' | 'security';
  title: string;
  detail: string;
  status: 'success' | 'warning' | 'error' | 'info';
}
