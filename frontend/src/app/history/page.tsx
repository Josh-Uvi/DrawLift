"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";
import Card from "@/components/shared/Card";
import JobTable from "@/components/history/JobTable";
import { listJobs } from "@/lib/api";
import type { Job, JobStatus } from "@/types/api";

const STATUSES: Array<JobStatus | "all"> = [
  "all",
  "pending",
  "queued",
  "processing",
  "completed",
  "failed",
  "archived",
];

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<JobStatus | "all">("all");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const selectedStatus = useMemo(() => (status === "all" ? undefined : status), [status]);
  const sortedJobs = useMemo(
    () =>
      [...jobs].sort((a, b) => {
        const left = new Date(a.created_at).getTime();
        const right = new Date(b.created_at).getTime();
        return sortDirection === "desc" ? right - left : left - right;
      }),
    [jobs, sortDirection]
  );

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listJobs(selectedStatus, 50, 0);
      setJobs(response.jobs);
      setTotal(response.total);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, [selectedStatus]);

  useEffect(() => {
    startTransition(() => {
      loadJobs();
    });
  }, [loadJobs]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href="/" className="text-sm text-primary hover:underline">
            ← Back to upload
          </Link>
          <h1 className="mt-3 text-3xl font-bold text-gray-900">Conversion History</h1>
          <p className="mt-1 text-sm text-gray-600">
            Review, reopen, filter, and delete past jobs.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm font-medium text-gray-700">
            Status
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as JobStatus | "all")}
              className="ml-2 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            >
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value === "all" ? "All statuses" : value}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">
            Date sort
            <select
              value={sortDirection}
              onChange={(event) => setSortDirection(event.target.value as "desc" | "asc")}
              className="ml-2 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            >
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </label>
        </div>
      </div>

      <Card title={`Jobs (${total})`}>
        {loading && <p className="text-sm text-gray-600">Loading jobs…</p>}
        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {!loading && !error && <JobTable jobs={sortedJobs} onDeleted={loadJobs} />}
      </Card>
    </div>
  );
}
