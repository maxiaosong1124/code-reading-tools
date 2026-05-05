from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePath

from coderead.models import FlowGraph, StackFrame, TraceEvent

_DEFAULT_VLLM_EXCLUDE_MODULES = {
    "torch",
    "transformers",
    "ray",
    "numpy",
    "triton",
    "debugpy",
    "pluggy",
    "pytest",
}


def apply_trace_profile(
    events: Iterable[TraceEvent],
    *,
    profile: str,
    include_paths: list[str],
    exclude_paths: list[str],
    exclude_modules: list[str],
) -> list[TraceEvent]:
    if profile != "vllm":
        return list(events)
    excluded_modules = _DEFAULT_VLLM_EXCLUDE_MODULES | set(exclude_modules)
    return [
        _annotate_event(event, profile=profile)
        for event in events
        if _keep_vllm_event(
            event,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
            exclude_modules=excluded_modules,
        )
    ]


def classify_vllm_module(path: str) -> str:
    normalized = path.replace("\\", "/")
    lowered = normalized.lower()
    parts = PurePath(normalized).parts
    if "/vllm/" not in lowered and not lowered.endswith("/vllm"):
        return "entry"
    if "async_llm" in lowered or "async_llm_engine" in lowered:
        return "async_llm"
    if "/scheduler" in lowered or lowered.endswith("scheduler.py"):
        return "scheduler"
    if "kv_cache" in lowered or "cache_engine" in lowered or "block_manager" in lowered:
        return "kv_cache"
    if "triton" in lowered or "fused_moe" in lowered or "custom_op" in lowered:
        return "triton_kernel"
    if "attention" in lowered:
        return "attention"
    if "model_executor" in parts or "/model_executor/" in lowered:
        return "model_executor"
    if "/engine/" in lowered:
        return "engine"
    if "/worker/" in lowered:
        return "worker"
    return "vllm"


def apply_graph_profile_metadata(graph: FlowGraph, *, profile: str) -> None:
    if profile != "vllm":
        return
    for node in graph.nodes.values():
        node.metadata["profile"] = profile
        node.metadata["vllm_module"] = classify_vllm_module(node.file)


def _keep_vllm_event(
    event: TraceEvent,
    *,
    include_paths: list[str],
    exclude_paths: list[str],
    exclude_modules: set[str],
) -> bool:
    frame = event.top_frame
    path = frame.file
    if _matches_any_path(path, exclude_paths):
        return False
    if _module_root(frame) in exclude_modules:
        return False
    if _is_vllm_source(path):
        return True
    return _matches_any_path(path, include_paths)


def _annotate_event(event: TraceEvent, *, profile: str) -> TraceEvent:
    metadata = dict(event.metadata)
    metadata["profile"] = profile
    metadata["vllm_module"] = classify_vllm_module(event.top_frame.file)
    return TraceEvent(
        id=event.id,
        session_id=event.session_id,
        timestamp=event.timestamp,
        adapter=event.adapter,
        event_type=event.event_type,
        reason=event.reason,
        command_before_stop=event.command_before_stop,
        thread_id=event.thread_id,
        top_frame=event.top_frame,
        stack=event.stack,
        metadata=metadata,
    )


def _is_vllm_source(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/vllm/" in normalized or _package_root_from_path(path) == "vllm"


def _matches_any_path(path: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return False
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix.replace("\\", "/")) for prefix in prefixes)


def _module_root(frame: StackFrame) -> str:
    return _package_root_from_path(frame.file)


def _package_root_from_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = PurePath(normalized).parts
    for marker in ("site-packages", "dist-packages"):
        if marker in parts:
            index = parts.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1].split(".", 1)[0]
    return ""
