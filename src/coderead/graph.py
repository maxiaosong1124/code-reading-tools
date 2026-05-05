from __future__ import annotations

from collections.abc import Iterable

from coderead.models import FlowEdge, FlowGraph, FlowNode, SourceLocation, TraceEvent


def build_flow_graph(events: Iterable[TraceEvent], loop_threshold: int = 3) -> FlowGraph:
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
