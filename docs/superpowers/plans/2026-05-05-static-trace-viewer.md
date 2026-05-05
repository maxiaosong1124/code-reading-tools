# Static Trace Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成离线 `trace.html`，提供成熟的源码阅读回顾入口：overview 主流程清晰，点击子函数后在右侧查看对应子流程图。

**Architecture:** 新增 `coderead.viewer` 负责从 `FlowGraph` 和 session metadata 渲染纯 HTML/CSS/JS 页面。页面不依赖 VS Code Mermaid Preview：左侧用 DOM 渲染主线，右侧用 DOM 渲染选中的 subflow summary。`coderead graph` 在现有 `graph.json`、`graph.mmd`、`trace.md` 外额外输出 `trace.html`。

**Tech Stack:** Python 3.12+、标准库 `html`/`json`、pytest、静态 HTML/CSS/JS。

---

## 进度

- [x] 创建实施计划。
- [x] 写 viewer HTML 输出测试。
- [x] 写 CLI 输出 `trace.html` 测试。
- [x] 实现 `src/coderead/viewer.py`。
- [x] 接入 `coderead graph`。
- [x] 更新 README 和 VS Code 示例说明。
- [x] 运行全量 pytest 和 compileall。
- [x] 修复 Step Over call placeholder 在 Overview 中被追加到后面的顺序问题。

## 验证命令

```bash
rtk uv run pytest tests/test_viewer.py tests/test_cli.py -q
rtk uv run pytest -q
rtk uv run python -m compileall src tests examples
```
