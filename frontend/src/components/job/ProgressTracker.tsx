"use client";

import { useEffect, useState } from "react";
import { getJob } from "@/lib/api";
import { createSSEStream } from "@/lib/sse";
import { SSEProgressEvent, JobStatus } from "@/types/api";

interface ProgressTrackerProps {
  jobId: string;
  initialProgress?: number;
  initialStatus?: JobStatus;
  initialStep?: string | null;
  onComplete?: () => void;
}

const STATUS_COLORS: Record<JobStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  queued: "bg-blue-100 text-blue-800",
  processing: "bg-purple-100 text-purple-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  archived: "bg-gray-200 text-gray-800",
};

export default function ProgressTracker({
  jobId,
  initialProgress = 0,
  initialStatus = "pending",
  initialStep = "",
  onComplete,
}: ProgressTrackerProps) {
  const [progress, setProgress] = useState(initialProgress);
  const [step, setStep] = useState(initialStep || "");
  const [status, setStatus] = useState<JobStatus>(initialStatus);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (
      initialStatus === "completed" ||
      initialStatus === "failed" ||
      initialStatus === "archived"
    ) {
      return;
    }

    const eventSource = createSSEStream(
      jobId,
      (event: SSEProgressEvent) => {
        setProgress(event.progress);
        setStep(event.step);
        setStatus(event.status);
        setMessage(event.message ?? null);
      },
      (error) => {
        console.error("SSE error:", error);
        setStatus("failed");
      },
      onComplete
    );

    return () => eventSource.close();
  }, [initialStatus, jobId, onComplete]);

  // Poll the REST API as a fallback so the UI stays in sync when SSE
  // events are missed (Redis Pub/Sub does not replay past events).
  useEffect(() => {
    if (
      initialStatus === "completed" ||
      initialStatus === "failed" ||
      initialStatus === "archived"
    ) {
      return;
    }

    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | undefined;

    const poll = async () => {
      try {
        const job = await getJob(jobId);
        if (cancelled) return;

        if (job.status === "completed" || job.status === "failed" || job.status === "archived") {
          setProgress(job.progress);
          setStep(job.step ?? "");
          setStatus(job.status);
          setMessage(job.error_msg ?? null);
          if (interval) clearInterval(interval);
          onComplete?.();
          return;
        }

        // Only advance state; SSE may already be ahead of the database.
        setStatus((current) =>
          current === "pending" || current === "queued" ? job.status : current
        );
        setProgress((current) => Math.max(current, job.progress));
      } catch {
        // Transient polling errors are ignored; SSE remains the primary channel.
      }
    };

    interval = setInterval(poll, 3000);

    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
  }, [initialStatus, jobId, onComplete]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${STATUS_COLORS[status]}`}>
          {status}
        </span>
        <span className="text-sm text-gray-500">{progress}%</span>
      </div>

      <div className="h-4 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {step && (
        <p className="text-center text-sm text-gray-600">
          Current step: <span className="font-medium">{step}</span>
        </p>
      )}
      {(message || status === "failed") && (
        <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {message || "The conversion failed. Review the job details and try again."}
        </p>
      )}
    </div>
  );
}
