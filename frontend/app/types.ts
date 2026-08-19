export type GenerationStatus = "QUEUED" | "GENERATING" | "COMPLETED" | "FAILED" | "CANCELLED";

export type GenerationImage = {
  id: string;
  url: string;
  selected: boolean;
  score: number | null;
  seed: number | null;
};

export type GenerationResponse = {
  job_id: string;
  status: GenerationStatus;
  status_message: string | null;
  progress: number;
  prompt: string;
  expanded_prompt: string | null;
  width: number | null;
  height: number | null;
  candidate_count: number;
  seed: number | null;
  images: GenerationImage[];
  generation_time_ms: number | null;
  ranking_time_ms: number | null;
  upscale_time_ms: number | null;
  error_code: string | null;
  error_message: string | null;
};

export type GenerationHistoryItem = GenerationResponse & {
  created_at: string;
  completed_at: string | null;
};

export type GenerationHistoryResponse = {
  generations: GenerationHistoryItem[];
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    role: string;
    plan?: string;
  };
};

export type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type ApiKeyListResponse = {
  api_keys: ApiKey[];
};

export type ApiKeyCreateResponse = ApiKey & {
  api_key: string;
};

export type LimitsResponse = {
  rate_limit_per_minute: number;
  rate_limit_remaining: number;
  rate_limit_reset_seconds: number;
  concurrent_limit: number;
  active_jobs: number;
  monthly_quota: number;
  monthly_used: number;
  monthly_remaining: number;
  monthly_reset_at: string;
};

export type SystemStatus = {
  uptime_seconds: number;
  load_1m: number;
  load_5m: number;
  load_15m: number;
  cpu_count: number;
  memory_used_percent: number;
  disk_used_percent: number;
  jobs_queued: number;
  jobs_generating: number;
  jobs_completed: number;
  jobs_failed: number;
  jobs_cancelled: number;
  worker: WorkerStatus | null;
};

export type WorkerStatus = {
  status: string;
  backend: string;
  preloaded: boolean;
  gpus: GpuStatus[];
};

export type GpuStatus = {
  index: number;
  name: string;
  utilization_gpu_percent: number;
  memory_used_mib: number;
  memory_total_mib: number;
  temperature_c: number;
  power_draw_w: number | null;
};
