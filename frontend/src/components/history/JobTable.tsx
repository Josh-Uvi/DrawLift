"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import Button from "@/components/shared/Button";
import { deleteJob } from "@/lib/api";
import type { Job } from "@/types/api";

interface JobTableProps {
  jobs: Job[];
  onDeleted: () => void;
}

export default function JobTable({ jobs, onDeleted }: JobTableProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (job: Job) => {
    const confirmed = window.confirm(
      `Delete job ${job.id}? This removes the uploaded PDF and generated outputs.`
    );
    if (!confirmed) return;

    setDeletingId(job.id);
    try {
      await deleteJob(job.id);
      toast.success("Job deleted");
      onDeleted();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete job");
    } finally {
      setDeletingId(null);
    }
  };

  if (jobs.length === 0) {
    return <p className="rounded-lg bg-gray-50 p-4 text-sm text-gray-600">No jobs found.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-4 py-3">Created</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Mode</th>
            <th className="px-4 py-3">Format</th>
            <th className="px-4 py-3">Progress</th>
            <th className="px-4 py-3">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {jobs.map((job) => (
            <tr key={job.id}>
              <td className="whitespace-nowrap px-4 py-3 text-gray-700">
                {new Date(job.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-3">
                <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                  {job.status}
                </span>
              </td>
              <td className="px-4 py-3 uppercase text-gray-700">{job.config.mode}</td>
              <td className="px-4 py-3 uppercase text-gray-700">{job.config.output_format}</td>
              <td className="px-4 py-3 text-gray-700">{job.progress}%</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-2">
                  <Link href={`/jobs/${job.id}`} className="text-primary hover:underline">
                    Open
                  </Link>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(job)}
                    disabled={deletingId === job.id}
                    className="text-red-700 hover:bg-red-50"
                  >
                    {deletingId === job.id ? "Deleting…" : "Delete"}
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
