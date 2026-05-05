from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coderead.graph import build_flow_graph, build_function_flow_graph, build_line_flow_graph
from coderead.mermaid import render_mermaid
from coderead.profiles import apply_graph_profile_metadata, apply_trace_profile
from coderead.report import render_trace_markdown
from coderead.store import dump_graph_json, load_events_jsonl, load_session_metadata
from coderead.viewer import render_trace_html

DEFAULT_PORT = 47111
DEFAULT_TRACE_DIR = ".coderead-traces"
CONFIG_PATH = Path(".coderead") / "config.json"
DEFAULT_REAL_ADAPTER = [sys.executable, "-m", "debugpy.adapter"]


@dataclass(frozen=True)
class RenderResult:
    events_path: Path
    out_dir: Path
    trace_html: Path


def init_project(
    *,
    root: Path,
    profile: str,
    program: str,
    scenario: str,
    port: int = DEFAULT_PORT,
    trace_dir: str = DEFAULT_TRACE_DIR,
) -> dict[str, Any]:
    config = {
        "profile": profile,
        "program": program,
        "scenario": scenario,
        "port": port,
        "trace_dir": trace_dir,
        "include_paths": [],
        "exclude_paths": [],
        "exclude_modules": _default_exclude_modules(profile),
        "real_adapter": DEFAULT_REAL_ADAPTER,
    }
    _write_json(root / CONFIG_PATH, config)
    _write_json(root / ".vscode" / "launch.json", _launch_json(program=program, port=port))
    _write_json(root / ".vscode" / "tasks.json", _tasks_json(config))
    return config


def render_latest(
    *,
    root: Path,
    events: Path | None = None,
    out_dir: Path | None = None,
    profile: str | None = None,
    scenario: str | None = None,
) -> RenderResult:
    config = load_config(root)
    events_path = events or latest_events_path(root / str(config.get("trace_dir", DEFAULT_TRACE_DIR)))
    output_dir = out_dir or events_path.parent.with_name(f"{events_path.parent.name}_output")
    requested_profile = profile or str(config.get("profile", "auto"))
    raw_events = load_events_jsonl(events_path)
    active_profile = resolve_profile(raw_events, requested_profile)
    active_scenario = scenario if scenario is not None else str(config.get("scenario", ""))
    include_paths = list(config.get("include_paths", []))
    exclude_paths = list(config.get("exclude_paths", []))
    exclude_modules = list(config.get("exclude_modules", []))
    _render_graph_outputs(
        events_path=events_path,
        out_dir=output_dir,
        view="trace",
        profile=active_profile,
        raw_events=raw_events,
        include_paths=include_paths,
        exclude_paths=exclude_paths,
        exclude_modules=exclude_modules,
        scenario=active_scenario,
    )
    return RenderResult(events_path=events_path, out_dir=output_dir, trace_html=output_dir / "trace.html")


def vscode_launch_sample(*, adapter: str = "debugpy", port: int = DEFAULT_PORT) -> dict[str, Any]:
    return {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "CodeRead: Python",
                "type": adapter,
                "request": "launch",
                "program": "${file}",
                "console": "integratedTerminal",
                "justMyCode": False,
                "subProcess": False,
                "debugServer": port,
            }
        ],
    }


def resolve_profile(events: list[Any], requested_profile: str) -> str:
    if requested_profile != "auto":
        return requested_profile
    return "vllm" if any(_looks_like_vllm_path(event.top_frame.file) for event in events) else "default"


