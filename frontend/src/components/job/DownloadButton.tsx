"use client";

import Button from "@/components/shared/Button";
import { getJobDownloadUrl } from "@/lib/api";

interface DownloadButtonProps {
  jobId: string;
  isReady: boolean;
  is3D?: boolean;
  outputFormat?: "dxf" | "dwg" | "both";
}

export default function DownloadButton({
  jobId,
  isReady,
  is3D = false,
  outputFormat = "dxf",
}: DownloadButtonProps) {
  if (!isReady) {
    return null;
  }

  return (
    <div className="space-y-2">
      {(outputFormat === "dxf" || outputFormat === "both") && (
        <a href={getJobDownloadUrl(jobId, "dxf")} download className="block">
          <Button variant="outline" className="w-full">
            Download DXF
          </Button>
        </a>
      )}
      {(outputFormat === "dwg" || outputFormat === "both") && (
        <a href={getJobDownloadUrl(jobId, "dwg")} download className="block">
          <Button variant="outline" className="w-full">
            Download DWG
          </Button>
        </a>
      )}
      {is3D && (
        <a href={getJobDownloadUrl(jobId, "glb")} download className="block">
          <Button variant="outline" className="w-full">
            Download 3D Model (GLB)
          </Button>
        </a>
      )}
    </div>
  );
}
