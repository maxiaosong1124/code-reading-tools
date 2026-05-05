from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path, PurePath

from coderead.models import FlowEdge, FlowGraph, FlowNode, SourceLocation, TraceEvent

_ORDER_SCALE = 10


def build_flow_graph(events: Iterable[TraceEvent], loop_threshold: int = 3) -> FlowGraph:
    return build_trace_flow_graph(events, loop_threshold=loop_threshold)


def build_trace_flow_graph(events: Iterable[TraceEvent], loop_threshold: int = 3) -> FlowGraph:
    graph = FlowGraph()
    previous_event: TraceEvent | None = None
    current_node: FlowNode | None = None
    segment_index = 0
    segment_events: dict[str, list[TraceEvent]] = {}

    for event_index, event in enumerate(events):
        if _is_runtime_event(event):
            continue

        if current_node is not None and _same_function(current_node, event.top_frame.location):
            current_node.hit_count += 1
            current_node.line = min(current_node.line, event.top_frame.line)
            current_node.end_line = max(current_node.end_line or event.top_frame.line, event.top_frame.line)
            segment_events[current_node.id].append(event)
            previous_event = event
            continue

        segment_index += 1
        parent_id = current_node.id if current_node is not None and previous_event is not None and len(event.stack) > len(previous_event.stack) else None
        node = _new_trace_node(event.top_frame.location, segment_index, parent_id=parent_id)
        node.metadata["overview_order"] = event_index * _ORDER_SCALE
        if parent_id is not None and previous_event is not None:
            node.metadata["call_site_file"] = previous_event.top_frame.file
            node.metadata["call_site_line"] = previous_event.top_frame.line
        graph.nodes[node.id] = node
        segment_events[node.id] = [event]

        if current_node is not None and previous_event is not None:
            edge = FlowEdge(
                from_id=current_node.id,
                to_id=node.id,
                kind=_classify_trace_edge(previous_event, event),
                thread_id=event.thread_id,
                count=1,
                evidence_event_ids=[event.id],
            )
            graph.edges[(edge.from_id, edge.to_id)] = edge

        current_node = node
        previous_event = event

    _mark_branch_nodes(graph)
    _add_internal_line_flows(graph, segment_events, loop_threshold=loop_threshold)
    _add_step_over_call_placeholders(graph, segment_events)
    return graph


def build_line_flow_graph(events: Iterable[TraceEvent], loop_threshold: int = 3) -> FlowGraph:
    graph = FlowGraph()
    previous: TraceEvent | None = None

    for event in events:
        location = event.top_frame.location
        node = _ensure_node(graph, location)
        node.hit_count += 1

        if previous is not None:
            previous_location = previous.top_frame.location
            edge_key = (previous_location.node_id(), location.node_id())
            edge = graph.edges.get(edge_key)
            if edge is None:
                edge = FlowEdge(
                    from_id=edge_key[0],
                    to_id=edge_key[1],
                    kind=_classify_edge(previous, event),
                    thread_id=event.thread_id,
                )
                graph.edges[edge_key] = edge
            edge.count += 1
            edge.thread_id = event.thread_id
            edge.evidence_event_ids.append(event.id)

            if edge.count >= loop_threshold and edge.from_id != edge.to_id:
                edge.kind = "loop"

        previous = event

    _mark_branch_nodes(graph)
    return graph


def build_function_flow_graph(events: Iterable[TraceEvent], loop_threshold: int = 3) -> FlowGraph:
    graph = FlowGraph()
    previous: TraceEvent | None = None

    for event in events:
        if _is_runtime_event(event):
            continue
        node = _ensure_function_node(graph, event.top_frame.location)
        node.hit_count += 1
        node.line = min(node.line, event.top_frame.line)
        node.end_line = max(node.end_line or event.top_frame.line, event.top_frame.line)

        if previous is not None:
            previous_location = _function_location(previous.top_frame.location)
            location = _function_location(event.top_frame.location)
            if previous_location.node_id() == location.node_id():
                previous = event
                continue
            edge_key = (previous_location.node_id(), location.node_id())
            edge = graph.edges.get(edge_key)
            if edge is None:
                edge = FlowEdge(
                    from_id=edge_key[0],
                    to_id=edge_key[1],
                    kind=_classify_edge(previous, event),
                    thread_id=event.thread_id,
                )
                graph.edges[edge_key] = edge
            edge.count += 1
            edge.thread_id = event.thread_id
            edge.evidence_event_ids.append(event.id)

            if edge.count >= loop_threshold and edge.from_id != edge.to_id:
                edge.kind = "loop"

        previous = event

    _mark_branch_nodes(graph)
    return graph