def watch_latest(
    *,
    root: Path,
    once: bool,
    interval: float,
) -> RenderResult | None:
    last_signature: tuple[Path, int, int] | None = None
    while True:
        try:
            events_path = latest_events_path(root / str(load_config(root).get("trace_dir", DEFAULT_TRACE_DIR)))
        except FileNotFoundError:
            if once:
                raise
            time.sleep(interval)
            continue
        stat = events_path.stat()
        signature = (events_path, stat.st_mtime_ns, stat.st_size)
        if signature != last_signature:
            result = render_latest(root=root, events=events_path)
            if once:
                return result
            last_signature = signature
        time.sleep(interval)


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_PATH
    if not path.exists():
        return {
            "profile": "auto",
            "scenario": "",
            "trace_dir": DEFAULT_TRACE_DIR,
            "include_paths": [],
            "exclude_paths": [],
            "exclude_modules": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def latest_events_path(trace_root: Path) -> Path:
    candidates = [path for path in trace_root.glob("sess_*/events.jsonl") if path.exists() and path.stat().st_size > 0]
    if not candidates:
        raise FileNotFoundError(f"没有找到可渲染的 trace events: {trace_root}")
    return max(candidates, key=_session_sort_key)


def _session_sort_key(events_path: Path) -> tuple[str, int, str]:
    session_path = events_path.parent / "session.json"
    created_at = ""
    if session_path.exists():
        try:
            created_at = str(load_session_metadata(session_path).get("created_at", ""))
        except (OSError, json.JSONDecodeError):
            created_at = ""
    return (created_at, events_path.stat().st_mtime_ns, events_path.parent.name)


def _render_graph_outputs(
    *,
    events_path: Path,
    out_dir: Path,
    view: str,
    profile: str,
    raw_events: list[Any] | None = None,
    include_paths: list[str],
    exclude_paths: list[str],
    exclude_modules: list[str],
    scenario: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    events = raw_events if raw_events is not None else load_events_jsonl(events_path)
    events = apply_trace_profile(
        events,
        profile=profile,
        include_paths=include_paths,
        exclude_paths=exclude_paths,
        exclude_modules=exclude_modules,
    )
    graph = _build_graph_for_view(events, view)
    apply_graph_profile_metadata(graph, profile=profile)
    dump_graph_json(graph, out_dir / "graph.json")
    mermaid = render_mermaid(graph)
    (out_dir / "graph.mmd").write_text(mermaid, encoding="utf-8")
    session = _load_session_for_events(events_path)
    session.update(
        {
            "profile": profile,
            "include_paths": include_paths,
            "exclude_paths": exclude_paths,
            "exclude_modules": exclude_modules,
        }
    )
    active_scenario = scenario or session.get("scenario", "")
    (out_dir / "trace.md").write_text(
        render_trace_markdown(graph=graph, mermaid=mermaid, scenario=active_scenario, session=session),
        encoding="utf-8",
    )
    (out_dir / "trace.html").write_text(
        render_trace_html(graph=graph, scenario=active_scenario, session=session),
        encoding="utf-8",
    )


def _build_graph_for_view(events: list[Any], view: str):
    if view == "line":
        return build_line_flow_graph(events)
    if view == "function":
        return build_function_flow_graph(events)
    return build_flow_graph(events)


def _load_session_for_events(events_path: Path) -> dict[str, Any]:
    session_path = events_path.parent / "session.json"
    if not session_path.exists():
        return {}
    return load_session_metadata(session_path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _launch_json(*, program: str, port: int) -> dict[str, Any]:
    return {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "CodeRead: Python",
                "type": "debugpy",
                "request": "launch",
                "program": "${workspaceFolder}/" + program,
                "console": "integratedTerminal",
                "justMyCode": False,
                "subProcess": False,
                "debugServer": port,
                "preLaunchTask": "CodeRead: Start Proxy",
            }
        ],
    }


def _tasks_json(config: dict[str, Any]) -> dict[str, Any]:
    port = int(config["port"])
    trace_dir = str(config["trace_dir"])
    scenario = str(config.get("scenario", ""))
    real_adapter = " ".join(str(part) for part in config.get("real_adapter", DEFAULT_REAL_ADAPTER))
    return {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "CodeRead: Start Proxy",
                "type": "shell",
                "command": (
                    "coderead proxy-server "
                    f"--host 127.0.0.1 --port {port} --out-dir {trace_dir} "
                    f'--scenario "{scenario}" '
                    f"--real-adapter {real_adapter}"
                ),
                "isBackground": True,
                "problemMatcher": {
                    "pattern": [{"regexp": ".", "file": 1, "location": 2, "message": 3}],
                    "background": {
                        "activeOnStart": True,
                        "beginsPattern": "coderead proxy-server listening",
                        "endsPattern": "coderead proxy-server listening",
                    },
                },
            }
        ],
    }


def _default_exclude_modules(profile: str) -> list[str]:
    if profile == "vllm":
        return ["torch", "transformers", "ray"]
    return []


def _looks_like_vllm_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/vllm/" in normalized or "/site-packages/vllm/" in normalized or "/dist-packages/vllm/" in normalized
