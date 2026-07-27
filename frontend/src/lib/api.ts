import type { Job, JobConfig, JobCreateResponse, JobListResponse } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function uploadFile(file: File, config: JobConfig): Promise<JobCreateResponse> {
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

export function getPageImageUrl(jobId: string, pageNumber: number): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/pages/${pageNumber}`;
}

export function getJobDownloadUrl(jobId: string, format: "dxf" | "dwg" | "glb" = "dxf"): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/download?format=${format}`;
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch job");
  }
  return response.json();
}

export async function listJobs(status?: string, limit = 50, offset = 0): Promise<JobListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("page", String(Math.floor(offset / limit) + 1));
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const response = await fetch(`${API_BASE}/api/v1/jobs?${params}`);
  if (!response.ok) {
    throw new Error("Failed to fetch jobs");
  }
  return response.json();
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to delete job" }));
    throw new Error(error.detail || "Failed to delete job");
  }
}

export async function retryJob(jobId: string): Promise<JobCreateResponse> {
  const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/retry`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Failed to retry job" }));
    throw new Error(error.detail || "Failed to retry job");
  }
  return response.json();
}
