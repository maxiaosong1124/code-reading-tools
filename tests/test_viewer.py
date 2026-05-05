from coderead.graph import build_trace_flow_graph
from coderead.models import StackFrame, TraceEvent
from coderead.viewer import _containerize_vllm_modules, _overview_payload, _render_static_overview, _view_payload, render_trace_html


def frame(function: str, file: str, line: int) -> StackFrame:
    return StackFrame(function=function, file=file, line=line, language="python")


def stopped(
    event_id: str,
    function: str,
    file: str,
    line: int,
    *,
    stack: list[StackFrame],
    command: str = "next",
) -> TraceEvent:
    top = StackFrame(function=function, file=file, line=line, language="python")
    return TraceEvent(
        id=event_id,
        session_id="sess_viewer",
        timestamp=f"2026-05-05T10:40:{int(event_id.removeprefix('evt_')):02d}.000Z",
        adapter="debugpy",
        event_type="stopped",
        reason="step",
        command_before_stop=command,
        thread_id=1,
        top_frame=top,
        stack=stack,
    )


def test_render_trace_html_contains_overview_and_clickable_subflow(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    summarize([1, 2])\n"
        "def summarize(values):\n"
        "    for value in values:\n"
        "        if value > 1:\n"
        "            return value\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    summarize_4 = frame("summarize", str(source), 4)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "summarize", str(source), 4, stack=[summarize_4, main_2], command="stepIn"),
            stopped("evt_03", "summarize", str(source), 5, stack=[frame("summarize", str(source), 5), main_2]),
            stopped("evt_04", "summarize", str(source), 6, stack=[frame("summarize", str(source), 6), main_2]),
        ]
    )

    html = render_trace_html(
        graph=graph,
        scenario="验证 summarize 子流程",
        session={"session_id": "sess_viewer", "cwd": "/repo", "command": ["python", "app.py"]},
    )

    assert "<!doctype html>" in html
    assert "Trace Viewer" in html
    assert "验证 summarize 子流程" in html
    assert 'data-node-id="trace_0002_summarize"' in html
    assert "function selectSubflow" in html
    assert "for value in values:" in html
    assert "if value &gt; 1:" in html
    assert "return value" in html
    assert "subflow-chart" in html
    assert "function-container" in html
    assert "flow-node loop-node" in html
    assert "flow-node branch-node" in html
    assert "flow-node return-node" in html
    assert "flow-connector" in html


def test_render_trace_html_shows_skipped_call_placeholder(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    summary = summarize(values)\n"
        "    print(summary)\n",
        encoding="utf-8",
    )
    main_1 = frame("main", str(source), 1)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 1, stack=[main_1]),
            stopped("evt_02", "main", str(source), 2, stack=[frame("main", str(source), 2)]),
            stopped("evt_03", "main", str(source), 3, stack=[frame("main", str(source), 3)]),
        ]
    )

    html = render_trace_html(graph=graph, scenario="验证 step over 调用", session={})

    assert "summarize" in html
    assert "skipped-call" in html


def test_render_trace_html_orders_skipped_call_before_following_main_segment(tmp_path):
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
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "normalize_numbers", str(source), 1, stack=[normalize_1, main_2], command="stepIn"),
            stopped("evt_03", "main", str(source), 3, stack=[frame("main", str(source), 3)]),
            stopped("evt_04", "main", str(source), 4, stack=[frame("main", str(source), 4)]),
        ]
    )

    html = render_trace_html(graph=graph, scenario="顺序验证", session={})
    overview = _overview_payload(
        graph,
        sorted(
            [node for node in graph.nodes.values() if "trace_segment" in node.kinds or "call_placeholder" in node.kinds],
            key=lambda node: node.metadata["overview_order"],
        ),
    )

    assert [(node["function"], node["line_text"], node["kind"]) for node in overview] == [
        ("main", "2", "trace_segment"),
        ("normalize_numbers", "1", "trace_segment"),
        ("main", "3", "trace_segment"),
        ("summarize", "3", "call_placeholder"),
        ("main", "4", "trace_segment"),
    ]
    assert "<strong>summarize</strong>" in html


def test_render_trace_html_deduplicates_returned_call_site_line(tmp_path):
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
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "normalize_numbers", str(source), 1, stack=[normalize_1, main_2], command="stepIn"),
            stopped("evt_03", "main", str(source), 2, stack=[frame("main", str(source), 2)]),
            stopped("evt_04", "main", str(source), 3, stack=[frame("main", str(source), 3)]),
        ]
    )

    overview = _overview_payload(
        graph,
        sorted(
            [node for node in graph.nodes.values() if "trace_segment" in node.kinds or "call_placeholder" in node.kinds],
            key=lambda node: node.metadata["overview_order"],
        ),
    )

    assert [(node["function"], node["line_text"], node["kind"]) for node in overview] == [
        ("main", "2", "trace_segment"),
        ("normalize_numbers", "1", "trace_segment"),
        ("main", "3", "trace_segment"),
        ("summarize", "3", "call_placeholder"),
    ]


