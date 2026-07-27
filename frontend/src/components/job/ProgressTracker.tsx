"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    if (initialStatus === "completed" || initialStatus === "failed") {
      return;
    }

    const eventSource = createSSEStream(
      jobId,
      (event: SSEProgressEvent) => {
        setProgress(event.progress);
        setStep(event.step);
        setStatus(event.status);
      },
      (error) => {
        console.error("SSE error:", error);
        setStatus("failed");
      },
      onComplete
    );

    return () => eventSource.close();
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
    </div>
  );
}
