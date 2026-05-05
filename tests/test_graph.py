from coderead.graph import build_flow_graph, build_function_flow_graph, build_line_flow_graph, build_trace_flow_graph
from coderead.mermaid import render_mermaid
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

    graph = build_line_flow_graph(events)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert edge(graph, events[0].top_frame.location, events[1].top_frame.location).count == 1
    assert edge(graph, events[1].top_frame.location, events[2].top_frame.location).count == 1


def test_marks_branch_when_same_node_has_multiple_targets():
    first = stopped("evt_01", "main", "/repo/app.py", 10)
    left = stopped("evt_02", "left", "/repo/app.py", 20)
    again = stopped("evt_03", "main", "/repo/app.py", 10)
    right = stopped("evt_04", "right", "/repo/app.py", 30)

    graph = build_line_flow_graph([first, left, again, right])

    branch_node = graph.nodes[first.top_frame.location.node_id()]
    assert branch_node.kinds == {"branch", "function_location"}
    assert len([edge for edge in graph.edges.values() if edge.from_id == branch_node.id]) == 2


def test_counts_repeated_edges_and_marks_loop_after_threshold():
    loop_a = stopped("evt_01", "loop", "/repo/app.py", 40)
    loop_b = stopped("evt_02", "loop", "/repo/app.py", 41)
    events = [loop_a, loop_b, loop_a, loop_b, loop_a, loop_b]

    graph = build_line_flow_graph(events, loop_threshold=3)

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

    graph = build_line_flow_graph(events)

    enter = edge(graph, events[0].top_frame.location, events[1].top_frame.location)
    ret = edge(graph, events[1].top_frame.location, events[2].top_frame.location)
    assert enter.kind == "function_enter"
    assert ret.kind == "function_return"


def test_annotates_thread_switch_edges():
    thread_one = stopped("evt_01", "main", "/repo/app.py", 10, thread_id=1)
    thread_two = stopped("evt_02", "worker", "/repo/app.py", 80, thread_id=2)

    graph = build_line_flow_graph([thread_one, thread_two])

    switch = edge(graph, thread_one.top_frame.location, thread_two.top_frame.location)
    assert switch.kind == "thread_switch"
    assert switch.thread_id == 2


def test_default_graph_groups_events_by_function_and_file():
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26),
        stopped("evt_02", "main", "/repo/app.py", 27),
        stopped(
            "evt_03",
            "normalize_numbers",
            "/repo/app.py",
            5,
            stack=[frame("normalize_numbers", "/repo/app.py", 5), frame("main", "/repo/app.py", 27)],
            command="stepIn",
        ),
        stopped(
            "evt_04",
            "normalize_numbers",
            "/repo/app.py",
            6,
            stack=[frame("normalize_numbers", "/repo/app.py", 6), frame("main", "/repo/app.py", 27)],
        ),
        stopped("evt_05", "main", "/repo/app.py", 28, command="stepOut"),
    ]

    graph = build_function_flow_graph(events)

    assert len(graph.nodes) == 2
    node_labels = {(node.function, node.file, node.line, node.end_line, node.hit_count) for node in graph.nodes.values()}
    assert ("main", "/repo/app.py", 26, 28, 3) in node_labels
    assert ("normalize_numbers", "/repo/app.py", 5, 6, 2) in node_labels
    assert len(graph.edges) == 2


def test_default_graph_filters_python_runtime_frames():
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26),
        stopped("evt_02", "_run_code", "/usr/lib/python3.12/runpy.py", 89),
        stopped("evt_03", "_run_module_as_main", "/usr/lib/python3.12/runpy.py", 198),
    ]

    graph = build_function_flow_graph(events)

    assert len(graph.nodes) == 1
    assert next(iter(graph.nodes.values())).function == "main"
    assert graph.edges == {}


def test_line_graph_keeps_line_level_nodes():
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26),
        stopped("evt_02", "main", "/repo/app.py", 27),
    ]

    graph = build_line_flow_graph(events)

    assert len(graph.nodes) == 2
    assert {node.line for node in graph.nodes.values()} == {26, 27}


def test_mermaid_function_node_label_shows_line_range_without_hits():
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26),
        stopped("evt_02", "main", "/repo/app.py", 28),
    ]

    mermaid = render_mermaid(build_function_flow_graph(events))

    assert "main<br/>app.py:26-28" in mermaid
    assert "\\n" not in mermaid
    assert "hits:" not in mermaid


