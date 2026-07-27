"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import Card from "@/components/shared/Card";
import Button from "@/components/shared/Button";
import ProgressTracker from "@/components/job/ProgressTracker";
import PageViewer from "@/components/job/PageViewer";
import { getJob } from "@/lib/api";
import type { Job } from "@/types/api";

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    getJob(id)
      .then(setJob)
      .catch(() => {
        /* error handled by ProgressTracker SSE */
      });
  }, [id]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="mb-6">
        <Link href="/" className="text-sm text-primary hover:underline">
          ← Back to upload
        </Link>
      </div>

      <Card title={`Job ${id}`}>
        <ProgressTracker jobId={id} />
        {job && job.page_count && job.page_count > 0 && (
          <div className="mt-6">
            <PageViewer jobId={id} pageCount={job.page_count} />
          </div>
        )}
        <div className="mt-6">
          <a href={`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/jobs/${id}/download`}>
            <Button variant="outline" className="w-full">
              Download Result
            </Button>
          </a>
        </div>
      </Card>
    </div>
  );
}
