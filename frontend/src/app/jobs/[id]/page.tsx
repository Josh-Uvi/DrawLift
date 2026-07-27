"use client";

import { use, useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import Card from "@/components/shared/Card";
import ProgressTracker from "@/components/job/ProgressTracker";
import PageViewer from "@/components/job/PageViewer";
import DownloadButton from "@/components/job/DownloadButton";
import RetryButton from "@/components/job/RetryButton";
import { getJob } from "@/lib/api";
import type { Job } from "@/types/api";

const Model3DPreview = dynamic(() => import("@/components/job/Model3DPreview"), {
  ssr: false,
  loading: () => <p className="text-center text-sm text-gray-600">Loading 3D preview…</p>,
});

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);

  const refreshJob = useCallback(() => {
    getJob(id)
      .then(setJob)
      .catch(() => {
        /* error handled by ProgressTracker SSE */
      });
  }, [id]);

  useEffect(() => {
    refreshJob();
  }, [refreshJob]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="mb-6">
        <Link href="/" className="text-sm text-primary hover:underline">
          ← Back to upload
        </Link>
        <Link href="/history" className="ml-4 text-sm text-primary hover:underline">
          View history
        </Link>
      </div>

      <Card title={`Job ${id}`}>
        {job ? (
          <ProgressTracker
            jobId={id}
            initialProgress={job.progress}
            initialStatus={job.status}
            initialStep={job.step}
            onComplete={refreshJob}
          />
        ) : (
          <p className="text-center text-sm text-gray-600">Loading job status…</p>
        )}
        {job && job.page_count && job.page_count > 0 && (
          <div className="mt-6">
            <PageViewer jobId={id} pageCount={job.page_count} />
          </div>
        )}
        {job && job.status === "completed" && job.config?.mode === "3d" && (
          <div className="mt-6">
            <Model3DPreview jobId={id} />
          </div>
        )}
        {job && job.status === "failed" && (
          <div className="mt-6 space-y-3 rounded-lg border border-red-200 bg-red-50 p-4">
            <div>
              <h2 className="text-sm font-semibold text-red-900">Conversion failed</h2>
              <p className="mt-1 text-sm text-red-700">
                {job.error_msg || "The worker could not complete this conversion."}
              </p>
            </div>
            <RetryButton jobId={id} onRetried={refreshJob} />
          </div>
        )}
        <div className="mt-6">
          <DownloadButton
            jobId={id}
            isReady={job?.status === "completed"}
            is3D={job?.config?.mode === "3d"}
            outputFormat={job?.config?.output_format}
          />
        </div>
      </Card>
    </div>
  );
}
