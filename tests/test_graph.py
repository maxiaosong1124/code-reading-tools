from coderead.graph import build_flow_graph
from coderead.models import SourceLocation, StackFrame, TraceEvent


def frame(function: str, file: str, line: int, language: str = "python") -> StackFrame:
    return StackFrame(
        function=function,
        file=file,
        line=line,
        column=1,
        language=language,
    )


def stopped(
    event_id: str,
    function: str,
    file: str,
    line: int,
    *,
    stack: list[StackFrame] | None = None,
    thread_id: int = 1,
    command: str = "next",
) -> TraceEvent:
    top = frame(function, file, line)
    return TraceEvent(
        id=event_id,
        session_id="sess_test",
        timestamp=f"2026-05-05T10:30:{int(event_id.removeprefix('evt_')):02d}.000Z",
        adapter="debugpy",
        event_type="stopped",
        reason="step",
        command_before_stop=command,
        thread_id=thread_id,
        top_frame=top,
        stack=stack if stack is not None else [top],
    )


def edge(graph, source: SourceLocation, target: SourceLocation):
    return graph.edges[(source.node_id(), target.node_id())]


def test_builds_linear_flow_between_stopped_locations():
    events = [
        stopped("evt_01", "main", "/repo/app.py", 10),
        stopped("evt_02", "load", "/repo/app.py", 14),
        stopped("evt_03", "run", "/repo/app.py", 20),
    ]

    graph = build_flow_graph(events)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert edge(graph, events[0].top_frame.location, events[1].top_frame.location).count == 1
    assert edge(graph, events[1].top_frame.location, events[2].top_frame.location).count == 1


def test_marks_branch_when_same_node_has_multiple_targets():
    first = stopped("evt_01", "main", "/repo/app.py", 10)
    left = stopped("evt_02", "left", "/repo/app.py", 20)
    again = stopped("evt_03", "main", "/repo/app.py", 10)
    right = stopped("evt_04", "right", "/repo/app.py", 30)

    graph = build_flow_graph([first, left, again, right])

    branch_node = graph.nodes[first.top_frame.location.node_id()]
    assert branch_node.kinds == {"branch", "function_location"}
    assert len([edge for edge in graph.edges.values() if edge.from_id == branch_node.id]) == 2


def test_counts_repeated_edges_and_marks_loop_after_threshold():
    loop_a = stopped("evt_01", "loop", "/repo/app.py", 40)
    loop_b = stopped("evt_02", "loop", "/repo/app.py", 41)
    events = [loop_a, loop_b, loop_a, loop_b, loop_a, loop_b]

    graph = build_flow_graph(events, loop_threshold=3)

    repeated = edge(graph, loop_a.top_frame.location, loop_b.top_frame.location)
    assert repeated.count == 3
    assert repeated.kind == "loop"
    assert graph.nodes[loop_a.top_frame.location.node_id()].hit_count == 3


def test_detects_function_enter_and_return_from_stack_depth():
    main_frame = frame("main", "/repo/app.py", 10)
    helper_frame = frame("helper", "/repo/app.py", 50)
    events = [
        stopped("evt_01", "main", "/repo/app.py", 10, stack=[main_frame]),
        stopped("evt_02", "helper", "/repo/app.py", 50, stack=[helper_frame, main_frame], command="stepIn"),
        stopped("evt_03", "main", "/repo/app.py", 11, stack=[main_frame], command="stepOut"),
    ]

    graph = build_flow_graph(events)

    enter = edge(graph, events[0].top_frame.location, events[1].top_frame.location)
    ret = edge(graph, events[1].top_frame.location, events[2].top_frame.location)
    assert enter.kind == "function_enter"
    assert ret.kind == "function_return"


def test_annotates_thread_switch_edges():
    thread_one = stopped("evt_01", "main", "/repo/app.py", 10, thread_id=1)
    thread_two = stopped("evt_02", "worker", "/repo/app.py", 80, thread_id=2)

    graph = build_flow_graph([thread_one, thread_two])

    switch = edge(graph, thread_one.top_frame.location, thread_two.top_frame.location)
    assert switch.kind == "thread_switch"
    assert switch.thread_id == 2
