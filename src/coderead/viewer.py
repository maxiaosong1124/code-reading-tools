from __future__ import annotations

import html
import ast
import json
from pathlib import Path
from pathlib import PurePath
from typing import Any

from coderead.models import FlowGraph, FlowNode


def render_trace_html(*, graph: FlowGraph, scenario: str, session: dict | None = None) -> str:
    payload = _view_payload(graph=graph, scenario=scenario, session=session)
    session = payload["session"]
    subflows = payload["subflows"]
    payload_json = json.dumps(payload, ensure_ascii=False)
    first_subflow_id = subflows[0]["id"] if subflows else ""
    initial_subflow = subflows[0] if subflows else None
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trace Viewer - {_escape_text(payload["scenario"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --line: #cbd5e1;
      --accent: #2563eb;
      --accent-soft: #eff6ff;
      --border: #d9dee8;
      --module-soft: #ecfdf5;
      --module-border: #86efac;
      --repeat-soft: #fef3c7;
      --repeat-border: #f59e0b;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding: 20px 28px 14px; border-bottom: 1px solid var(--border); background: var(--panel); }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px 18px; color: var(--muted); font-size: 12px; }}
    main {{ display: grid; grid-template-columns: minmax(320px, 42%) minmax(420px, 1fr); gap: 18px; padding: 18px; }}
    section {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; min-height: 520px; overflow: auto; }}
    .section-title {{ position: sticky; top: 0; background: var(--panel); z-index: 2; padding: 14px 16px; border-bottom: 1px solid var(--border); font-weight: 650; }}
    .timeline {{ padding: 18px; display: grid; gap: 0; justify-items: stretch; }}
    .function-container {{ border: 1px solid var(--border); background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06); }}
    .module-lane {{ border-left: 3px solid var(--module-border); background: #fbfefc; padding: 12px; margin-bottom: 14px; border-radius: 6px; }}
    .module-lane-header {{ display: flex; align-items: center; margin-bottom: 10px; }}
    .function-header {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; padding: 2px 2px 10px; border-bottom: 1px solid #eef2f7; }}
    .function-header strong {{ font-size: 15px; }}
    .function-title {{ display: inline-flex; align-items: center; gap: 8px; min-width: 0; }}
    .function-steps {{ display: grid; gap: 0; justify-items: center; padding-top: 12px; }}
    .node {{ border: 1px solid var(--border); background: #fff; border-radius: 6px; padding: 10px 12px; min-width: 220px; max-width: 420px; text-align: center; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06); }}
    .node.trace-line {{ background: #f8fafc; box-shadow: none; }}
    .node.clickable {{ cursor: pointer; border-color: #93c5fd; background: var(--accent-soft); }}
    .node.clickable:hover {{ border-color: var(--accent); }}
    .node.skipped-call {{ border-style: dashed; background: #fff7ed; border-color: #fdba74; }}
    .edge {{ display: grid; place-items: center; min-height: 40px; color: var(--muted); }}
    .edge::before {{ content: ""; width: 1px; height: 18px; background: var(--line); display: block; }}
    .edge-label {{ font-size: 12px; background: #f3f4f6; border: 1px solid var(--border); border-radius: 4px; padding: 1px 6px; margin: 2px 0; }}
    .subflow {{ padding: 18px; }}
    .subflow h2 {{ margin: 0 0 4px; font-size: 18px; }}
    .subflow-path {{ color: var(--muted); font-size: 12px; margin-bottom: 18px; }}
    .subflow-chart {{ display: grid; gap: 0; justify-items: stretch; max-width: 820px; }}
    .flow-node {{ --depth: 0; margin-left: calc(var(--depth) * 34px); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; background: #fff; min-width: min(520px, 100%); max-width: 760px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05); }}
    .flow-node.loop-node {{ border-color: #7c3aed; background: #f5f3ff; }}
    .flow-node.branch-node {{ width: min(440px, 90%); min-width: 240px; transform: skew(-8deg); border-color: #d97706; background: #fffbeb; }}
    .flow-node.branch-node .flow-node-inner {{ transform: skew(8deg); justify-content: center; text-align: center; }}
    .flow-node.return-node {{ width: min(420px, 90%); min-width: 220px; border-radius: 999px; border-color: #16a34a; background: #f0fdf4; }}
    .flow-node-inner {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
    .flow-connector {{ display: grid; place-items: center; height: 34px; color: var(--muted); }}
    .flow-connector::before {{ content: ""; width: 1px; height: 20px; background: var(--line); display: block; }}
    .flow-depth-connector {{ --depth: 0; margin-left: calc(var(--depth) * 34px); }}
    code {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 12px; }}
    .badge {{ color: #1d4ed8; background: var(--accent-soft); border: 1px solid #bfdbfe; border-radius: 999px; padding: 1px 8px; font-size: 12px; white-space: nowrap; }}
    .module-badge {{ color: #166534; background: var(--module-soft); border: 1px solid var(--module-border); border-radius: 999px; padding: 1px 8px; font-size: 12px; white-space: nowrap; }}
    .repeat-badge {{ color: #92400e; background: var(--repeat-soft); border: 1px solid var(--repeat-border); border-radius: 999px; padding: 1px 8px; font-size: 12px; white-space: nowrap; }}
    .empty {{ color: var(--muted); padding: 18px; }}
  </style>
</head>
<body>
  <header>
    <h1>Trace Viewer: {_escape_text(payload["scenario"])}</h1>
    <div class="meta">
      <span>Session: <code>{_escape_text(str(session.get("session_id", "")))}</code></span>
      <span>CWD: <code>{_escape_text(str(session.get("cwd", "")))}</code></span>
      <span>Command: <code>{_escape_text(_format_command(session.get("command", [])))}</code></span>
      {_render_static_session_meta(session)}
    </div>
  </header>
  <main>
    <section>
      <div class="section-title">Overview 主流程</div>
      <div id="overview" class="timeline">{_render_static_overview(payload["overview"], {item["id"] for item in subflows})}</div>
    </section>
    <section>
      <div class="section-title">Subflow 子流程</div>
      <div id="subflow" class="subflow">{_render_static_subflow(initial_subflow)}</div>
    </section>
  </main>
  <script id="trace-data" type="application/json">{_escape_script_json(payload_json)}</script>
  <script>
    const traceData = JSON.parse(document.getElementById("trace-data").textContent);
    const subflowById = new Map(traceData.subflows.map((item) => [item.id, item]));

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[char]));
    }}

    function renderOverview() {{
      const root = document.getElementById("overview");
      root.innerHTML = traceData.overview.map((item) => item.kind === "module_lane" ? renderModuleLane(item) : renderFunctionContainer(item)).join("");
      root.querySelectorAll("[data-node-id]").forEach((element) => {{
        const id = element.dataset.nodeId;
        if (subflowById.has(id)) element.addEventListener("click", () => selectSubflow(id));
      }});
    }}

    function renderFunctionContainer(container) {{
      const steps = container.steps.map((node, index) => `${{index === 0 ? "" : `<div class="edge"><span class="edge-label">${{edgeLabel(container.steps[index - 1], node)}}</span></div>`}}${{renderNode(node)}}`).join("");
      const repeatBadge = container.repeat_count > 1 ? `<span class="repeat-badge">x${{escapeHtml(container.repeat_count)}}</span>` : "";
      const headerTitle = repeatBadge ? `<span class="function-title"><strong>${{escapeHtml(container.function)}}</strong>${{repeatBadge}}</span>` : `<strong>${{escapeHtml(container.function)}}</strong>`;
      return `<div class="function-container">
        <div class="function-header">${{headerTitle}}<code>${{escapeHtml(container.file_name)}}:${{escapeHtml(container.line_text)}}</code></div>
        <div class="function-steps">${{steps}}</div>
      </div>`;
    }}

    function renderModuleLane(lane) {{
      const items = lane.items.map((item) => renderFunctionContainer(item)).join("");
      return `<div class="module-lane"><div class="module-lane-header"><span class="module-badge">${{escapeHtml(lane.module_label)}}</span></div>${{items}}</div>`;
    }}

    function renderNode(node) {{
      const classes = `node ${{subflowById.has(node.id) ? "clickable" : ""}} ${{node.kind === "call_placeholder" ? "skipped-call" : ""}} ${{node.kind === "trace_line" ? "trace-line" : ""}}`;
      const title = node.kind === "trace_line" ? (node.display_text || node.source_text || node.function) : node.function;
      const moduleBadge = node.module_label ? `<span class="module-badge">${{escapeHtml(node.module_label)}}</span>` : "";
      return `<button type="button" class="${{classes}}" data-node-id="${{escapeHtml(node.id)}}"><strong>${{escapeHtml(title)}}</strong><br><code>${{escapeHtml(node.file_name)}}:${{escapeHtml(node.line_text)}}</code>${{moduleBadge}}</button>`;
    }}

    function selectSubflow(id) {{
      const root = document.getElementById("subflow");
      const subflow = subflowById.get(id);
      if (!subflow) {{
        root.innerHTML = '<div class="empty">这个节点没有子流程。</div>';
        return;
      }}
      const subflowSteps = subflow.steps || subflow.lines || [];
      const lines = subflowSteps.map((line, index) => {{
        const markers = line.markers.map((marker) => `<span class="badge">${{escapeHtml(marker)}}</span>`).join(" ");
        const kindClass = flowNodeClass(line.markers);
        const connector = index === 0 ? "" : '<div class="flow-connector"></div>';
        return `${{connector}}<div class="flow-node ${{kindClass}}" style="--depth: ${{line.depth || 0}}">
          <div class="flow-node-inner"><code>${{escapeHtml(line.line_text || line.line)}}: ${{escapeHtml(line.source_text)}}</code>${{markers}}</div>
        </div>`;
      }}).join("");
      root.innerHTML = `<h2>${{escapeHtml(subflow.function)}}</h2>
        <div class="subflow-path">${{escapeHtml(subflow.file_name)}}:${{escapeHtml(subflow.line_text)}}</div>
        <div class="subflow-chart">${{lines || '<div class="empty">没有记录到内部行。</div>'}}</div>`;
    }}

    renderOverview();
    selectSubflow("{_escape_js_string(first_subflow_id)}");

    function edgeLabel(previous, current) {{
      if (current.kind === "call_placeholder" || current.parent_id) return "call";
      if (previous && previous.kind === "call_placeholder") return "return";
      if (previous && previous.parent_id && !current.parent_id) return "return";
      if (previous && previous.function === current.function) return "step";
      return "return";
    }}

    function flowNodeClass(markers) {{
      if (markers.includes("return") || markers.includes("raise")) return "return-node";
      if (markers.includes("branch")) return "branch-node";
      if (markers.includes("loop")) return "loop-node";
      return "statement-node";
    }}
  </script>
</body>
</html>
"""


def _view_payload(*, graph: FlowGraph, scenario: str, session: dict | None = None) -> dict[str, Any]:
    session = session or {}
    overview_nodes = sorted(
        [
            node
            for node in graph.nodes.values()
            if "trace_segment" in node.kinds or "call_placeholder" in node.kinds
        ],
        key=_overview_sort_key,
    )
    overview = _containerize_overview(_overview_payload(graph, overview_nodes))
    if session.get("profile") == "vllm":
        overview = _containerize_vllm_modules(overview)
    subflows = [
        _subflow_payload(graph, node)
        for node in overview_nodes
        if node.parent_id is not None and "trace_segment" in node.kinds
    ]
    payload = {
        "scenario": scenario or "未命名 Trace",
        "session": session,
        "overview": overview,
        "subflows": subflows,
    }
    return payload


def _overview_payload(graph: FlowGraph, overview_nodes: list[FlowNode]) -> list[dict[str, Any]]:
    handled_nodes: set[str] = set()
    rendered_call_sites: set[tuple[str, int]] = set()
    payload: list[dict[str, Any]] = []
    for node in overview_nodes:
        if node.id in handled_nodes:
            continue
        if "call_placeholder" in node.kinds and _is_embedded_placeholder(graph, node):
            continue
        if "trace_segment" in node.kinds and node.parent_id is None:
            payload.extend(_split_root_segment_payload(graph, node, handled_nodes, rendered_call_sites))
            continue
        payload.append(_node_payload(node))
    return payload


def _containerize_overview(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    container_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for node in nodes:
        if node.get("kind") in {"trace_segment", "trace_line"} and not node.get("parent_id"):
            key = (node["function"], node["file_name"])
            container = container_by_key.get(key)
            if container is None:
                container = {
                    "id": f"container_{node['id']}",
                    "function": node["function"],
                    "file_name": node["file_name"],
                    "line_text": node["line_text"],
                    "kind": "function_container",
                    "steps": [],
                }
                container_by_key[key] = container
                containers.append(container)
            else:
                container["line_text"] = _merge_line_text(str(container["line_text"]), str(node["line_text"]))
            container["steps"].append({**node, "kind": "trace_line"})
            continue
        if containers:
            containers[-1]["steps"].append(node)
            continue
        containers.append(
            {
                "id": f"container_{node['id']}",
                "function": node["function"],
                "file_name": node["file_name"],
                "line_text": node["line_text"],
                "kind": "function_container",
                "steps": [node],
            }
        )
    return containers


def _containerize_vllm_modules(containers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lanes: list[dict[str, Any]] = []
    current_lane: dict[str, Any] | None = None
    for container in containers:
        module_label = _container_module_label(container)
        if not module_label:
            lanes.append(container)
            current_lane = None
            continue
        if current_lane is None or current_lane["module_label"] != module_label:
            current_lane = {
                "id": f"lane_{len(lanes) + 1:04d}_{module_label}",
                "kind": "module_lane",
                "module_label": module_label,
                "items": [],
            }
            lanes.append(current_lane)
        _append_folded_lane_item(current_lane["items"], container)
    return lanes


def _append_folded_lane_item(items: list[dict[str, Any]], container: dict[str, Any]) -> None:
    if not items:
        items.append(container)
        return
    previous = items[-1]
    if _same_foldable_container(previous, container):
        previous["repeat_count"] = int(previous.get("repeat_count", 1)) + int(container.get("repeat_count", 1))
        return
    items.append(container)


def _same_foldable_container(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _container_repeat_key(left) == _container_repeat_key(right)


def _container_repeat_key(container: dict[str, Any]) -> tuple[object, ...]:
    steps = container.get("steps", [])
    step_key = tuple(
        (
            step.get("kind"),
            step.get("function"),
            step.get("file_name"),
            step.get("line_text"),
            step.get("source_text", ""),
            step.get("module_label", ""),
        )
        for step in steps
    )
    return (
        container.get("kind"),
        container.get("function"),
        container.get("file_name"),
        container.get("line_text"),
        _container_module_label(container),
        step_key,
    )


def _container_module_label(container: dict[str, Any]) -> str:
    for step in container.get("steps", []):
        module_label = step.get("module_label")
        if module_label:
            return str(module_label)
    return str(container.get("module_label", ""))


def _merge_line_text(left: str, right: str) -> str:
    left_start, left_end = _line_bounds(left)
    right_start, right_end = _line_bounds(right)
    start = min(left_start, right_start)
    end = max(left_end, right_end)
    return str(start) if start == end else f"{start}-{end}"


def _line_bounds(value: str) -> tuple[int, int]:
    if "-" in value:
        start, end = value.split("-", 1)
        return int(start), int(end)
    line = int(value)
    return line, line


def _is_embedded_placeholder(graph: FlowGraph, node: FlowNode) -> bool:
    if node.parent_id is None:
        return False
    parent = graph.nodes.get(node.parent_id)
    return parent is not None and "trace_segment" in parent.kinds and parent.parent_id is None


def _split_root_segment_payload(
    graph: FlowGraph,
    node: FlowNode,
    handled_nodes: set[str],
    rendered_call_sites: set[tuple[str, int]],
) -> list[dict[str, Any]]:
    visible_ranges = _visible_statement_ranges(node.file, node.function, node.line, node.end_line or node.line)
    breaks = _call_breaks_for_segment(graph, node)
    if not breaks:
        return [_virtual_node_payload(node, start, end) for start, end in visible_ranges] or [_node_payload(node)]

    chunks: list[dict[str, Any]] = []
    cursor = node.line
    end_line = node.end_line or node.line
    for line, call_node in breaks:
        if line < cursor or line > end_line:
            continue
        if cursor <= line - 1:
            _append_visible_line_range(chunks, node, cursor, line - 1, rendered_call_sites, visible_ranges)
        call_site = (node.file, line)
        if call_site not in rendered_call_sites:
            start, end = _statement_range_for_line(visible_ranges, line)
            chunks.append(_virtual_node_payload(node, start, end))
            rendered_call_sites.add(call_site)
        if "call_placeholder" in call_node.kinds:
            chunks.append(_node_payload(call_node))
            handled_nodes.add(call_node.id)
            rendered_call_sites.add(call_site)
        _, call_end = _statement_range_for_line(visible_ranges, line)
        cursor = call_end + 1
    if cursor <= end_line:
        _append_visible_line_range(chunks, node, cursor, end_line, rendered_call_sites, visible_ranges)
    return chunks


def _append_visible_line_range(
    chunks: list[dict[str, Any]],
    node: FlowNode,
    start_line: int,
    end_line: int,
    rendered_call_sites: set[tuple[str, int]],
    visible_ranges: list[tuple[int, int]] | None = None,
) -> None:
    ranges = visible_ranges or [(start_line, end_line)]
    for range_start, range_end in ranges:
        clipped_start = max(start_line, range_start)
        clipped_end = min(end_line, range_end)
        if clipped_start > clipped_end:
            continue
        if any((node.file, line) in rendered_call_sites for line in range(clipped_start, clipped_end + 1)):
            continue
        chunks.append(_virtual_node_payload(node, clipped_start, clipped_end))


def _visible_statement_ranges(path: str, function_name: str, start_line: int, end_line: int) -> list[tuple[int, int]]:
    statement_ranges = _python_statement_ranges(path, function_name)
    if not statement_ranges:
        return _fallback_visible_ranges(path, start_line, end_line)
    ranges = []
    seen = set()
    for statement_start, statement_end in statement_ranges:
        if statement_end < start_line or statement_start > end_line:
            continue
        clipped = (max(start_line, statement_start), min(end_line, statement_end))
        if clipped not in seen:
            ranges.append(clipped)
            seen.add(clipped)
    return ranges


def _python_statement_ranges(path: str, function_name: str) -> list[tuple[int, int]]:
    statements = _python_function_statements(path, function_name)
    return sorted({(int(statement["line"]), int(statement["end_line"])) for statement in statements})


def _fallback_visible_ranges(path: str, start_line: int, end_line: int) -> list[tuple[int, int]]:
    try:
        source_lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return [(start_line, end_line)]
    ranges = []
    for line_number in range(start_line, end_line + 1):
        if 1 <= line_number <= len(source_lines):
            stripped = source_lines[line_number - 1].strip()
            if stripped and not stripped.startswith("#"):
                ranges.append((line_number, line_number))
    return ranges


def _statement_range_for_line(ranges: list[tuple[int, int]], line: int) -> tuple[int, int]:
    for start, end in ranges:
        if start <= line <= end:
            return start, end
    return line, line


def _call_breaks_for_segment(graph: FlowGraph, node: FlowNode) -> list[tuple[int, FlowNode]]:
    breaks = []
    for candidate in graph.nodes.values():
        if "trace_segment" in candidate.kinds and candidate.parent_id == node.id:
            call_site_line = candidate.metadata.get("call_site_line")
            call_site_file = candidate.metadata.get("call_site_file")
            if call_site_file == node.file and isinstance(call_site_line, int):
                breaks.append((call_site_line, candidate))
        if "call_placeholder" in candidate.kinds and candidate.parent_id == node.id:
            breaks.append((candidate.line, candidate))
    return sorted(breaks, key=lambda item: (item[0], _overview_sort_key(item[1])))


def _subflow_payload(graph: FlowGraph, node: FlowNode) -> dict[str, Any]:
    children = [child for child in graph.nodes.values() if child.parent_id == node.id and "internal_line" in child.kinds]
    statements = _python_function_statements(node.file, node.function)
    structure = {int(statement["line"]): statement for statement in statements}
    statement_by_line = _statement_lookup_by_line(statements)
    child_by_line = {child.line: child for child in children}
    sequence = node.metadata.get("internal_line_sequence")
    ordered_children = (
        [child_by_line[line] for line in sequence if isinstance(line, int) and line in child_by_line]
        if isinstance(sequence, list)
        else sorted(children, key=lambda item: item.line)
    )
    steps = []
    previous_key: tuple[int, int] | None = None
    for child in ordered_children:
        statement = statement_by_line.get(child.line)
        if statement is None:
            statement = {
                "line": child.line,
                "end_line": child.line,
                "depth": structure.get(child.line, {}).get("depth", 0),
                "source_text": child.metadata.get("source_text", ""),
                "markers": structure.get(child.line, {}).get(
                    "markers",
                    _source_markers(child.metadata.get("source_text", "")),
                ),
            }
        line = int(statement["line"])
        end_line = int(statement["end_line"])
        key = (line, end_line)
        if key == previous_key:
            continue
        previous_key = key
        steps.append(
            {
                "line": line,
                "depth": int(statement.get("depth", 0)),
                "function": child.function,
                "file_name": PurePath(child.file).name,
                "line_text": str(line) if line == end_line else f"{line}-{end_line}",
                "kind": "trace_line",
                "source_text": str(statement.get("source_text") or child.metadata.get("source_text", "")),
                "markers": list(statement.get("markers", [])),
            }
        )
    return {
        **_node_payload(node),
        "kind": "function_container",
        "steps": steps,
    }


def _python_function_structure(path: str, function_name: str) -> dict[int, dict[str, Any]]:
    return {int(statement["line"]): statement for statement in _python_function_statements(path, function_name)}


def _python_function_statements(path: str, function_name: str) -> list[dict[str, Any]]:
    try:
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            statements: list[dict[str, Any]] = []
            for statement in node.body:
                _collect_statement_structure(statement, 0, statements, source)
            return sorted(statements, key=lambda item: (int(item["line"]), int(item["end_line"])))
    return []


def _collect_statement_structure(statement: ast.stmt, depth: int, statements: list[dict[str, Any]], source_text: str) -> None:
    markers = _ast_markers(statement)
    line = getattr(statement, "lineno", 0)
    end_line = _statement_visible_end_line(statement)
    if line:
        statements.append(
            {
                "line": line,
                "end_line": end_line,
                "depth": depth,
                "markers": markers,
                "source_text": _statement_source_text(source_text, statement, line, end_line),
            }
        )
    child_depth = depth + 1 if isinstance(statement, (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith, ast.Try)) else depth
    for child in _statement_children(statement):
        _collect_statement_structure(child, child_depth, statements, source_text)


def _statement_visible_end_line(statement: ast.stmt) -> int:
    line = getattr(statement, "lineno", 0)
    end_line = getattr(statement, "end_lineno", line)
    child_lines = [getattr(child, "lineno", 0) for child in _statement_children(statement)]
    child_lines = [child_line for child_line in child_lines if child_line]
    if child_lines:
        return max(line, min(child_lines) - 1)
    return end_line


def _statement_source_text(source_text: str, statement: ast.stmt, start_line: int, end_line: int) -> str:
    if end_line == getattr(statement, "end_lineno", start_line):
        segment = ast.get_source_segment(source_text, statement) or ""
        if segment:
            return _compact_source_text(segment)
    return _read_source_lines(source_text, start_line, end_line)


def _statement_lookup_by_line(statements: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for statement in statements:
        start = int(statement["line"])
        end = int(statement["end_line"])
        for line in range(start, end + 1):
            lookup[line] = statement
    return lookup


def _statement_children(statement: ast.stmt) -> list[ast.stmt]:
    children: list[ast.stmt] = []
    for attr in ("body", "orelse", "finalbody"):
        value = getattr(statement, attr, None)
        if isinstance(value, list):
            children.extend(child for child in value if isinstance(child, ast.stmt))
    handlers = getattr(statement, "handlers", None)
    if isinstance(handlers, list):
        for handler in handlers:
            children.extend(child for child in getattr(handler, "body", []) if isinstance(child, ast.stmt))
    return children


def _ast_markers(statement: ast.stmt) -> list[str]:
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        return ["loop"]
    if isinstance(statement, ast.If):
        return ["branch"]
    if isinstance(statement, ast.Return):
        return ["return"]
    if isinstance(statement, ast.Raise):
        return ["raise"]
    return []


def _render_static_overview(nodes: list[dict[str, Any]], subflow_ids: set[str]) -> str:
    return "".join(_render_static_overview_item(node, subflow_ids) for node in nodes)


def _render_static_overview_item(node: dict[str, Any], subflow_ids: set[str]) -> str:
    if node.get("kind") == "module_lane":
        return _render_static_module_lane(node, subflow_ids)
    if node.get("kind") == "function_container":
        return _render_static_container(node, subflow_ids)
    return _render_static_node(node, subflow_ids)


def _render_static_module_lane(lane: dict[str, Any], subflow_ids: set[str]) -> str:
    items = "".join(_render_static_container(item, subflow_ids) for item in lane.get("items", []))
    return (
        '<div class="module-lane">'
        f'<div class="module-lane-header"><span class="module-badge">{_escape_text(str(lane["module_label"]))}</span></div>'
        f"{items}</div>"
    )


def _render_static_container(container: dict[str, Any], subflow_ids: set[str]) -> str:
    steps = container.get("steps", [])
    step_chunks = []
    for index, step in enumerate(steps):
        if index > 0:
            label = _edge_label(steps[index - 1], step)
            step_chunks.append(f'<div class="edge"><span class="edge-label">{_escape_text(label)}</span></div>')
        step_chunks.append(_render_static_node(step, subflow_ids))
    repeat_badge = (
        f'<span class="repeat-badge">x{_escape_text(str(container["repeat_count"]))}</span>'
        if int(container.get("repeat_count", 1)) > 1
        else ""
    )
    header_title = (
        f'<span class="function-title"><strong>{_escape_text(container["function"])}</strong>{repeat_badge}</span>'
        if repeat_badge
        else f'<strong>{_escape_text(container["function"])}</strong>'
    )
    return (
        '<div class="function-container">'
        f'<div class="function-header">{header_title}'
        f'<code>{_escape_text(container["file_name"])}:{_escape_text(container["line_text"])}</code></div>'
        f'<div class="function-steps">{"".join(step_chunks)}</div>'
        "</div>"
    )


def _render_static_node(node: dict[str, Any], subflow_ids: set[str]) -> str:
    classes = "node clickable" if node["id"] in subflow_ids else "node"
    if node.get("kind") == "call_placeholder":
        classes += " skipped-call"
    if node.get("kind") == "trace_line":
        classes += " trace-line"
    title = str(node.get("display_text") or node.get("source_text") or node["function"]) if node.get("kind") == "trace_line" else node["function"]
    module_badge = f'<span class="module-badge">{_escape_text(str(node["module_label"]))}</span>' if node.get("module_label") else ""
    return (
        f'<button type="button" class="{classes}" data-node-id="{_escape_text(node["id"])}">'
        f'<strong>{_escape_text(title)}</strong><br>'
        f'<code>{_escape_text(node["file_name"])}:{_escape_text(node["line_text"])}</code>'
        f"{module_badge}"
        "</button>"
    )


def _edge_label(previous: dict[str, Any], current: dict[str, Any]) -> str:
    if current.get("kind") == "call_placeholder" or current.get("parent_id"):
        return "call"
    if previous.get("kind") == "call_placeholder":
        return "return"
    if previous.get("parent_id") and not current.get("parent_id"):
        return "return"
    if previous.get("function") == current.get("function"):
        return "step"
    return "return"


def _render_static_subflow(subflow: dict[str, Any] | None) -> str:
    if subflow is None:
        return '<div class="empty">没有子流程。</div>'
    line_chunks = []
    for index, line in enumerate(subflow.get("steps", subflow.get("lines", []))):
        markers = "".join(f'<span class="badge">{_escape_text(marker)}</span>' for marker in line["markers"])
        kind_class = " " + _flow_node_class(line["markers"])
        depth = int(line.get("depth", 0))
        connector = "" if index == 0 else f'<div class="flow-connector flow-depth-connector" style="--depth: {depth}"></div>'
        line_chunks.append(
            connector
            + f'<div class="flow-node{kind_class}" style="--depth: {depth}"><div class="flow-node-inner">'
            f'<code>{_escape_text(str(line.get("line_text", line["line"])))}: {_escape_text(line["source_text"])}</code>{markers}'
            "</div></div>"
        )
    lines = "".join(line_chunks) or '<div class="empty">没有记录到内部行。</div>'
    return (
        f'<h2>{_escape_text(subflow["function"])}</h2>'
        f'<div class="subflow-path">{_escape_text(subflow["file_name"])}:{_escape_text(subflow["line_text"])}</div>'
        f'<div class="subflow-chart">{lines}</div>'
    )


def _node_payload(node: FlowNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "function": node.function,
        "file_name": PurePath(node.file).name,
        "line_text": _line_text(node),
        "parent_id": node.parent_id,
        "kind": sorted(node.kinds)[0] if len(node.kinds) == 1 else "mixed",
        "module_label": node.metadata.get("vllm_module", ""),
    }


def _virtual_node_payload(node: FlowNode, line: int, end_line: int) -> dict[str, Any]:
    source_text = _read_source_range(node.file, line, end_line)
    return {
        "id": f"{node.id}_line_{line}_{end_line}",
        "function": node.function,
        "file_name": PurePath(node.file).name,
        "line_text": str(line) if line == end_line else f"{line}-{end_line}",
        "parent_id": node.parent_id,
        "kind": "trace_segment",
        "source_text": source_text,
        "display_text": _display_source_text(source_text),
        "module_label": node.metadata.get("vllm_module", ""),
    }


def _overview_sort_key(node: FlowNode) -> tuple[float, str]:
    order = node.metadata.get("overview_order")
    if isinstance(order, int | float):
        return (float(order), node.id)
    return (float("inf"), node.id)


def _line_text(node: FlowNode) -> str:
    end_line = node.end_line or node.line
    if end_line == node.line:
        return str(node.line)
    return f"{node.line}-{end_line}"


def _read_source_range(path: str, start_line: int, end_line: int) -> str:
    try:
        source_text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    if compact := _compact_python_statement(source_text, start_line, end_line):
        return compact
    return _read_source_lines(source_text, start_line, end_line)


def _read_source_lines(source_text: str, start_line: int, end_line: int) -> str:
    source_lines = source_text.splitlines()
    snippets = []
    for line_number in range(start_line, end_line + 1):
        if 1 <= line_number <= len(source_lines):
            snippet = source_lines[line_number - 1].strip()
            if snippet and not snippet.startswith("#"):
                snippets.append(snippet)
    return _compact_source_text("\n".join(snippets))


def _compact_python_statement(source_text: str, start_line: int, end_line: int) -> str:
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return ""
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if getattr(node, "lineno", None) == start_line and getattr(node, "end_lineno", start_line) == end_line:
            segment = ast.get_source_segment(source_text, node) or ""
            return _compact_source_text(segment)
    return ""


def _compact_source_text(source_text: str) -> str:
    compact = " ".join(line.strip() for line in source_text.splitlines() if line.strip() and not line.strip().startswith("#"))
    compact = compact.replace("( ", "(").replace(" )", ")")
    compact = compact.replace(",)", ")")
    compact = compact.replace(", )", ")")
    return compact


def _display_source_text(source_text: str, limit: int = 96) -> str:
    if len(source_text) <= limit:
        return source_text
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return _truncate_source_text(source_text, limit)
    if len(tree.body) != 1:
        return _truncate_source_text(source_text, limit)
    statement = tree.body[0]
    if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
        targets = " = ".join(ast.unparse(target) for target in statement.targets)
        return f"{targets} = {_call_display_name(statement.value)}(...)"
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.value, ast.Call):
        return f"{ast.unparse(statement.target)} = {_call_display_name(statement.value)}(...)"
    if isinstance(statement, ast.Expr):
        return _display_expression(statement.value, source_text)
    return _truncate_source_text(source_text, limit)


def _display_expression(expression: ast.expr, fallback: str) -> str:
    if isinstance(expression, ast.Await) and isinstance(expression.value, ast.Call):
        return f"await {_call_display_name(expression.value)}(...)"
    if isinstance(expression, ast.Call):
        return f"{_call_display_name(expression)}(...)"
    return _truncate_source_text(fallback)


def _call_display_name(call: ast.Call) -> str:
    try:
        return ast.unparse(call.func)
    except Exception:
        return "call"


def _truncate_source_text(source_text: str, limit: int = 96) -> str:
    if len(source_text) <= limit:
        return source_text
    return source_text[: limit - 1].rstrip() + "…"


def _source_markers(source_text: str) -> list[str]:
    stripped = source_text.strip()
    markers = []
    if stripped.startswith(("for ", "while ")):
        markers.append("loop")
    if stripped.startswith(("if ", "elif ", "else")):
        markers.append("branch")
    if stripped.startswith("return"):
        markers.append("return")
    if stripped.startswith("raise"):
        markers.append("raise")
    return markers


def _flow_node_class(markers: list[str]) -> str:
    if "return" in markers or "raise" in markers:
        return "return-node"
    if "branch" in markers:
        return "branch-node"
    if "loop" in markers:
        return "loop-node"
    return "statement-node"


def _format_command(command: object) -> str:
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    return str(command or "")


def _render_static_session_meta(session: dict[str, Any]) -> str:
    chunks = []
    if session.get("profile"):
        chunks.append(f'<span>Profile: <code>{_escape_text(str(session["profile"]))}</code></span>')
    if session.get("include_paths"):
        chunks.append(f'<span>Include: <code>{_escape_text(_format_meta_list(session["include_paths"]))}</code></span>')
    if session.get("exclude_paths"):
        chunks.append(f'<span>Exclude: <code>{_escape_text(_format_meta_list(session["exclude_paths"]))}</code></span>')
    if session.get("exclude_modules"):
        chunks.append(f'<span>Exclude Modules: <code>{_escape_text(_format_meta_list(session["exclude_modules"]))}</code></span>')
    return "".join(chunks)


def _format_meta_list(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _escape_text(value: str) -> str:
    return html.escape(value, quote=True)


def _escape_script_json(value: str) -> str:
    return value.replace("</", "<\\/")


def _escape_js_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
