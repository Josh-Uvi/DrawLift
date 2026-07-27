"use client";

import Button from "@/components/shared/Button";
import { getJobDownloadUrl } from "@/lib/api";

interface DownloadButtonProps {
  jobId: string;
  isReady: boolean;
}

export default function DownloadButton({ jobId, isReady }: DownloadButtonProps) {
  if (!isReady) {
    return null;
  }

  return (
    <a href={getJobDownloadUrl(jobId)} download className="block">
      <Button variant="outline" className="w-full">
        Download DXF
      </Button>
    </a>
  );
}
