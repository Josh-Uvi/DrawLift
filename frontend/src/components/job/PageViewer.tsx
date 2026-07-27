"use client";

import { useState } from "react";
import ImageModal from "./ImageModal";
import { getPageImageUrl } from "@/lib/api";

interface PageViewerProps {
  jobId: string;
  pageCount: number;
}

export default function PageViewer({ jobId, pageCount }: PageViewerProps) {
  const [selectedPage, setSelectedPage] = useState<number | null>(null);

  if (pageCount === 0) {
    return null;
  }

  return (
    <div>
      <h3 className="mb-3 text-lg font-semibold text-gray-900">Page Preview</h3>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {Array.from({ length: pageCount }, (_, i) => i + 1).map((pageNum) => (
          <button
            key={pageNum}
            onClick={() => setSelectedPage(pageNum)}
            className="flex-shrink-0 overflow-hidden rounded-lg border border-gray-200 transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label={`View page ${pageNum}`}
          >
            <img
              src={getPageImageUrl(jobId, pageNum)}
              alt={`Page ${pageNum}`}
              className="h-40 w-28 object-cover"
              loading="lazy"
            />
            <div className="border-t border-gray-100 bg-gray-50 px-2 py-1 text-center text-xs text-gray-500">
              Page {pageNum}
            </div>
          </button>
        ))}
      </div>

      {selectedPage !== null && (
        <ImageModal
          src={getPageImageUrl(jobId, selectedPage)}
          alt={`Page ${selectedPage}`}
          onClose={() => setSelectedPage(null)}
        />
      )}
    </div>
  );
}