def test_trace_graph_keeps_temporal_segments_without_return_back_edges():
    main_26 = frame("main", "/repo/app.py", 26)
    main_28 = frame("main", "/repo/app.py", 28)
    normalize_5 = frame("normalize_numbers", "/repo/app.py", 5)
    normalize_11 = frame("normalize_numbers", "/repo/app.py", 11)
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26, stack=[main_26]),
        stopped("evt_02", "normalize_numbers", "/repo/app.py", 5, stack=[normalize_5, main_26], command="stepIn"),
        stopped("evt_03", "normalize_numbers", "/repo/app.py", 11, stack=[normalize_11, main_26]),
        stopped("evt_04", "main", "/repo/app.py", 28, stack=[main_28], command="stepOut"),
    ]

    graph = build_trace_flow_graph(events)

    nodes = [node for node in graph.nodes.values() if "trace_segment" in node.kinds]
    assert [(node.function, node.line, node.end_line, node.hit_count) for node in nodes] == [
        ("main", 26, 26, 1),
        ("normalize_numbers", 5, 11, 2),
        ("main", 28, 28, 1),
    ]
    trace_node_ids = {node.id for node in nodes}
    edges = [edge for edge in graph.edges.values() if edge.from_id in trace_node_ids and edge.to_id in trace_node_ids]
    assert [(edge.from_id, edge.to_id, edge.kind) for edge in edges] == [
        (nodes[0].id, nodes[1].id, "function_enter"),
        (nodes[1].id, nodes[2].id, "resume"),
    ]


def test_default_graph_uses_trace_view():
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26),
        stopped("evt_02", "main", "/repo/app.py", 27),
    ]

    graph = build_flow_graph(events)

    node = next(iter(graph.nodes.values()))
    assert node.id.startswith("trace_")
    assert node.line == 26
    assert node.end_line == 27


def test_trace_graph_filters_module_wrapper_without_function_name():
    events = [
        stopped("evt_01", "", "/repo/app.py", 33),
        stopped("evt_02", "main", "/repo/app.py", 25),
        stopped("evt_03", "main", "/repo/app.py", 26),
        stopped("evt_04", "", "/repo/app.py", 33),
    ]

    graph = build_trace_flow_graph(events)

    assert [(node.function, node.line, node.end_line) for node in graph.nodes.values()] == [
        ("main", 25, 26),
    ]


def test_trace_mermaid_uses_reading_friendly_edge_labels():
    main_26 = frame("main", "/repo/app.py", 26)
    normalize_5 = frame("normalize_numbers", "/repo/app.py", 5)
    main_28 = frame("main", "/repo/app.py", 28)
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26, stack=[main_26]),
        stopped("evt_02", "normalize_numbers", "/repo/app.py", 5, stack=[normalize_5, main_26], command="stepIn"),
        stopped("evt_03", "main", "/repo/app.py", 28, stack=[main_28], command="stepOut"),
    ]

    mermaid = render_mermaid(build_trace_flow_graph(events))

    assert "|call|" in mermaid
    assert "|return|" in mermaid
    assert "t1" not in mermaid
    assert "function_enter" not in mermaid
    assert "resume" not in mermaid


def test_trace_graph_assigns_called_segments_to_parent_segment():
    main_26 = frame("main", "/repo/app.py", 26)
    normalize_5 = frame("normalize_numbers", "/repo/app.py", 5)
    summarize_15 = frame("summarize", "/repo/app.py", 15)
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26, stack=[main_26]),
        stopped("evt_02", "normalize_numbers", "/repo/app.py", 5, stack=[normalize_5, main_26], command="stepIn"),
        stopped("evt_03", "main", "/repo/app.py", 27, stack=[main_26], command="stepOut"),
        stopped("evt_04", "summarize", "/repo/app.py", 15, stack=[summarize_15, main_26], command="stepIn"),
    ]

    graph = build_trace_flow_graph(events)
    nodes = list(graph.nodes.values())

    assert nodes[0].function == "main"
    assert nodes[1].function == "normalize_numbers"
    assert nodes[1].parent_id == nodes[0].id
    assert nodes[2].function == "main"
    assert nodes[2].parent_id is None
    assert nodes[3].function == "summarize"
    assert nodes[3].parent_id == nodes[2].id