def _ensure_node(graph: FlowGraph, location: SourceLocation) -> FlowNode:
    node_id = location.node_id()
    node = graph.nodes.get(node_id)
    if node is None:
        node = FlowNode(
            id=node_id,
            function=location.function,
            file=location.file,
            line=location.line,
            language=location.language,
        )
        graph.nodes[node_id] = node
    return node


def _ensure_function_node(graph: FlowGraph, location: SourceLocation) -> FlowNode:
    function_location = _function_location(location)
    node_id = function_location.node_id()
    node = graph.nodes.get(node_id)
    if node is None:
        node = FlowNode(
            id=node_id,
            function=function_location.function,
            file=function_location.file,
            line=location.line,
            end_line=location.line,
            language=function_location.language,
            kinds={"function"},
        )
        graph.nodes[node_id] = node
    return node


def _new_trace_node(location: SourceLocation, segment_index: int, *, parent_id: str | None = None) -> FlowNode:
    function_part = "".join(char if char.isalnum() else "_" for char in location.function).strip("_").lower()
    return FlowNode(
        id=f"trace_{segment_index:04d}_{function_part or 'unknown'}",
        function=location.function,
        file=location.file,
        line=location.line,
        end_line=location.line,
        parent_id=parent_id,
        language=location.language,
        hit_count=1,
        kinds={"trace_segment"},
    )


def _add_internal_line_flows(
    graph: FlowGraph,
    segment_events: dict[str, list[TraceEvent]],
    *,
    loop_threshold: int,
) -> None:
    for segment_id, events in segment_events.items():
        segment = graph.nodes[segment_id]
        if segment.parent_id is None:
            continue
        previous_line_node: FlowNode | None = None
        line_nodes: dict[int, FlowNode] = {}
        line_sequence: list[int] = []
        for event in events:
            line_sequence.append(event.top_frame.line)
            line_node = line_nodes.get(event.top_frame.line)
            if line_node is None:
                line_node = _new_internal_line_node(segment, event.top_frame.line)
                line_nodes[event.top_frame.line] = line_node
                graph.nodes[line_node.id] = line_node
            line_node.hit_count += 1
            if previous_line_node is not None:
                edge_key = (previous_line_node.id, line_node.id)
                edge = graph.edges.get(edge_key)
                if edge is None:
                    edge = FlowEdge(
                        from_id=previous_line_node.id,
                        to_id=line_node.id,
                        kind="step",
                        thread_id=event.thread_id,
                    )
                    graph.edges[edge_key] = edge
                edge.count += 1
                edge.evidence_event_ids.append(event.id)
                if line_node.line <= previous_line_node.line:
                    edge.kind = "loop"
            previous_line_node = line_node
        segment.metadata["internal_line_sequence"] = line_sequence


def _new_internal_line_node(segment: FlowNode, line: int) -> FlowNode:
    source_text = _read_source_line(segment.file, line)
    return FlowNode(
        id=f"internal_{segment.id}_{line}",
        function=segment.function,
        file=segment.file,
        line=line,
        end_line=line,
        parent_id=segment.id,
        language=segment.language,
        hit_count=0,
        kinds={"internal_line"},
        metadata={"source_text": source_text},
    )


def _read_source_line(path: str, line: int) -> str:
    try:
        source_path = Path(path)
        text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    source_lines = text.splitlines()
    if line < 1 or line > len(source_lines):
        return ""
    return source_lines[line - 1].strip()


