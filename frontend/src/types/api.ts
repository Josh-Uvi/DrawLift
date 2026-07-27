export type JobStatus = "pending" | "queued" | "processing" | "completed" | "failed";

export interface JobConfig {
  mode: "2d" | "3d";
  dpi: number;
  floor_height_m: number;
  output_format: "dxf" | "dwg";
  segmenter: "ml" | "classic";
}

export interface JobCreateResponse {
  job_id: string;
}

export interface Job {
  id: string;
  status: JobStatus;
  progress: number;
  step: string | null;
  config: JobConfig;
  input_file: string;
  output_file: string | null;
  page_count: number | null;
  error_msg: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}

export interface SSEProgressEvent {
  job_id: string;
  status: JobStatus;
  progress: number;
  step: string;
}
