from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import uuid4

from coderead.dap_capture import DapTraceCapture
from coderead.graph import build_flow_graph
from coderead.mermaid import render_mermaid
from coderead.proxy import ByteObserver
from coderead.proxy import run_proxy
from coderead.store import TraceStore, dump_graph_json, load_events_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coderead")
    subparsers = parser.add_subparsers(dest="command", required=True)

    graph = subparsers.add_parser("graph", help="从 events.jsonl 生成 graph.json 和 graph.mmd")
    graph.add_argument("--events", required=True, type=Path)
    graph.add_argument("--out-dir", required=True, type=Path)
    graph.set_defaults(func=_graph_command)

    trace = subparsers.add_parser("trace", help="创建空 trace session")
    trace.add_argument("--out-dir", required=True, type=Path)
    trace.add_argument("--adapter", default="manual")
    trace.set_defaults(func=_trace_command)

    proxy = subparsers.add_parser("proxy", help="启动 experimental DAP proxy")
    proxy.add_argument("--out-dir", required=True, type=Path)
    proxy.add_argument("--real-adapter", required=True, nargs=argparse.REMAINDER)
    proxy.set_defaults(func=_proxy_command)

    return parser


def _graph_command(args: argparse.Namespace) -> int:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events_jsonl(args.events)
    graph = build_flow_graph(events)
    dump_graph_json(graph, args.out_dir / "graph.json")
    (args.out_dir / "graph.mmd").write_text(render_mermaid(graph), encoding="utf-8")
    return 0


def _trace_command(args: argparse.Namespace) -> int:
    session_id = f"sess_{uuid4().hex[:12]}"
    store = TraceStore.create(args.out_dir, session_id=session_id, adapter=args.adapter)
    print(store.session_dir)
    return 0


def _proxy_command(args: argparse.Namespace) -> int:
    if not args.real_adapter:
        raise SystemExit("--real-adapter requires a command")
    client_observer, adapter_observer, store = create_proxy_trace_observers(
        out_dir=args.out_dir,
        adapter="dap",
    )
    print(store.session_dir)
    return asyncio.run(
        run_proxy(
            args.real_adapter,
            on_client_chunk=client_observer,
            on_adapter_chunk=adapter_observer,
        )
    )


def create_proxy_trace_observers(
    *,
    out_dir: Path,
    adapter: str,
    session_id: str | None = None,
) -> tuple[ByteObserver, ByteObserver, TraceStore]:
    session = session_id or f"sess_{uuid4().hex[:12]}"
    store = TraceStore.create(out_dir, session_id=session, adapter=adapter)
    capture = DapTraceCapture(session_id=session, adapter=adapter)

    def client_observer(chunk: bytes) -> list[bytes]:
        injected = capture.observe_client_bytes(chunk)
        _flush_capture_events(capture, store)
        return injected

    def adapter_observer(chunk: bytes) -> list[bytes]:
        injected = capture.observe_adapter_bytes(chunk)
        _flush_capture_events(capture, store)
        return injected

    return client_observer, adapter_observer, store


def _flush_capture_events(capture: DapTraceCapture, store: TraceStore) -> None:
    for event in capture.pop_events():
        store.append_event(event)