def test_view_payload_groups_main_steps_inside_single_function_container(tmp_path):
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
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "normalize_numbers", str(source), 1, stack=[normalize_1, main_2], command="stepIn"),
            stopped("evt_03", "main", str(source), 2, stack=[frame("main", str(source), 2)]),
            stopped("evt_04", "main", str(source), 3, stack=[frame("main", str(source), 3)]),
            stopped("evt_05", "main", str(source), 4, stack=[frame("main", str(source), 4)]),
        ]
    )

    payload = _view_payload(graph=graph, scenario="容器视图", session={})

    assert [(item["function"], item["kind"]) for item in payload["overview"]] == [
        ("main", "function_container"),
    ]
    main_steps = payload["overview"][0]["steps"]
    assert [(step["function"], step["line_text"], step["kind"]) for step in main_steps] == [
        ("main", "2", "trace_line"),
        ("normalize_numbers", "1", "trace_segment"),
        ("main", "3", "trace_line"),
        ("summarize", "3", "call_placeholder"),
        ("main", "4", "trace_line"),
    ]


def test_render_trace_html_uses_function_container_for_overview(tmp_path):
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
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "normalize_numbers", str(source), 1, stack=[normalize_1, main_2], command="stepIn"),
            stopped("evt_03", "main", str(source), 2, stack=[frame("main", str(source), 2)]),
            stopped("evt_04", "main", str(source), 3, stack=[frame("main", str(source), 3)]),
            stopped("evt_05", "main", str(source), 4, stack=[frame("main", str(source), 4)]),
        ]
    )

    html = render_trace_html(graph=graph, scenario="容器视图", session={})

    assert '<div class="function-container">' in html
    assert '<div class="function-header"><strong>main</strong><code>app.py:2-4</code></div>' in html
    assert 'data-node-id="trace_0003_main_line_3_3"><strong>summary = summarize(normalized)</strong>' in html
    assert '<strong>line 3</strong>' not in html
    assert '<strong>summarize</strong>' in html


def test_view_payload_subflow_uses_function_container_steps(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    summarize([1, 2])\n"
        "def summarize(values):\n"
        "    for value in values:\n"
        "        if value > 1:\n"
        "            return value\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    summarize_4 = frame("summarize", str(source), 4)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "summarize", str(source), 4, stack=[summarize_4, main_2], command="stepIn"),
            stopped("evt_03", "summarize", str(source), 5, stack=[frame("summarize", str(source), 5), main_2]),
            stopped("evt_04", "summarize", str(source), 6, stack=[frame("summarize", str(source), 6), main_2]),
        ]
    )

    payload = _view_payload(graph=graph, scenario="子流程容器", session={})
    subflow = payload["subflows"][0]

    assert subflow["kind"] == "function_container"
    assert [(step["line"], step["kind"], step["markers"]) for step in subflow["steps"]] == [
        (4, "trace_line", ["loop"]),
        (5, "trace_line", ["branch"]),
        (6, "trace_line", ["return"]),
    ]


def test_view_payload_subflow_preserves_python_ast_nesting_depth(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    score([[1, 2], [3]])\n"
        "def score(groups):\n"
        "    total = 0\n"
        "    for group in groups:\n"
        "        for value in group:\n"
        "            if value % 2 == 0:\n"
        "                total += value\n"
        "            else:\n"
        "                total -= value\n"
        "    return total\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    score_4 = frame("score", str(source), 4)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "score", str(source), 4, stack=[score_4, main_2], command="stepIn"),
            stopped("evt_03", "score", str(source), 5, stack=[frame("score", str(source), 5), main_2]),
            stopped("evt_04", "score", str(source), 6, stack=[frame("score", str(source), 6), main_2]),
            stopped("evt_05", "score", str(source), 7, stack=[frame("score", str(source), 7), main_2]),
            stopped("evt_06", "score", str(source), 8, stack=[frame("score", str(source), 8), main_2]),
            stopped("evt_07", "score", str(source), 11, stack=[frame("score", str(source), 11), main_2]),
        ]
    )

    payload = _view_payload(graph=graph, scenario="AST 子流程", session={})
    steps = payload["subflows"][0]["steps"]

    assert [(step["line"], step["depth"], step["markers"]) for step in steps] == [
        (4, 0, []),
        (5, 0, ["loop"]),
        (6, 1, ["loop"]),
        (7, 2, ["branch"]),
        (8, 3, []),
        (11, 0, ["return"]),
    ]


