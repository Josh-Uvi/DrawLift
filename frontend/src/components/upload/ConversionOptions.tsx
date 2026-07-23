"use client";

import { JobConfig } from "@/types/api";

interface ConversionOptionsProps {
  config: JobConfig;
  onChange: (config: JobConfig) => void;
  disabled?: boolean;
}

export default function ConversionOptions({
  config,
  onChange,
  disabled = false,
}: ConversionOptionsProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">Mode</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onChange({ ...config, mode: "2d" })}
            disabled={disabled}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              config.mode === "2d"
                ? "bg-primary text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
          >
            2D
          </button>
          <button
            type="button"
            onClick={() => onChange({ ...config, mode: "3d" })}
            disabled={disabled}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              config.mode === "3d"
                ? "bg-primary text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
          >
            3D
          </button>
        </div>
      </div>

      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">
          DPI: {config.dpi}
        </label>
        <input
          type="range"
          min={150}
          max={600}
          step={150}
          value={config.dpi}
          onChange={(e) => onChange({ ...config, dpi: Number(e.target.value) })}
          disabled={disabled}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>150</span>
          <span>300</span>
          <span>600</span>
        </div>
      </div>

      {config.mode === "3d" && (
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Floor Height (m)
          </label>
          <input
            type="number"
            min={0.5}
            max={10}
            step={0.1}
            value={config.floor_height_m}
            onChange={(e) =>
              onChange({ ...config, floor_height_m: Number(e.target.value) })
            }
            disabled={disabled}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
        </div>
      )}

      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">
          Output Format
        </label>
        <select
          value={config.output_format}
          onChange={(e) =>
            onChange({ ...config, output_format: e.target.value as "dxf" | "dwg" })
          }
          disabled={disabled}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        >
          <option value="dxf">DXF</option>
          <option value="dwg">DWG</option>
        </select>
      </div>
    </div>
  );
}