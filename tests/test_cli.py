from coderead.cli import main
from coderead.dap import encode_message
from coderead.cli import create_proxy_trace_observers
from coderead.models import StackFrame, TraceEvent
from coderead.store import dump_events_jsonl, load_events_jsonl


def event(event_id: str, function: str, line: int) -> TraceEvent:
    frame = StackFrame(function=function, file="/repo/app.py", line=line, language="python")
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
    assert len(injected) == 1
    assert len(events) == 1
    assert events[0].command_before_stop == "next"
    assert events[0].top_frame.function == "main"
