"use client";

import { use } from "react";
import Link from "next/link";
import Card from "@/components/shared/Card";
import Button from "@/components/shared/Button";
import ProgressTracker from "@/components/job/ProgressTracker";

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <div className="mb-6">
        <Link href="/" className="text-sm text-primary hover:underline">
          ← Back to upload
        </Link>
      </div>

      <Card title={`Job ${id}`}>
        <ProgressTracker jobId={id} />
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
