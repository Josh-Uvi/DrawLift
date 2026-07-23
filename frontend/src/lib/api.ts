import type { Job, JobCreateResponse, JobListResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function uploadFile(
  file: File,
  config: {
    mode: "2d" | "3d";
    dpi: number;
    floor_height_m: number;
    output_format: "dxf" | "dwg";
  }
): Promise<JobCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("config", JSON.stringify(config));

  const response = await fetch(`${API_BASE}/api/v1/jobs`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch job");
  }
  return response.json();
}

export async function listJobs(
  status?: string,
  limit = 50,
  offset = 0
): Promise<JobListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status_filter", status);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const response = await fetch(`${API_BASE}/api/v1/jobs?${params}`);
  if (!response.ok) {
    throw new Error("Failed to fetch jobs");
  }
  return response.json();
}