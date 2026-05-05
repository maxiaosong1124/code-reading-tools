# Subflow Execution Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `trace.html` 的 Subflow 按真实 debug 停靠顺序展示内部执行路径，而不是按源码行号排序，避免 vLLM loop/branch 回顾时失真。

**Architecture:** 在 `build_trace_flow_graph` 生成 internal line nodes 时，把每个子函数 trace segment 的停靠行序列写入 segment metadata。Viewer 渲染 Subflow 时优先使用该 sequence 构造 steps，同时继续复用 Python AST depth/markers 做视觉层级。

**Tech Stack:** Python 3.12+、静态 HTML/CSS/JS、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 Subflow execution order RED 测试。
- [x] 在 graph metadata 中记录 internal line sequence。
- [x] 让 viewer Subflow 使用真实执行顺序。
- [x] 更新 README 说明 Subflow 顺序语义。
- [x] 运行 targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
rtk uv run pytest tests/test_graph.py tests/test_viewer.py -q
rtk uv run pytest -q
rtk uv run python -m compileall src tests examples
```
