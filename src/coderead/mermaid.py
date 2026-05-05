from __future__ import annotations

from pathlib import PurePath

from coderead.models import FlowEdge, FlowGraph, FlowNode


def render_mermaid(graph: FlowGraph) -> str:
    lines = ["flowchart TD"]
    for node in graph.nodes.values():
        if "internal_line" in node.kinds:
            continue
        if node.parent_id is not None:
            children = [child for child in graph.nodes.values() if child.parent_id == node.id and "internal_line" in child.kinds]
            lines.append(f'  subgraph group_{node.id}["{_escape_label(_node_label(node))}"]')
            lines.append("    direction TB")
            lines.append(f'    {node.id}["{_escape_label(_node_label(node))}"]')
            if children:
                summary_id = f"summary_{node.id}"
                lines.append(f'    {summary_id}["{_escape_label(_summary_label(children))}"]')
            lines.append("  end")
        else:
            lines.append(f'  {node.id}["{_escape_label(_node_label(node))}"]')
    for edge in graph.edges.values():
        if edge.from_id.startswith("internal_") or edge.to_id.startswith("internal_"):
            continue
        lines.append(f"  {edge.from_id} -->|{_edge_label(edge)}| {edge.to_id}")
    return "\n".join(lines) + "\n"


def _node_label(node: FlowNode) -> str:
    file_name = PurePath(node.file).name
    if "internal_line" in node.kinds:
        source_text = node.metadata.get("source_text") or f"{node.function}:{node.line}"
        return f"{node.line}: {source_text}"
    if "function" in node.kinds or "trace_segment" in node.kinds:
        end_line = node.end_line or node.line
        line_text = f"{node.line}" if end_line == node.line else f"{node.line}-{end_line}"
        return f"{node.function}<br/>{file_name}:{line_text}"
    return f"{node.function}<br/>{file_name}:{node.line}"


def _summary_label(nodes: list[FlowNode]) -> str:
    parts = []
    for node in sorted(nodes, key=lambda item: item.line):
        source_text = node.metadata.get("source_text") or f"{node.function}:{node.line}"
        markers = _source_markers(source_text)
        marker_text = "" if not markers else " | " + " ".join(markers)
        parts.append(f"{node.line}: {source_text}{marker_text}")
    return "<br/>".join(parts)


def _source_markers(source_text: str) -> list[str]:
    stripped = source_text.strip()
    markers = []
    if stripped.startswith(("for ", "while ")):
        markers.append("loop")
    if stripped.startswith(("if ", "elif ", "else")):
        markers.append("branch")
    if stripped.startswith("return"):
        markers.append("return")
    return markers


def _edge_label(edge: FlowEdge) -> str:
    parts = [_display_edge_kind(edge.kind)]
    if edge.count > 1:
        parts.append(f"x{edge.count}")
    if edge.thread_id is not None and edge.thread_id != 1:
        parts.append(f"t{edge.thread_id}")
    return " ".join(parts)


def _display_edge_kind(kind: str) -> str:
    if kind == "function_enter":
        return "call"
    if kind == "resume":
        return "return"
    return kind


def _escape_label(label: str) -> str:
    placeholder = "__CODEREAD_BR__"
    escaped = (
        label.replace("<br/>", placeholder)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace(">", "&gt;")
        .replace("<", "&lt;")
    )
    return escaped.replace(placeholder, "<br/>")
