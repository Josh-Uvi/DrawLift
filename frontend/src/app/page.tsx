"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import DropZone from "@/components/upload/DropZone";
import ConversionOptions from "@/components/upload/ConversionOptions";
import Button from "@/components/shared/Button";
import Card from "@/components/shared/Card";
import { uploadFile } from "@/lib/api";
import { JobConfig } from "@/types/api";

export default function HomePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [config, setConfig] = useState<JobConfig>({
    mode: "2d",
    dpi: 300,
    floor_height_m: 3.0,
    output_format: "dxf",
    segmenter: "classic",
  });
  const [uploading, setUploading] = useState(false);

  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile);
    toast.success(`Selected: ${selectedFile.name}`);
  };

  const handleSubmit = async () => {
    if (!file) {
      toast.error("Please select a PDF file first");
      return;
    }

    setUploading(true);
    try {
      const response = await uploadFile(file, config);
      toast.success("Job created! Redirecting...");
      router.push(`/jobs/${response.job_id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="mb-8 text-center">
        <h1 className="text-4xl font-bold text-gray-900">AI File Converter</h1>
        <p className="mt-2 text-lg text-gray-600">
          Convert architecture PDFs to DWG/DXF CAD models
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Upload PDF">
          <DropZone onFileSelect={handleFileSelect} disabled={uploading} />
          {file && (
            <div className="mt-4 flex items-center justify-between rounded-lg bg-gray-50 p-3">
              <span className="truncate text-sm text-gray-700">{file.name}</span>
              <span className="text-xs text-gray-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </span>
            </div>
          )}
        </Card>

        <Card title="Conversion Options">
          <ConversionOptions config={config} onChange={setConfig} disabled={uploading} />
          <div className="mt-6">
            <Button
              onClick={handleSubmit}
              disabled={!file || uploading}
              className="w-full"
              size="lg"
            >
              {uploading ? "Uploading..." : "Convert"}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
