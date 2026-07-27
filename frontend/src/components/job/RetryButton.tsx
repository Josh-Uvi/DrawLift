"use client";

import { useState } from "react";
import { toast } from "sonner";
import Button from "@/components/shared/Button";
import { retryJob } from "@/lib/api";

interface RetryButtonProps {
  jobId: string;
  onRetried?: () => void;
}

export default function RetryButton({ jobId, onRetried }: RetryButtonProps) {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await retryJob(jobId);
      toast.success("Job re-queued with the same conversion settings.");
      onRetried?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to retry job");
    } finally {
      setRetrying(false);
    }
  };

  return (
    <Button onClick={handleRetry} disabled={retrying} className="w-full">
      {retrying ? "Retrying…" : "Retry conversion"}
    </Button>
  );
}
