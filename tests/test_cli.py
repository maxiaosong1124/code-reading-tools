from coderead.cli import main
import coderead.cli as cli
import sys
import tomllib
from coderead.dap import encode_message
from coderead.cli import create_proxy_trace_observers
from coderead.models import StackFrame, TraceEvent
from coderead.store import TraceStore, dump_events_jsonl, load_events_jsonl


def event(event_id: str, function: str, line: int, file: str = "/repo/app.py") -> TraceEvent:
    frame = StackFrame(function=function, file=file, line=line, language="python")
    return TraceEvent(
        id=event_id,
        session_id="sess_cli",
        timestamp=f"2026-05-05T10:32:{int(event_id.removeprefix('evt_')):02d}.000Z",
        adapter="debugpy",
        event_type="stopped",
        reason="step",
        command_before_stop="next",
        thread_id=1,
        top_frame=frame,
        stack=[frame],
    )


def test_graph_command_writes_graph_json_and_mermaid(tmp_path):
    events_path = dump_events_jsonl(
        [event("evt_01", "main", 10), event("evt_02", "load", 20)],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(["graph", "--events", str(events_path), "--out-dir", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "graph.json").exists()
    assert (out_dir / "graph.mmd").exists()
    assert "flowchart TD" in (out_dir / "graph.mmd").read_text(encoding="utf-8")


def test_graph_command_defaults_to_function_view(tmp_path):
    events_path = dump_events_jsonl(
        [event("evt_01", "main", 10), event("evt_02", "main", 11)],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(["graph", "--events", str(events_path), "--out-dir", str(out_dir)])

    graph_json = (out_dir / "graph.json").read_text(encoding="utf-8")
    assert exit_code == 0
    assert graph_json.count('"function": "main"') == 1
    assert '"line": 10' in graph_json
    assert '"end_line": 11' in graph_json


def test_graph_command_can_render_line_view(tmp_path):
    events_path = dump_events_jsonl(
        [event("evt_01", "main", 10), event("evt_02", "main", 11)],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(["graph", "--events", str(events_path), "--out-dir", str(out_dir), "--view", "line"])

    graph_json = (out_dir / "graph.json").read_text(encoding="utf-8")
    assert exit_code == 0
    assert graph_json.count('"function": "main"') == 2


def test_graph_command_can_render_function_view(tmp_path):
    events_path = dump_events_jsonl(
        [event("evt_01", "main", 10), event("evt_02", "main", 11)],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(["graph", "--events", str(events_path), "--out-dir", str(out_dir), "--view", "function"])

    graph_json = (out_dir / "graph.json").read_text(encoding="utf-8")
    assert exit_code == 0
    assert '"kinds": [\n        "function"\n      ]' in graph_json


def test_graph_command_writes_trace_markdown_with_scenario(tmp_path):
    events_path = dump_events_jsonl(
        [event("evt_01", "main", 10), event("evt_02", "load", 20)],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "graph",
            "--events",
            str(events_path),
            "--out-dir",
            str(out_dir),
            "--scenario",
            "验证配置加载路径",
        ]
    )

    trace_md = (out_dir / "trace.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "# Trace: 验证配置加载路径" in trace_md
    assert "```mermaid" in trace_md
    assert "`main`" in trace_md


def test_graph_command_writes_trace_html(tmp_path):
    events_path = dump_events_jsonl(
        [event("evt_01", "main", 10), event("evt_02", "load", 20)],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(["graph", "--events", str(events_path), "--out-dir", str(out_dir), "--scenario", "加载配置"])

    trace_html = (out_dir / "trace.html").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "Trace Viewer" in trace_html
    assert "加载配置" in trace_html


def test_graph_command_applies_vllm_profile_and_writes_profile_metadata(tmp_path):
    events_path = dump_events_jsonl(
        [
            event("evt_01", "step", 10, "/repo/vllm/vllm/engine/llm_engine.py"),
            event("evt_02", "forward", 20, "/repo/.venv/lib/python3.12/site-packages/torch/nn/modules/module.py"),
            event("evt_03", "schedule", 30, "/repo/vllm/vllm/core/scheduler.py"),
        ],
        tmp_path / "events.jsonl",
    )
    out_dir = tmp_path / "out"

    exit_code = main(["graph", "--events", str(events_path), "--out-dir", str(out_dir), "--profile", "vllm"])

    graph_json = (out_dir / "graph.json").read_text(encoding="utf-8")
    trace_html = (out_dir / "trace.html").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "llm_engine.py" in graph_json
    assert "scheduler.py" in graph_json
    assert "module.py" not in graph_json
    assert '"vllm_module": "engine"' in graph_json
    assert '"profile": "vllm"' in trace_html


def test_init_command_writes_coderead_config_and_vscode_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--profile", "vllm", "--program", "examples/offline_inference.py", "--scenario", "vLLM 离线推理"])

    config = (tmp_path / ".coderead" / "config.json").read_text(encoding="utf-8")
    launch_json = (tmp_path / ".vscode" / "launch.json").read_text(encoding="utf-8")
    tasks_json = (tmp_path / ".vscode" / "tasks.json").read_text(encoding="utf-8")
    assert exit_code == 0
    assert '"profile": "vllm"' in config
    assert '"program": "examples/offline_inference.py"' in config
    assert '"debugServer": 47111' in launch_json
    assert "CodeRead: Start Proxy" in tasks_json
    assert "coderead proxy-server" in tasks_json
    assert "debugpy.adapter" in tasks_json


def test_render_command_uses_latest_session_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init", "--profile", "default", "--program", "app.py", "--scenario", "普通 Python"])
    older = TraceStore.create(tmp_path / ".coderead-traces", session_id="sess_old", adapter="debugpy", scenario="old")
    latest = TraceStore.create(tmp_path / ".coderead-traces", session_id="sess_new", adapter="debugpy", scenario="new")
    dump_events_jsonl([event("evt_01", "main", 1), event("evt_02", "load", 2)], latest.events_path)
    dump_events_jsonl([event("evt_01", "ignored", 9)], older.events_path)

    exit_code = main(["render"])

    trace_html = tmp_path / ".coderead-traces" / "sess_new_output" / "trace.html"
    assert exit_code == 0
    assert trace_html.exists()
    assert "Trace Viewer" in trace_html.read_text(encoding="utf-8")


def test_watch_once_renders_latest_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init", "--profile", "vllm", "--program", "examples/offline_inference.py"])
    store = TraceStore.create(tmp_path / ".coderead-traces", session_id="sess_watch", adapter="debugpy", scenario="watch")
    dump_events_jsonl(
        [
            event("evt_01", "step", 10, "/repo/vllm/vllm/engine/llm_engine.py"),
            event("evt_02", "schedule", 30, "/repo/vllm/vllm/core/scheduler.py"),
        ],
        store.events_path,
    )

    exit_code = main(["watch", "--once"])

    trace_html = tmp_path / ".coderead-traces" / "sess_watch_output" / "trace.html"
    assert exit_code == 0
    assert trace_html.exists()
    assert '"profile": "vllm"' in trace_html.read_text(encoding="utf-8")


def test_samples_vscode_prints_generic_debugpy_launch_json(capsys):
    exit_code = main(["samples", "vscode"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"debugServer": 47111' in output
    assert '"type": "debugpy"' in output
    assert "CodeRead" in output
    assert "vllm" not in output.lower()


def test_render_command_auto_detects_vllm_without_project_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = TraceStore.create(tmp_path / ".coderead-traces", session_id="sess_auto", adapter="debugpy", scenario="auto")
    dump_events_jsonl(
        [
            event("evt_01", "step", 10, "/repo/vllm/vllm/engine/llm_engine.py"),
            event("evt_02", "forward", 20, "/repo/.venv/lib/python3.12/site-packages/torch/nn/modules/module.py"),
            event("evt_03", "schedule", 30, "/repo/vllm/vllm/core/scheduler.py"),
        ],
        store.events_path,
    )

    exit_code = main(["render"])

    graph_json = (tmp_path / ".coderead-traces" / "sess_auto_output" / "graph.json").read_text(encoding="utf-8")
    trace_html = (tmp_path / ".coderead-traces" / "sess_auto_output" / "trace.html").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "llm_engine.py" in graph_json
    assert "scheduler.py" in graph_json
    assert "module.py" not in graph_json
    assert '"profile": "vllm"' in trace_html


def test_serve_command_uses_generic_proxy_defaults(monkeypatch):
    calls = {}

    async def fake_run_proxy_server(real_adapter, *, host, port, observer_factory, on_listening):
        calls["real_adapter"] = real_adapter
        calls["host"] = host
        calls["port"] = port
        calls["observer_factory"] = observer_factory
        on_listening(host, port)
        return 0

    monkeypatch.setattr(cli, "run_proxy_server", fake_run_proxy_server)

    exit_code = main(["serve"])

    assert exit_code == 0
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 47111
    assert calls["real_adapter"] == [sys.executable, "-m", "debugpy.adapter"]


def test_init_task_uses_current_python_for_debugpy_adapter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--program", "app.py"])

    tasks_json = (tmp_path / ".vscode" / "tasks.json").read_text(encoding="utf-8")
    assert exit_code == 0
    assert f"{sys.executable} -m debugpy.adapter" in tasks_json


def test_pyproject_declares_debugpy_runtime_dependency():
    pyproject = tomllib.loads((cli.Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))

    assert "debugpy>=1.8" in pyproject["project"]["dependencies"]


def test_proxy_trace_observers_write_captured_events(tmp_path):
    client_observer, adapter_observer, store = create_proxy_trace_observers(
        out_dir=tmp_path,
        adapter="debugpy",
        session_id="sess_proxy",
    )

    assert client_observer(
        encode_message({"seq": 1, "type": "request", "command": "next"})
    ) == []
    injected = adapter_observer(
        encode_message(
            {
                "seq": 2,
                "type": "event",
                "event": "stopped",
                "body": {"reason": "step", "threadId": 1},
            }
        )
    )
    adapter_observer(
        encode_message(
            {
                "seq": 3,
                "type": "response",
                "request_seq": 1,
                "success": True,
                "command": "stackTrace",
                "body": {
                    "stackFrames": [
                        {
                            "id": 1,
                            "name": "main",
                            "source": {"path": "/repo/app.py"},
                            "line": 10,
                            "column": 1,
                        }
                    ]
                },
            }
        )
    )

    events = load_events_jsonl(store.events_path)
    assert len(injected.inject_to_writer) == 1
    assert len(events) == 1
    assert events[0].command_before_stop == "next"
    assert events[0].top_frame.function == "main"
