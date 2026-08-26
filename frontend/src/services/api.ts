import axios from 'axios';
import type {
  HealthResponse,
  IdentityResponse,
  NameChangeResponse,
  ConfirmationResponse,
  ChatResponse,
  ConversationSummary,
  ConversationDetail,
  LaptopStatusResponse,
  LaptopToolListResponse,
  ToolExecutionResponse,
  VoiceConfigResponse,
  VoiceStatusResponse,
  DeviceNode,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 45000,
});

export const api = {
  // System Health
  async getHealth(): Promise<HealthResponse> {
    const { data } = await apiClient.get<HealthResponse>('/health');
    return data;
  },

  // Identity & Assistant Name Management
  async getIdentity(): Promise<IdentityResponse> {
    const { data } = await apiClient.get<IdentityResponse>('/identity');
    return data;
  },

  async updateIdentity(payload: {
    user_name?: string;
    require_wake_word?: boolean;
    aliases?: string[];
  }): Promise<IdentityResponse> {
    const { data } = await apiClient.put<IdentityResponse>('/identity', payload);
    return data;
  },

  async requestNameChange(name: string): Promise<NameChangeResponse> {
    const { data } = await apiClient.post<NameChangeResponse>('/identity/change-name', { name });
    return data;
  },

  async confirmPendingAction(confirmed: boolean): Promise<ConfirmationResponse> {
    const { data } = await apiClient.post<ConfirmationResponse>('/identity/confirm', { confirmed });
    return data;
  },

  async cancelPendingConfirmation(): Promise<ConfirmationResponse> {
    const { data } = await apiClient.post<ConfirmationResponse>('/identity/cancel');
    return data;
  },

  async addAlias(alias: string): Promise<IdentityResponse> {
    const { data } = await apiClient.post<IdentityResponse>(`/identity/aliases?alias=${encodeURIComponent(alias)}`);
    return data;
  },

  async removeAlias(alias: string): Promise<IdentityResponse> {
    const { data } = await apiClient.delete<IdentityResponse>(`/identity/aliases/${encodeURIComponent(alias)}`);
    return data;
  },

  // Chat & Conversation
  async sendMessage(message: string, conversationId?: string): Promise<ChatResponse> {
    const { data } = await apiClient.post<ChatResponse>('/chat', {
      message,
      conversation_id: conversationId,
    });
    return data;
  },

  async resetChat(): Promise<{ message: string }> {
    const { data } = await apiClient.post<{ message: string }>('/chat/reset');
    return data;
  },

  async listConversations(page = 1, pageSize = 20): Promise<{
    conversations: ConversationSummary[];
    total: number;
    page: number;
    page_size: number;
  }> {
    const { data } = await apiClient.get('/conversations', {
      params: { page, page_size: pageSize },
    });
    return data;
  },

  async getConversation(conversationId: string): Promise<ConversationDetail> {
    const { data } = await apiClient.get<ConversationDetail>(`/conversations/${encodeURIComponent(conversationId)}`);
    return data;
  },

  async deleteConversation(conversationId: string): Promise<{ message: string; deleted_id: string }> {
    const { data } = await apiClient.delete(`/conversations/${encodeURIComponent(conversationId)}`);
    return data;
  },

  async updateConversation(conversationId: string, summary: string): Promise<ConversationSummary> {
    const { data } = await apiClient.patch<ConversationSummary>(`/conversations/${encodeURIComponent(conversationId)}`, {
      summary,
    });
    return data;
  },

  // Laptop Agent & System Control
  async getLaptopStatus(): Promise<LaptopStatusResponse> {
    const { data } = await apiClient.get<LaptopStatusResponse>('/laptop/status');
    return data;
  },

  async listLaptopTools(): Promise<LaptopToolListResponse> {
    const { data } = await apiClient.get<LaptopToolListResponse>('/laptop/tools');
    return data;
  },

  async executeLaptopTool(
    toolName: string,
    parameters: Record<string, unknown> = {},
    skipConfirmation = false
  ): Promise<ToolExecutionResponse> {
    const { data } = await apiClient.post<ToolExecutionResponse>('/laptop/execute', {
      request_id: `gui_${Date.now()}`,
      tool_name: toolName,
      parameters,
      skip_confirmation: skipConfirmation,
    });
    return data;
  },

  // Voice Pipeline & Speech Synthesis
  async getVoiceStatus(): Promise<VoiceStatusResponse> {
    const { data } = await apiClient.get<VoiceStatusResponse>('/voice/status');
    return data;
  },

  async getVoiceConfig(): Promise<VoiceConfigResponse> {
    const { data } = await apiClient.get<VoiceConfigResponse>('/voice/config');
    return data;
  },

  async startVoice(): Promise<{ status: string; message: string }> {
    const { data } = await apiClient.post('/voice/start');
    return data;
  },

  async stopVoice(): Promise<{ status: string; message: string }> {
    const { data } = await apiClient.post('/voice/stop');
    return data;
  },

  async synthesizeSpeech(text: string, voice?: string, speed?: number): Promise<Blob> {
    const response = await apiClient.post(
      '/voice/synthesize',
      { text, voice, speed },
      { responseType: 'blob' }
    );
    return response.data;
  },

  async transcribeAudio(audioBlob: Blob, language = 'en-US'): Promise<{
    text: string;
    language: string;
    provider: string;
    success: boolean;
    error?: string;
  }> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');
    formData.append('language', language);

    const { data } = await apiClient.post('/voice/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return data;
  },

  // Unified Device Ecosystem
  async listDevices(): Promise<{ count: number; devices: DeviceNode[] }> {
    const { data } = await apiClient.get('/devices/');
    return data;
  },

  // Conversational Computer-Use Agent
  async getComputerUseStatus(): Promise<{
    status: string;
    history_count: number;
    history: Array<{
      step: number;
      thought: string;
      action: string;
      coordinates: [number | null, number | null];
      success: boolean;
      elapsed_seconds: number;
    }>;
  }> {
    const { data } = await apiClient.get('/computer-use/status');
    return data;
  },

  async runComputerUseGoal(goal: string, maxSteps = 20, autoConfirm = false, conversationId?: string): Promise<any> {
    const { data } = await apiClient.post(
      '/computer-use/run',
      {
        goal,
        max_steps: maxSteps,
        auto_confirm: autoConfirm,
        conversation_id: conversationId,
      },
      {
        timeout: 180000,
      }
    );
    return data;
  },

  async steerComputerUse(instruction: string, interrupt = true): Promise<{
    status: string;
    instruction: string;
    message: string;
  }> {
    const { data } = await apiClient.post('/computer-use/steer', {
      instruction,
      interrupt,
    });
    return data;
  },

  async stopComputerUse(): Promise<{ status: string; message: string }> {
    const { data } = await apiClient.post('/computer-use/stop');
    return data;
  },

  async observeScreenState(tagElements = true): Promise<{
    status: string;
    screen_width: number;
    screen_height: number;
    active_window: string;
    detected_elements_count: number;
    detected_elements: Array<any>;
    som_base64_image?: string;
    base64_image?: string;
    timestamp: number;
  }> {
    const { data } = await apiClient.get('/computer-use/observe', {
      params: { tag_elements: tagElements },
    });
    return data;
  },

  async executeDirectAction(payload: {
    action_type: string;
    x?: number;
    y?: number;
    text?: string;
    key?: string;
    direction?: string;
    amount?: number;
  }): Promise<any> {
    const { data } = await apiClient.post('/computer-use/action', payload);
    return data;
  },
};
