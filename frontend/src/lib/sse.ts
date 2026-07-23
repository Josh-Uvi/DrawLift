import type { SSEProgressEvent } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function createSSEStream(
  jobId: string,
  onProgress: (event: SSEProgressEvent) => void,
  onError?: (error: Event) => void,
  onComplete?: () => void
): EventSource {
  const eventSource = new EventSource(`${API_BASE}/api/v1/jobs/${jobId}/stream`);

  eventSource.addEventListener("progress", (event) => {
    try {
      const data: SSEProgressEvent = JSON.parse(event.data);
      onProgress(data);
      if (data.status === "completed" || data.status === "failed") {
        eventSource.close();
        onComplete?.();
      }
    } catch (e) {
      console.error("Failed to parse SSE event:", e);
    }
  });

  eventSource.onerror = (error) => {
    eventSource.close();
    onError?.(error);
  };

  return eventSource;
}