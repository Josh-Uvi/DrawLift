"""Minimal local type stubs for Celery.

Celery does not ship a ``py.typed`` marker, so strict type checkers
report missing stubs and partially unknown member types. These stubs
cover only the Celery surface used by this project. Extend them here
if new Celery APIs are introduced.
"""

from collections.abc import Callable
from typing import Any, TypeVar, overload

_F = TypeVar("_F", bound=Callable[..., Any])

class _Settings:
    def update(self, **settings: Any) -> None: ...

class Celery:
    conf: _Settings
    def __init__(
        self,
        main: str = ...,
        *,
        broker: str | None = ...,
        backend: str | None = ...,
        include: list[str] | None = ...,
        **kwargs: Any,
    ) -> None: ...
    @overload
    def task(self, fun: _F, **kwargs: Any) -> _F: ...
    @overload
    def task(self, **kwargs: Any) -> Callable[[_F], _F]: ...
