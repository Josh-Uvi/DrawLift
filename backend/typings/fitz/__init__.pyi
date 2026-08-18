"""Minimal local type stubs for PyMuPDF's ``fitz`` import alias.

PyMuPDF is installed as ``pymupdf`` but is commonly imported as ``fitz``.
The package does not provide type stubs for this import name in the current
project environment, so Pylance reports ``Stub file not found for \"fitz\"``.
These stubs cover only the PDF rendering surface used by ``PdfParserStep``.
Extend them here if additional PyMuPDF APIs are introduced.
"""

from pathlib import Path
from types import TracebackType
from typing import Any

class Rect:
    width: float
    height: float

class Matrix:
    def __init__(self, zoom_x: float, zoom_y: float) -> None: ...

class Pixmap:
    def save(self, filename: str | Path, *args: Any, **kwargs: Any) -> None: ...

class Page:
    rect: Rect
    def get_pixmap(
        self,
        *,
        matrix: Matrix | None = ...,
        alpha: bool = ...,
        **kwargs: Any,
    ) -> Pixmap: ...

class Document:
    page_count: int
    def __enter__(self) -> Document: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def load_page(self, page_id: int) -> Page: ...

def open(filename: str | Path, *args: Any, **kwargs: Any) -> Document: ...
