import json

from coderead.graph import build_flow_graph
from coderead.mermaid import render_mermaid
from coderead.models import StackFrame, TraceEvent
from coderead.store import TraceStore, dump_graph_json, load_events_jsonl


def make_event(event_id: str, function: str, line: int) -> TraceEvent:
    frame = StackFrame(function=function, file="/repo/app.py", line=line, language="python")
    return TraceEvent(
        id=event_id,
        session_id="sess_store",
        timestamp=f"2026-05-05T10:31:{int(event_id.removeprefix('evt_')):02d}.000Z",
        adapter="debugpy",
        event_type="stopped",
        reason="step",
        command_before_stop="next",
        thread_id=1,
        top_frame=frame,
        stack=[frame],
    )


def test_trace_store_writes_session_and_jsonl_events(tmp_path):
    store = TraceStore.create(tmp_path, session_id="sess_store", adapter="debugpy")
    first = make_event("evt_01", "main", 10)
    second = make_event("evt_02", "load", 20)

    store.append_event(first)
    store.append_event(second)

    session = json.loads((store.session_dir / "session.json").read_text(encoding="utf-8"))
    assert session["session_id"] == "sess_store"
    assert session["adapter"] == "debugpy"
    assert [event.id for event in load_events_jsonl(store.events_path)] == ["evt_01", "evt_02"]


def test_dump_graph_json_and_render_mermaid_with_repeated_edge(tmp_path):
    first = make_event("evt_01", "loop", 40)
    second = make_event("evt_02", "loop", 41)
    graph = build_flow_graph([first, second, first, second, first, second], loop_threshold=3)

    graph_path = dump_graph_json(graph, tmp_path / "graph.json")
    mermaid = render_mermaid(graph)

    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert len(graph_data["nodes"]) == 2
    assert graph_data["edges"][0]["count"] == 3
    assert "flowchart TD" in mermaid
    assert "x3" in mermaid
