"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Card from "@/components/shared/Card";
import ProgressTracker from "@/components/job/ProgressTracker";
import PageViewer from "@/components/job/PageViewer";
import DownloadButton from "@/components/job/DownloadButton";
import { getJob } from "@/lib/api";
import type { Job } from "@/types/api";

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
        <div className="mt-6">
          <DownloadButton jobId={id} isReady={job?.status === "completed"} />
        </div>
      </Card>
    </div>
  );
}
