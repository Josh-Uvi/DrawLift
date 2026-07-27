"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Stage, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { getJobDownloadUrl } from "@/lib/api";
import Button from "@/components/shared/Button";

interface Model3DPreviewProps {
  jobId: string;
}

function Model({ url, wireframe }: { url: string; wireframe: boolean }) {
  const { scene } = useGLTF(url);

  const clonedScene = useMemo(() => scene.clone(true), [scene]);

  useEffect(() => {
    clonedScene.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => {
          if (material instanceof THREE.MeshStandardMaterial || "wireframe" in material) {
            (material as THREE.MeshStandardMaterial).wireframe = wireframe;
          }
        });
      }
    });
  }, [clonedScene, wireframe]);

  return <primitive object={clonedScene} />;
}

export default function Model3DPreview({ jobId }: Model3DPreviewProps) {
  const [wireframe, setWireframe] = useState(false);
  const modelUrl = getJobDownloadUrl(jobId, "glb");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">3D Model Preview</h3>
        <Button
          variant="outline"
          className="px-3 py-1 text-xs"
          onClick={() => setWireframe((value) => !value)}
        >
          {wireframe ? "Solid shading" : "Wireframe"}
        </Button>
      </div>
      <div className="h-96 w-full overflow-hidden rounded-lg border border-gray-200 bg-gray-900">
        <Canvas camera={{ position: [10, 10, 10], fov: 50 }} dpr={[1, 2]}>
          <Suspense fallback={null}>
            <Stage environment="city" intensity={0.5} adjustCamera>
              <Model url={modelUrl} wireframe={wireframe} />
            </Stage>
          </Suspense>
          <OrbitControls enablePan enableZoom enableRotate makeDefault />
        </Canvas>
      </div>
      <p className="text-center text-xs text-gray-500">
        Drag to rotate · scroll to zoom · right-click drag to pan
      </p>
    </div>
  );
}