def test_mermaid_renders_trace_subgraphs_for_called_functions():
    main_26 = frame("main", "/repo/app.py", 26)
    normalize_5 = frame("normalize_numbers", "/repo/app.py", 5)
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26, stack=[main_26]),
        stopped("evt_02", "normalize_numbers", "/repo/app.py", 5, stack=[normalize_5, main_26], command="stepIn"),
    ]

    mermaid = render_mermaid(build_trace_flow_graph(events))

    assert "subgraph group_trace_0002_normalize_numbers" in mermaid
    assert "trace_0002_normalize_numbers" in mermaid
    assert "end" in mermaid


def test_mermaid_keeps_mainline_nodes_outside_called_function_subgraphs():
    main_26 = frame("main", "/repo/app.py", 26)
    main_28 = frame("main", "/repo/app.py", 28)
    normalize_5 = frame("normalize_numbers", "/repo/app.py", 5)
    events = [
        stopped("evt_01", "main", "/repo/app.py", 26, stack=[main_26]),
        stopped("evt_02", "normalize_numbers", "/repo/app.py", 5, stack=[normalize_5, main_26], command="stepIn"),
        stopped("evt_03", "main", "/repo/app.py", 28, stack=[main_28], command="stepOut"),
    ]

    mermaid = render_mermaid(build_trace_flow_graph(events))

    main_node = 'trace_0001_main["main<br/>app.py:26"]'
    child_group = 'subgraph group_trace_0002_normalize_numbers["normalize_numbers<br/>app.py:5"]'
    assert main_node in mermaid
    assert child_group in mermaid
    assert mermaid.index(main_node) < mermaid.index(child_group)
    assert "subgraph group_trace_0001_main" not in mermaid


