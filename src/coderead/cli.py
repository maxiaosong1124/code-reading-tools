from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from coderead.dap_capture import DapTraceCapture
from coderead.graph import build_flow_graph
from coderead.graph import build_function_flow_graph
from coderead.graph import build_line_flow_graph
from coderead.mermaid import render_mermaid
from coderead.profiles import apply_graph_profile_metadata, apply_trace_profile
from coderead.proxy import ByteObserver, PipeObservation
from coderead.proxy import run_proxy
from coderead.proxy import run_proxy_server
from coderead.report import render_trace_markdown
from coderead.store import TraceStore, dump_graph_json, load_events_jsonl, load_session_metadata
from coderead.viewer import render_trace_html
from coderead.workflow import DEFAULT_REAL_ADAPTER, init_project, render_latest, vscode_launch_sample, watch_latest


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
    graph.add_argument("--view", choices=["trace", "function", "line"], default="trace")
    graph.add_argument("--profile", choices=["default", "vllm"], default="default")
    graph.add_argument("--include-path", action="append", default=[])
    graph.add_argument("--exclude-path", action="append", default=[])
    graph.add_argument("--exclude-module", action="append", default=[])
    graph.add_argument("--scenario", default="")
    graph.set_defaults(func=_graph_command)

    trace = subparsers.add_parser("trace", help="创建空 trace session")
    trace.add_argument("--out-dir", required=True, type=Path)
    trace.add_argument("--adapter", default="manual")
    trace.add_argument("--scenario", default="")
    trace.set_defaults(func=_trace_command)

    proxy = subparsers.add_parser("proxy", help="启动 experimental DAP proxy")
    proxy.add_argument("--out-dir", required=True, type=Path)
    proxy.add_argument("--scenario", default="")
    proxy.add_argument("--real-adapter", required=True, nargs=argparse.REMAINDER)
    proxy.set_defaults(func=_proxy_command)

    proxy_server = subparsers.add_parser("proxy-server", help="启动 TCP DAP proxy，供 VS Code debugServer 连接")
    proxy_server.add_argument("--host", default="127.0.0.1")
    proxy_server.add_argument("--port", required=True, type=int)
    proxy_server.add_argument("--out-dir", required=True, type=Path)
    proxy_server.add_argument("--scenario", default="")
    proxy_server.add_argument("--real-adapter", required=True, nargs=argparse.REMAINDER)
    proxy_server.set_defaults(func=_proxy_server_command)

    serve = subparsers.add_parser("serve", help="启动通用 CodeRead DAP proxy，所有项目共用")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=47111)
    serve.add_argument("--out-dir", type=Path, default=Path(".coderead-traces"))
    serve.add_argument("--scenario", default="")
    serve.add_argument("--real-adapter", nargs=argparse.REMAINDER, default=DEFAULT_REAL_ADAPTER)
    serve.set_defaults(func=_serve_command)

    init = subparsers.add_parser("init", help="初始化 CodeRead 项目配置和 VS Code 调试配置")
    init.add_argument("--profile", choices=["default", "vllm"], default="default")
    init.add_argument("--program", default="app.py")
    init.add_argument("--scenario", default="")
    init.add_argument("--port", type=int, default=47111)
    init.set_defaults(func=_init_command)

    render = subparsers.add_parser("render", help="自动查找最新 trace session 并生成 trace.html")
    render.add_argument("--events", type=Path)
    render.add_argument("--out-dir", type=Path)
    render.add_argument("--profile", choices=["auto", "default", "vllm"])
    render.add_argument("--scenario")
    render.set_defaults(func=_render_command)

    watch = subparsers.add_parser("watch", help="监听最新 trace session 并自动生成 trace.html")
    watch.add_argument("--once", action="store_true")
    watch.add_argument("--interval", type=float, default=1.0)
    watch.set_defaults(func=_watch_command)

    samples = subparsers.add_parser("samples", help="输出通用接入样例，不写项目文件")
    sample_subparsers = samples.add_subparsers(dest="sample", required=True)
    vscode = sample_subparsers.add_parser("vscode", help="输出 VS Code launch.json debugpy 样例")
    vscode.add_argument("--adapter", default="debugpy")
    vscode.add_argument("--port", type=int, default=47111)
    vscode.set_defaults(func=_samples_vscode_command)

    return parser


def _graph_command(args: argparse.Namespace) -> int:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events_jsonl(args.events)
    events = apply_trace_profile(
        events,
        profile=args.profile,
        include_paths=args.include_path,
        exclude_paths=args.exclude_path,
        exclude_modules=args.exclude_module,
    )
    graph = _build_graph_for_view(events, args.view)
    apply_graph_profile_metadata(graph, profile=args.profile)
    dump_graph_json(graph, args.out_dir / "graph.json")
    mermaid = render_mermaid(graph)
    (args.out_dir / "graph.mmd").write_text(mermaid, encoding="utf-8")
    session = _load_session_for_events(args.events)
    session.update(
        {
            "profile": args.profile,
            "include_paths": args.include_path,
            "exclude_paths": args.exclude_path,
            "exclude_modules": args.exclude_module,
        }
    )
    scenario = args.scenario or session.get("scenario", "")
    (args.out_dir / "trace.md").write_text(
        render_trace_markdown(graph=graph, mermaid=mermaid, scenario=scenario, session=session),
        encoding="utf-8",
    )
    (args.out_dir / "trace.html").write_text(
        render_trace_html(graph=graph, scenario=scenario, session=session),
        encoding="utf-8",
    )
    return 0


