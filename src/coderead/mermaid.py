from __future__ import annotations

from pathlib import PurePath

from coderead.models import FlowEdge, FlowGraph, FlowNode


def render_mermaid(graph: FlowGraph) -> str:
    lines = ["flowchart TD"]
    for node in graph.nodes.values():
        lines.append(f'  {node.id}["{_node_label(node)}"]')
    for edge in graph.edges.values():
        lines.append(f"  {edge.from_id} -->|{_edge_label(edge)}| {edge.to_id}")
    return "\n".join(lines) + "\n"


def _node_label(node: FlowNode) -> str:
    file_name = PurePath(node.file).name
    return f"{node.function}\\n{file_name}:{node.line}"


def _edge_label(edge: FlowEdge) -> str:
    parts = [edge.kind]
    if edge.count > 1:
        parts.append(f"x{edge.count}")
    if edge.thread_id is not None:
        parts.append(f"t{edge.thread_id}")
    return " ".join(parts)
