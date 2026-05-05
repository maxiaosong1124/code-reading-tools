from __future__ import annotations

from pathlib import Path

from coderead.models import FlowGraph


def render_trace_markdown(
    *,
    graph: FlowGraph,
    mermaid: str,
    scenario: str,
    session: dict | None = None,
) -> str:
    title = scenario or "未命名 Trace"
    lines = [
        f"# Trace: {title}",
        "",
        "## 场景",
        scenario or "未填写。建议补充本次 debug 的输入、配置、断点和关注问题。",
        "",
        "## 运行信息",
    ]
    session = session or {}
    if session:
        lines.extend(
            [
                f"- Session: `{session.get('session_id', '')}`",
                f"- Adapter: `{session.get('adapter', '')}`",
                f"- Created At: `{session.get('created_at', '')}`",
                f"- CWD: `{session.get('cwd', '')}`",
                f"- Command: `{_format_command(session.get('command', []))}`",
            ]
        )
    else:
        lines.append("- Session: `unknown`")

    lines.extend(
        [
            "",
            "## 流程图",
            "",
            "```mermaid",
            mermaid.rstrip(),
            "```",
            "",
            "## 关键路径",
            "",
        ]
    )
    for index, node in enumerate(graph.nodes.values(), start=1):
        line_text = _line_text(node.line, node.end_line)
        lines.append(f"{index}. `{node.function}` `{Path(node.file).name}:{line_text}` hits: {node.hit_count}")
    return "\n".join(lines) + "\n"


def _line_text(line: int, end_line: int | None) -> str:
    if end_line is None or end_line == line:
        return str(line)
    return f"{line}-{end_line}"


def _format_command(command: object) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command or "")