def test_trace_graph_adds_internal_line_nodes_for_called_segments(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "\n".join(
            [
                "def summarize(values):",
                "    total = 0",
                "    maximum = values[0]",
                "    for value in values:",
                "        total += value",
                "        if value > maximum:",
                "            maximum = value",
                "    return {'total': total, 'maximum': maximum}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    main_1 = frame("main", str(source), 1)
    summarize_1 = frame("summarize", str(source), 1)
    events = [
        stopped("evt_01", "main", str(source), 1, stack=[main_1]),
        stopped("evt_02", "summarize", str(source), 4, stack=[summarize_1, main_1], command="stepIn"),
        stopped("evt_03", "summarize", str(source), 5, stack=[frame("summarize", str(source), 5), main_1]),
        stopped("evt_04", "summarize", str(source), 6, stack=[frame("summarize", str(source), 6), main_1]),
        stopped("evt_05", "summarize", str(source), 7, stack=[frame("summarize", str(source), 7), main_1]),
        stopped("evt_06", "summarize", str(source), 4, stack=[frame("summarize", str(source), 4), main_1]),
    ]

    graph = build_trace_flow_graph(events)
    summarize_segment = next(node for node in graph.nodes.values() if node.function == "summarize" and "trace_segment" in node.kinds)
    internal_nodes = [node for node in graph.nodes.values() if node.parent_id == summarize_segment.id and "internal_line" in node.kinds]

    assert [(node.line, node.metadata["source_text"]) for node in internal_nodes] == [
        (4, "for value in values:"),
        (5, "total += value"),
        (6, "if value > maximum:"),
        (7, "maximum = value"),
    ]
    assert summarize_segment.metadata["internal_line_sequence"] == [4, 5, 6, 7, 4]
    loop_edge = next(edge for edge in graph.edges.values() if edge.kind == "loop")
    assert loop_edge.count == 1


def test_mermaid_renders_internal_summary_inside_called_function_subgraph(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def summarize(values):\n"
        "    for value in values:\n"
        "        total += value\n",
        encoding="utf-8",
    )
    main_1 = frame("main", str(source), 1)
    summarize_2 = frame("summarize", str(source), 2)
    events = [
        stopped("evt_01", "main", str(source), 1, stack=[main_1]),
        stopped("evt_02", "summarize", str(source), 2, stack=[summarize_2, main_1], command="stepIn"),
        stopped("evt_03", "summarize", str(source), 3, stack=[frame("summarize", str(source), 3), main_1]),
    ]

    mermaid = render_mermaid(build_trace_flow_graph(events))

    assert "2: for value in values: | loop" in mermaid
    assert "3: total += value" in mermaid
    assert "<br/>3: total += value" in mermaid
    assert "hits:" not in mermaid
    assert "internal_trace_0002_summarize_2" not in mermaid
    assert "internal_trace_0002_summarize_2 -->" not in mermaid


def test_mermaid_internal_summary_marks_branch_and_return(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def summarize(values):\n"
        "    if value > maximum:\n"
        "        maximum = value\n"
        "    return {\"total\": total}\n",
        encoding="utf-8",
    )
    main_1 = frame("main", str(source), 1)
    summarize_2 = frame("summarize", str(source), 2)
    events = [
        stopped("evt_01", "main", str(source), 1, stack=[main_1]),
        stopped("evt_02", "summarize", str(source), 2, stack=[summarize_2, main_1], command="stepIn"),
        stopped("evt_03", "summarize", str(source), 3, stack=[frame("summarize", str(source), 3), main_1]),
        stopped("evt_04", "summarize", str(source), 4, stack=[frame("summarize", str(source), 4), main_1]),
    ]

    mermaid = render_mermaid(build_trace_flow_graph(events))

    assert "2: if value &gt; maximum: | branch" in mermaid
    assert "4: return {&quot;total&quot;: total} | return" in mermaid
    assert "hits:" not in mermaid


def test_mermaid_escapes_source_text_that_contains_quotes_and_braces(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def summarize(values):\n"
        "    return {\"total\": total, \"maximum\": maximum}\n",
        encoding="utf-8",
    )
    main_1 = frame("main", str(source), 1)
    summarize_2 = frame("summarize", str(source), 2)
    events = [
        stopped("evt_01", "main", str(source), 1, stack=[main_1]),
        stopped("evt_02", "summarize", str(source), 2, stack=[summarize_2, main_1], command="stepIn"),
    ]

    mermaid = render_mermaid(build_trace_flow_graph(events))

    assert "return {&quot;total&quot;: total, &quot;maximum&quot;: maximum}" in mermaid
    assert 'return {"total": total, "maximum": maximum}' not in mermaid


def test_trace_graph_adds_call_placeholder_for_step_over_function_call(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    normalized = normalize_numbers(raw_values)\n"
        "    summary = summarize(normalized)\n"
        "    print(summary)\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    main_3 = frame("main", str(source), 3)
    main_4 = frame("main", str(source), 4)
    events = [
        stopped("evt_01", "main", str(source), 2, stack=[main_2]),
        stopped("evt_02", "main", str(source), 3, stack=[main_3], command="next"),
        stopped("evt_03", "main", str(source), 4, stack=[main_4], command="next"),
    ]

    graph = build_trace_flow_graph(events)
    call_nodes = [node for node in graph.nodes.values() if "call_placeholder" in node.kinds]

    assert [(node.function, node.line, node.parent_id) for node in call_nodes] == [
        ("normalize_numbers", 2, "trace_0001_main"),
        ("summarize", 3, "trace_0001_main"),
    ]
    assert all(any(edge.kind == "call_skipped" and edge.to_id == node.id for edge in graph.edges.values()) for node in call_nodes)


def test_trace_graph_orders_step_over_placeholder_before_resumed_segment(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    normalized = normalize_numbers(values)\n"
        "    summary = summarize(normalized)\n"
        "    print(summary)\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    normalize_1 = frame("normalize_numbers", str(source), 1)
    events = [
        stopped("evt_01", "main", str(source), 2, stack=[main_2]),
        stopped("evt_02", "normalize_numbers", str(source), 1, stack=[normalize_1, main_2], command="stepIn"),
        stopped("evt_03", "main", str(source), 3, stack=[frame("main", str(source), 3)], command="stepOut"),
        stopped("evt_04", "main", str(source), 4, stack=[frame("main", str(source), 4)]),
    ]

    graph = build_trace_flow_graph(events)
    overview_nodes = sorted(
        [node for node in graph.nodes.values() if "trace_segment" in node.kinds or "call_placeholder" in node.kinds],
        key=lambda node: node.metadata["overview_order"],
    )

    assert [(node.function, node.line, node.end_line) for node in overview_nodes] == [
        ("main", 2, 2),
        ("normalize_numbers", 1, 1),
        ("summarize", 3, 3),
        ("main", 3, 4),
    ]
