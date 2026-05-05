# Trace View And Scenario Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将默认 graph 改为面向源码阅读回顾的 Trace View，并为每次 trace/session 支持 scenario 场景说明和 `trace.md` 回顾笔记。

**Architecture:** 新增 trace-level graph builder：过滤 runtime frame，按 debug 时间顺序生成连续片段节点，同一个函数连续停靠点合并为一个 segment，函数返回后的调用者续执行会生成新的 segment，避免反向 return 边。`TraceStore` 扩展 session metadata，CLI 支持 `--scenario`，graph 命令生成 `graph.json`、`graph.mmd` 和 `trace.md`。

**Tech Stack:** Python 3.12+、argparse、pytest、Markdown、Mermaid。

---

## 文件结构

- 修改 `src/coderead/graph.py`：新增 `build_trace_flow_graph()`，并让 `build_flow_graph()` 默认指向 trace view。
- 修改 `src/coderead/mermaid.py`：隐藏 trace view 中无意义的 edge label，例如单线程 `t1` 和 `function_return`。
- 修改 `src/coderead/store.py`：扩展 `TraceStore.create()` 支持 scenario、cwd、command metadata，并新增 session metadata 读取/更新能力。
- 新增 `src/coderead/report.py`：生成 `trace.md`。
- 修改 `src/coderead/cli.py`：`graph --view trace|function|line` 默认 trace，支持 `--scenario`；`trace/proxy/proxy-server` 支持 `--scenario`。
- 修改 `tests/test_graph.py`、`tests/test_cli.py`、`tests/test_store.py`：覆盖 trace view、scenario metadata、trace.md。
- 修改 `README.md`、`docs/vscode-debugpy-example.md`：更新默认渲染说明。

## 进度

- [x] 创建实施计划。
- [x] 写 trace view failing tests。
- [x] 运行测试确认 RED。
- [x] 实现 trace view graph。
- [x] 运行 graph tests 确认 GREEN。
- [x] 写 scenario/session/report failing tests。
- [x] 运行测试确认 RED。
- [x] 实现 scenario metadata 和 `trace.md`。
- [x] 更新 CLI view 默认值和文档。
- [x] 运行全量 pytest 和 compileall。
- [x] 更新本计划最终状态。
- [x] 清理 Trace View 默认显示：过滤 module wrapper，弱化 edge label，隐藏单线程 thread label。
- [x] 支持 Hierarchical Trace View：用 subgraph 表达函数进入后的嵌套源码流程。
- [x] 调整为 Mainline Trace View：主线保持外层顺序，step into 的子函数用独立 subgraph 展示。
- [x] 子接口 subgraph 内展开实际走过的 line-level internal flow，并显示源码行内容。
- [x] 将默认子接口内部展示从 line graph 改为 summary，避免 loop/step 回边让图过乱。
- [x] 在 overview 中显示 Step Over 经过但未进入的源码行函数调用占位节点。

## 验证命令

```bash
uv run pytest tests/test_graph.py -q
uv run pytest tests/test_cli.py tests/test_store.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
