"""OpenCV-based image preprocessing for architectural drawings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.pipeline.context import PipelineContext
from app.pipeline.steps.base import PipelineStep

DEFAULT_GAUSSIAN_KERNEL: tuple[int, int] = (5, 5)
DEFAULT_ADAPTIVE_BLOCK_SIZE = 15
DEFAULT_ADAPTIVE_C = 5
DEFAULT_MAX_ANGLE_DEVIATION = 0.1


class OpenCVPreprocessor(PipelineStep):
    """Preprocess page images with grayscale, threshold, and deskew correction.

    This step consumes the ``page_images`` produced by :class:`PdfParserStep`
    and writes cleaned binary images to ``context.preprocessed`` as a list of
    filesystem paths.
    """

    name = "OpenCV Preprocessing"
    progress = 35

    def __init__(
        self,
        output_dir: Path | str | None = None,
        *,
        gaussian_kernel: tuple[int, int] = DEFAULT_GAUSSIAN_KERNEL,
        adaptive_block_size: int = DEFAULT_ADAPTIVE_BLOCK_SIZE,
        adaptive_c: int = DEFAULT_ADAPTIVE_C,
    ) -> None:
        """Create a preprocessor with an optional output directory override.

        Args:
            output_dir: Directory for preprocessed images. When ``None`` the
                step derives a ``preprocessed/`` folder next to the page images.
            gaussian_kernel: Kernel size for the Gaussian blur operation.
            adaptive_block_size: Neighborhood size for adaptive thresholding.
                Must be an odd integer greater than 1.
            adaptive_c: Constant subtracted from the mean in adaptive threshold.
        """
        self.output_dir = Path(output_dir) if output_dir is not None else None
        self.gaussian_kernel = gaussian_kernel
        self.adaptive_block_size = adaptive_block_size
        self.adaptive_c = adaptive_c

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Run grayscale, blur, threshold, and deskew on every page image."""
        if not context.page_images:
            raise ValueError(
                "OpenCV preprocessor requires page_images on the context. "
                "Ensure PdfParserStep runs before this step."
            )

        output_dir = self._resolve_output_dir(context)
        output_dir.mkdir(parents=True, exist_ok=True)

        preprocessed_images: list[Path] = []
        for page_index, image_path in enumerate(context.page_images, start=1):
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise FileNotFoundError(
                    f"Unable to read page image for preprocessing: {image_path}"
                )

            processed = self._process_image(image)
            output_path = output_dir / f"preprocessed_{page_index:04d}.png"
            cv2.imwrite(str(output_path), processed)
            preprocessed_images.append(output_path)

        context.preprocessed = preprocessed_images
        context.metadata["preprocessed_image_dir"] = output_dir
        context.metadata["preprocessed_count"] = len(preprocessed_images)

        self.publish_progress(
            context,
            progress=self.progress,
            message=f"Preprocessed {len(preprocessed_images)} page image(s)",
        )
        return context

    def _process_image(self, image: np.ndarray) -> np.ndarray:
        """Apply grayscale, Gaussian blur, adaptive threshold, and deskew."""
        grayscale = self._to_grayscale(image)
        blurred = self._apply_gaussian_blur(grayscale)
        binary = self._apply_adaptive_threshold(blurred)
        deskewed = self._deskew(binary)
        return deskewed

    @staticmethod
    def _to_grayscale(image: np.ndarray) -> np.ndarray:
        """Convert a BGR image to grayscale."""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def _apply_gaussian_blur(self, image: np.ndarray) -> np.ndarray:
        """Apply Gaussian blur to reduce noise before thresholding."""
        kernel = self.gaussian_kernel
        if kernel[0] <= 0 or kernel[1] <= 0:
            return image
        # OpenCV requires odd kernel dimensions for Gaussian blur.
        ksize = (
            kernel[0] if kernel[0] % 2 == 1 else kernel[0] + 1,
            kernel[1] if kernel[1] % 2 == 1 else kernel[1] + 1,
        )
        return cv2.GaussianBlur(image, ksize, 0)

    def _apply_adaptive_threshold(self, image: np.ndarray) -> np.ndarray:
        """Apply adaptive thresholding to produce a binary image."""
        block_size = self.adaptive_block_size
        if block_size % 2 == 0:
            block_size += 1
        if block_size <= 1:
            block_size = 3
        return cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            block_size,
            self.adaptive_c,
        )

    @staticmethod
    def _deskew(image: np.ndarray) -> np.ndarray:
        """Correct skew by detecting the dominant text/line angle and rotating."""
        contours, _ = cv2.findContours(
            image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return image

        angles: list[float] = []
        for contour in contours:
            if cv2.contourArea(contour) < 20:
                continue
            rect = cv2.minAreaRect(contour)
            angle = rect[-1]
            # minAreaRect returns angles in [-90, 0). Normalize to [-45, 45).
            if angle < -45:
                angle = 90 + angle
            angles.append(angle)

        if not angles:
            return image

        median_angle = float(np.median(angles))
        if abs(median_angle) < DEFAULT_MAX_ANGLE_DEVIATION:
            return image

        center = (
            image.shape[1] // 2,
            image.shape[0] // 2,
        )
        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        return cv2.warpAffine(
            image,
            rotation_matrix,
            (image.shape[1], image.shape[0]),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

    def _resolve_output_dir(self, context: PipelineContext) -> Path:
        """Resolve where preprocessed images should be written."""
        if self.output_dir is not None:
            return self.output_dir

        configured_dir: Any = context.config.get("preprocessed_image_dir")
        if configured_dir is not None:
            return Path(str(configured_dir))

        page_image_dir = context.metadata.get("page_image_dir")
        if page_image_dir is not None:
            return Path(str(page_image_dir)) / "preprocessed"

        return context.input_path.parent / context.job_id / "preprocessed"