def test_view_payload_subflow_preserves_debug_execution_order_for_loops(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    decode([1, 2])\n"
        "def decode(values):\n"
        "    total = 0\n"
        "    for value in values:\n"
        "        total += value\n"
        "    return total\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    decode_4 = frame("decode", str(source), 4)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "decode", str(source), 4, stack=[decode_4, main_2], command="stepIn"),
            stopped("evt_03", "decode", str(source), 5, stack=[frame("decode", str(source), 5), main_2]),
            stopped("evt_04", "decode", str(source), 6, stack=[frame("decode", str(source), 6), main_2]),
            stopped("evt_05", "decode", str(source), 5, stack=[frame("decode", str(source), 5), main_2]),
            stopped("evt_06", "decode", str(source), 6, stack=[frame("decode", str(source), 6), main_2]),
            stopped("evt_07", "decode", str(source), 7, stack=[frame("decode", str(source), 7), main_2]),
        ]
    )

    payload = _view_payload(graph=graph, scenario="loop 顺序", session={})
    steps = payload["subflows"][0]["steps"]

    assert [step["line"] for step in steps] == [4, 5, 6, 5, 6, 7]
    assert [step["markers"] for step in steps] == [[], ["loop"], [], ["loop"], [], ["return"]]


def test_render_trace_html_subflow_uses_depth_for_visual_nesting(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def main():\n"
        "    score([[1, 2]])\n"
        "def score(groups):\n"
        "    for group in groups:\n"
        "        for value in group:\n"
        "            if value % 2 == 0:\n"
        "                return value\n",
        encoding="utf-8",
    )
    main_2 = frame("main", str(source), 2)
    score_4 = frame("score", str(source), 4)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "main", str(source), 2, stack=[main_2]),
            stopped("evt_02", "score", str(source), 4, stack=[score_4, main_2], command="stepIn"),
            stopped("evt_03", "score", str(source), 5, stack=[frame("score", str(source), 5), main_2]),
            stopped("evt_04", "score", str(source), 6, stack=[frame("score", str(source), 6), main_2]),
            stopped("evt_05", "score", str(source), 7, stack=[frame("score", str(source), 7), main_2]),
        ]
    )

    html = render_trace_html(graph=graph, scenario="嵌套显示", session={})

    assert 'style="--depth: 3"' in html
    assert 'flow-depth-connector' in html


def test_render_trace_html_shows_profile_and_vllm_module_badges(tmp_path):
    source = tmp_path / "vllm" / "engine" / "llm_engine.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def step():\n"
        "    schedule()\n"
        "def schedule():\n"
        "    return None\n",
        encoding="utf-8",
    )
    step_2 = frame("step", str(source), 2)
    schedule_4 = frame("schedule", str(source), 4)
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "step", str(source), 2, stack=[step_2]),
            stopped("evt_02", "schedule", str(source), 4, stack=[schedule_4, step_2], command="stepIn"),
        ]
    )
    for node in graph.nodes.values():
        node.metadata["profile"] = "vllm"
        node.metadata["vllm_module"] = "engine"

    html = render_trace_html(
        graph=graph,
        scenario="vLLM 阅读",
        session={"profile": "vllm", "include_paths": ["/repo/vllm"], "exclude_modules": ["torch"]},
    )

    assert "Profile: <code>vllm</code>" in html
    assert "Include: <code>/repo/vllm</code>" in html
    assert "Exclude Modules: <code>torch</code>" in html
    assert '<span class="module-badge">engine</span>' in html


