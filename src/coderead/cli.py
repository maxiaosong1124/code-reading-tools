from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import uuid4

from coderead.graph import build_flow_graph
from coderead.mermaid import render_mermaid
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
    args.out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(run_proxy(args.real_adapter))
