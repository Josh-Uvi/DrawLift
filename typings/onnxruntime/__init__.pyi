"""Minimal local type stubs for ``onnxruntime``.

ONNX Runtime does not ship a ``py.typed`` marker, so strict type checkers
report missing stubs and partially unknown member types. These stubs cover
only the ONNX Runtime surface used by this project (``SessionOptions``,
``GraphOptimizationLevel``, ``InferenceSession``, ``get_inputs``, ``run``).
Extend them here if new ONNX Runtime APIs are introduced.
"""

from collections.abc import Sequence
from enum import IntEnum
from typing import Any

import numpy as np

class GraphOptimizationLevel(IntEnum):
    ORT_DISABLE_ALL: int
    ORT_ENABLE_BASIC: int
    ORT_ENABLE_EXTENDED: int
    ORT_ENABLE_ALL: int

class SessionOptions:
    intra_op_num_threads: int
    inter_op_num_threads: int
    graph_optimization_level: GraphOptimizationLevel

class SessionInput:
    name: str

class InferenceSession:
    def __init__(
        self,
        path_or_bytes: str | bytes,
        *,
        providers: list[str] | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def get_inputs(self) -> Sequence[SessionInput]: ...
    def get_outputs(self) -> Sequence[SessionInput]: ...
    def run(
        self,
        output_names: Sequence[str] | None,
        input_feed: dict[str, np.ndarray],
        *,
        run_options: Any | None = ...,
    ) -> list[np.ndarray]: ...