def _add_step_over_call_placeholders(graph: FlowGraph, segment_events: dict[str, list[TraceEvent]]) -> None:
    inserted = 0
    for segment_id, events in segment_events.items():
        segment = graph.nodes[segment_id]
        if segment.parent_id is not None:
            continue
        base_order = int(segment.metadata.get("overview_order", 0))
        starts_after_resume = any(edge.to_id == segment.id and edge.kind == "resume" for edge in graph.edges.values())
        for event_offset, current in enumerate(events):
            call_name = _single_direct_call_name(_read_source_line(current.top_frame.file, current.top_frame.line))
            if call_name is None:
                continue
            if _has_recorded_call_at_site(graph, call_name, current.top_frame.file, current.top_frame.line):
                continue
            if any(node.function == call_name and node.parent_id == segment.id for node in graph.nodes.values()):
                continue
            event_order = base_order + event_offset * _ORDER_SCALE
            inserted += 1
            node = FlowNode(
                id=f"call_{inserted:04d}_{_safe_node_part(call_name)}",
                function=call_name,
                file=current.top_frame.file,
                line=current.top_frame.line,
                end_line=current.top_frame.line,
                parent_id=segment.id,
                language=current.top_frame.language,
                hit_count=0,
                kinds={"call_placeholder"},
                metadata={
                    "source_text": _read_source_line(current.top_frame.file, current.top_frame.line),
                    "overview_order": event_order - 1 if event_offset == 0 and starts_after_resume else event_order + 1,
                },
            )
            graph.nodes[node.id] = node
            graph.edges[(segment.id, node.id)] = FlowEdge(
                from_id=segment.id,
                to_id=node.id,
                kind="call_skipped",
                thread_id=current.thread_id,
                count=1,
                evidence_event_ids=[current.id],
            )


def _has_recorded_call_at_site(graph: FlowGraph, call_name: str, file: str, line: int) -> bool:
    return any(
        "trace_segment" in node.kinds
        and node.parent_id is not None
        and node.function == call_name
        and node.metadata.get("call_site_file") == file
        and node.metadata.get("call_site_line") == line
        for node in graph.nodes.values()
    )


def _single_direct_call_name(source_text: str) -> str | None:
    if not source_text:
        return None
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        try:
            tree = ast.parse(f"_ = {source_text}")
        except SyntaxError:
            return None
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    if len(calls) != 1:
        return None
    func = calls[0].func
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return None
    if name in {"print", "range", "len", "int", "str", "list", "dict", "set", "tuple"}:
        return None
    return name


def _safe_node_part(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower() or "call"


def _same_function(node: FlowNode, location: SourceLocation) -> bool:
    return node.function == location.function and node.file == location.file


def _classify_trace_edge(previous: TraceEvent, current: TraceEvent) -> str:
    kind = _classify_edge(previous, current)
    if kind == "function_return":
        return "resume"
    return kind


def _function_location(location: SourceLocation) -> SourceLocation:
    return SourceLocation(
        function=location.function,
        file=location.file,
        line=0,
        language=location.language,
    )


def _is_runtime_event(event: TraceEvent) -> bool:
    location = event.top_frame.location
    if not location.function.strip() or location.function in {"<module>", "__main__"}:
        return True
    path = PurePath(location.file)
    parts = set(path.parts)
    name = path.name
    if name in {"runpy.py", "debugpy", "pydevd.py"}:
        return True
    if "site-packages" in parts or "dist-packages" in parts:
        return True
    return False


def _classify_edge(previous: TraceEvent, current: TraceEvent) -> str:
    if previous.thread_id != current.thread_id:
        return "thread_switch"
    previous_depth = len(previous.stack)
    current_depth = len(current.stack)
    if current_depth > previous_depth:
        return "function_enter"
    if current_depth < previous_depth:
        return "function_return"
    return "step"


def _mark_branch_nodes(graph: FlowGraph) -> None:
    outgoing: dict[str, set[str]] = {}
    for edge in graph.edges.values():
        outgoing.setdefault(edge.from_id, set()).add(edge.to_id)

    for from_id, targets in outgoing.items():
        if len(targets) > 1:
            graph.nodes[from_id].kinds.add("branch")
