import { apiFetch } from './api';

export interface AdminSettings {
  confidence_threshold: number;
  vision_provider: 'ollama' | 'gemini' | 'anthropic';
  vision_model: string;
  ollama_endpoint: string;
  gemini_api_key_masked: string;
  anthropic_api_key_masked: string;
  gemini_api_key_set: boolean;
  anthropic_api_key_set: boolean;
  few_shot_correction_window: number;
  use_real_pipeline: boolean;
  rocm_available: boolean;
}

export type AdminSettingsPatch = Partial<{
  confidence_threshold: number;
  vision_provider: 'ollama' | 'gemini' | 'anthropic';
  vision_model: string;
  ollama_endpoint: string;
  gemini_api_key: string;
  anthropic_api_key: string;
  few_shot_correction_window: number;
}>;

export async function getAdminSettings(): Promise<AdminSettings> {
  return apiFetch<AdminSettings>('/api/admin/settings');
}

export async function patchAdminSettings(body: AdminSettingsPatch): Promise<AdminSettings> {
  return apiFetch<AdminSettings>('/api/admin/settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}