def _trace_command(args: argparse.Namespace) -> int:
    session_id = f"sess_{uuid4().hex[:12]}"
    store = TraceStore.create(
        args.out_dir,
        session_id=session_id,
        adapter=args.adapter,
        scenario=args.scenario,
    )
    print(store.session_dir, file=sys.stderr)
    return 0


def _proxy_command(args: argparse.Namespace) -> int:
    if not args.real_adapter:
        raise SystemExit("--real-adapter requires a command")
    client_observer, adapter_observer, store = create_proxy_trace_observers(
        out_dir=args.out_dir,
        adapter="dap",
        scenario=args.scenario,
        command=list(args.real_adapter),
    )
    return asyncio.run(
        run_proxy(
            args.real_adapter,
            on_client_chunk=client_observer,
            on_adapter_chunk=adapter_observer,
            on_ready=lambda: print(store.session_dir, file=sys.stderr, flush=True),
        )
    )


def _proxy_server_command(args: argparse.Namespace) -> int:
    if not args.real_adapter:
        raise SystemExit("--real-adapter requires a command")

    def observer_factory() -> tuple[ByteObserver, ByteObserver]:
        client_observer, adapter_observer, store = create_proxy_trace_observers(
            out_dir=args.out_dir,
            adapter="dap",
            scenario=args.scenario,
            command=list(args.real_adapter),
        )
        print(store.session_dir, file=sys.stderr, flush=True)
        return client_observer, adapter_observer

    return asyncio.run(
        run_proxy_server(
            args.real_adapter,
            host=args.host,
            port=args.port,
            observer_factory=observer_factory,
            on_listening=lambda host, port: print(
                f"coderead proxy-server listening on {host}:{port}",
                file=sys.stderr,
                flush=True,
            ),
        )
    )


def _serve_command(args: argparse.Namespace) -> int:
    if not args.real_adapter:
        raise SystemExit("--real-adapter requires a command")

    def observer_factory() -> tuple[ByteObserver, ByteObserver]:
        client_observer, adapter_observer, store = create_proxy_trace_observers(
            out_dir=args.out_dir,
            adapter="dap",
            scenario=args.scenario,
            command=list(args.real_adapter),
        )
        print(store.session_dir, file=sys.stderr, flush=True)
        return client_observer, adapter_observer

    return asyncio.run(
        run_proxy_server(
            list(args.real_adapter),
            host=args.host,
            port=args.port,
            observer_factory=observer_factory,
            on_listening=lambda host, port: print(
                f"coderead serve listening on {host}:{port}",
                file=sys.stderr,
                flush=True,
            ),
        )
    )


def _init_command(args: argparse.Namespace) -> int:
    init_project(
        root=Path.cwd(),
        profile=args.profile,
        program=args.program,
        scenario=args.scenario,
        port=args.port,
    )
    print("CodeRead 配置已生成：.coderead/config.json、.vscode/launch.json、.vscode/tasks.json")
    return 0


def _render_command(args: argparse.Namespace) -> int:
    result = render_latest(
        root=Path.cwd(),
        events=args.events,
        out_dir=args.out_dir,
        profile=args.profile,
        scenario=args.scenario,
    )
    print(result.trace_html)
    return 0


def _watch_command(args: argparse.Namespace) -> int:
    result = watch_latest(root=Path.cwd(), once=args.once, interval=args.interval)
    if result is not None:
        print(result.trace_html)
    return 0


def _samples_vscode_command(args: argparse.Namespace) -> int:
    print(json.dumps(vscode_launch_sample(adapter=args.adapter, port=args.port), ensure_ascii=False, indent=2))
    return 0

def create_proxy_trace_observers(
    *,
    out_dir: Path,
    adapter: str,
    session_id: str | None = None,
    scenario: str | None = None,
    command: list[str] | None = None,
) -> tuple[ByteObserver, ByteObserver, TraceStore]:
    session = session_id or f"sess_{uuid4().hex[:12]}"
    store = TraceStore.create(out_dir, session_id=session, adapter=adapter, scenario=scenario, command=command)
    capture = DapTraceCapture(session_id=session, adapter=adapter)

    def client_observer(chunk: bytes) -> list[bytes]:
        injected = capture.observe_client_bytes(chunk)
        _flush_capture_events(capture, store)
        return injected

    def adapter_observer(chunk: bytes) -> list[bytes]:
        observed = capture.observe_adapter_bytes(chunk)
        _flush_capture_events(capture, store)
        return PipeObservation(
            inject_to_writer=observed.inject_to_adapter,
            forward_chunk=observed.forward_to_client,
        )

    return client_observer, adapter_observer, store


def _flush_capture_events(capture: DapTraceCapture, store: TraceStore) -> None:
    for event in capture.pop_events():
        store.append_event(event)


def _build_graph_for_view(events, view: str):
    if view == "line":
        return build_line_flow_graph(events)
    if view == "function":
        return build_function_flow_graph(events)
    return build_flow_graph(events)


def _load_session_for_events(events_path: Path) -> dict:
    session_path = events_path.parent / "session.json"
    if not session_path.exists():
        return {}
    return load_session_metadata(session_path)


if __name__ == "__main__":
    raise SystemExit(main())
