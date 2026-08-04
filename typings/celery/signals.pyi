"""Minimal local type stubs for ``celery.signals``.

Covers only the signals used by this project. Extend as needed.
"""

from collections.abc import Callable
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

class BaseSignal:
    def connect(self, fun: _F, **kwargs: Any) -> _F: ...

worker_process_init: BaseSignal
task_failure: BaseSignal
task_postrun: BaseSignal
