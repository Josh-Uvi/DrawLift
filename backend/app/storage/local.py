"""Storage adapter for local filesystem (dev) with pluggable backend interface."""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


class StorageBackend(ABC):
    """Abstract storage backend for file persistence."""

    @abstractmethod
    async def save(self, file: UploadFile, job_id: str) -> str:
        """Save an uploaded file and return its storage path."""
        ...

    @abstractmethod
    def get_path(self, job_id: str, filename: str) -> Path:
        """Return the path to a stored file."""
        ...

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        """Delete all files for a given job."""
        ...


class LocalStorage(StorageBackend):
    """Local filesystem storage implementation."""

    def __init__(self) -> None:
        self.base_path = Path(get_settings().STORAGE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, file: UploadFile, job_id: str) -> str:
        """Save uploaded file to local storage under the job's directory."""
        job_dir = self.base_path / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        file_path = job_dir / file.filename if file.filename else job_dir / "input.pdf"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        return str(file_path)

    def get_path(self, job_id: str, filename: str) -> Path:
        """Return the path to a stored file."""
        return self.base_path / job_id / filename

    async def delete(self, job_id: str) -> None:
        """Delete all files for a given job."""
        job_dir = self.base_path / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)


def get_storage() -> StorageBackend:
    """Factory returning the configured storage backend."""
    return LocalStorage()