def test_view_payload_groups_vllm_overview_into_module_lanes(tmp_path):
    engine = tmp_path / "vllm" / "engine" / "llm_engine.py"
    scheduler = tmp_path / "vllm" / "core" / "scheduler.py"
    cache = tmp_path / "vllm" / "v1" / "core" / "kv_cache_manager.py"
    for path in (engine, scheduler, cache):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def f():\n    return None\n", encoding="utf-8")
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "engine_step", str(engine), 1, stack=[frame("engine_step", str(engine), 1)]),
            stopped("evt_02", "schedule", str(scheduler), 1, stack=[frame("schedule", str(scheduler), 1)]),
            stopped("evt_03", "allocate", str(cache), 1, stack=[frame("allocate", str(cache), 1)]),
        ]
    )
    modules = {"llm_engine.py": "engine", "scheduler.py": "scheduler", "kv_cache_manager.py": "kv_cache"}
    for node in graph.nodes.values():
        node.metadata["profile"] = "vllm"
        node.metadata["vllm_module"] = modules[node.file.rsplit("/", 1)[-1]]

    payload = _view_payload(graph=graph, scenario="vLLM lanes", session={"profile": "vllm"})

    assert [(item["kind"], item["module_label"]) for item in payload["overview"]] == [
        ("module_lane", "engine"),
        ("module_lane", "scheduler"),
        ("module_lane", "kv_cache"),
    ]
    assert [item["items"][0]["steps"][0]["function"] for item in payload["overview"]] == [
        "engine_step",
        "schedule",
        "allocate",
    ]


def test_render_trace_html_renders_vllm_module_lanes(tmp_path):
    engine = tmp_path / "vllm" / "engine" / "llm_engine.py"
    scheduler = tmp_path / "vllm" / "core" / "scheduler.py"
    for path in (engine, scheduler):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def f():\n    return None\n", encoding="utf-8")
    graph = build_trace_flow_graph(
        [
            stopped("evt_01", "engine_step", str(engine), 1, stack=[frame("engine_step", str(engine), 1)]),
            stopped("evt_02", "schedule", str(scheduler), 1, stack=[frame("schedule", str(scheduler), 1)]),
        ]
    )
    for node in graph.nodes.values():
        node.metadata["profile"] = "vllm"
        node.metadata["vllm_module"] = "engine" if "llm_engine" in node.file else "scheduler"

    html = render_trace_html(graph=graph, scenario="vLLM lanes", session={"profile": "vllm"})

    assert '<div class="module-lane">' in html
    assert '<div class="module-lane-header"><span class="module-badge">engine</span></div>' in html
    assert '<div class="module-lane-header"><span class="module-badge">scheduler</span></div>' in html


def test_containerize_vllm_modules_folds_adjacent_repeated_functions():
    schedule_container = {
        "id": "container_schedule_1",
        "function": "schedule",
        "file_name": "scheduler.py",
        "line_text": "120",
        "kind": "function_container",
        "steps": [
            {
                "id": "trace_schedule_1",
                "function": "schedule",
                "file_name": "scheduler.py",
                "line_text": "120",
                "parent_id": None,
                "kind": "trace_line",
                "source_text": "scheduled_seq_group = self._schedule()",
                "module_label": "scheduler",
            }
        ],
    }
    repeated_schedule_container = {
        **schedule_container,
        "id": "container_schedule_2",
        "steps": [{**schedule_container["steps"][0], "id": "trace_schedule_2"}],
    }
    allocate_container = {
        "id": "container_allocate",
        "function": "allocate_slots",
        "file_name": "kv_cache_manager.py",
        "line_text": "88",
        "kind": "function_container",
        "steps": [
            {
                "id": "trace_allocate",
                "function": "allocate_slots",
                "file_name": "kv_cache_manager.py",
                "line_text": "88",
                "parent_id": None,
                "kind": "trace_line",
                "source_text": "self.kv_cache_manager.allocate_slots(request)",
                "module_label": "kv_cache",
            }
        ],
    }

    lanes = _containerize_vllm_modules([schedule_container, repeated_schedule_container, allocate_container])

    assert [(lane["kind"], lane["module_label"]) for lane in lanes] == [
        ("module_lane", "scheduler"),
        ("module_lane", "kv_cache"),
    ]
    assert len(lanes[0]["items"]) == 1
    assert lanes[0]["items"][0]["function"] == "schedule"
    assert lanes[0]["items"][0]["repeat_count"] == 2


def test_static_overview_renders_repeat_badge_for_folded_vllm_items():
    html = _render_static_overview(
        [
            {
                "id": "lane_scheduler",
                "kind": "module_lane",
                "module_label": "scheduler",
                "items": [
                    {
                        "id": "container_schedule_1",
                        "function": "schedule",
                        "file_name": "scheduler.py",
                        "line_text": "120",
                        "kind": "function_container",
                        "repeat_count": 3,
                        "steps": [
                            {
                                "id": "trace_schedule_1",
                                "function": "schedule",
                                "file_name": "scheduler.py",
                                "line_text": "120",
                                "parent_id": None,
                                "kind": "trace_line",
                                "source_text": "scheduled_seq_group = self._schedule()",
                                "module_label": "scheduler",
                            }
                        ],
                    }
                ],
            }
        ],
        set(),
    )

    assert '<span class="repeat-badge">x3</span>' in html
