# Function Container Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `trace.html` 中每个函数只作为一个容器出现一次，返回到 parent function 后不重复显示 parent function 大节点，同时在容器内部展示源码行和 call site。

**Architecture:** 保持 `FlowGraph` 的 trace segment 数据不变，在 `coderead.viewer` 中新增 function container payload。Overview 和 Subflow 都通过同一套容器化步骤渲染：函数标题只出现一次，内部 steps 表示源码行、Step Into 调用和 Step Over skipped call。

**Tech Stack:** Python 3.12+、静态 HTML/CSS/JS、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 Overview 函数容器失败测试。
- [x] 实现 Overview 函数容器 payload。
- [x] 更新静态 HTML/CSS/JS 渲染函数容器。
- [x] 写 Subflow 嵌套 call site 测试。
- [x] 实现 Subflow 复用函数容器步骤。
- [x] 重新生成 examples trace.html。
- [x] 运行 targeted tests、全量 pytest 和 compileall。
- [x] 将 Overview 普通步骤标题从 `line N` 改为源码文本。

## 验证命令

```bash
uv run pytest tests/test_viewer.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
