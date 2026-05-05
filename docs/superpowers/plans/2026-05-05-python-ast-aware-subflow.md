# Python AST-aware Subflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Python Subflow 不再只是按行号列表展示，而是按 Python AST 的 `for` / `while` / `if` / `else` / `return` 源码结构展示嵌套流程。

**Architecture:** 保持 DAP trace 和 `FlowGraph` 不变，在 `coderead.viewer` 的 Subflow payload 阶段读取 Python 源码 AST，并把实际命中过的 internal line 映射到 function body 的结构化 statement。HTML 渲染根据 `depth` 缩进，并用 block 类型展示 loop、branch、return，后续 C++/CUDA 可用 tree-sitter 生成同一类 payload。

**Tech Stack:** Python 3.12+、标准库 `ast`、静态 HTML/CSS/JS、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 Python 嵌套 `for` / `if` 的 RED 测试。
- [x] 实现 AST statement 提取和 trace line 映射。
- [x] 为 Subflow step 增加 `depth` 和结构化 `markers`。
- [x] 更新 HTML/CSS 按 `depth` 展示嵌套结构。
- [x] 重新生成 examples trace.html。
- [x] 运行 viewer tests、全量 pytest 和 compileall。

## 验证命令

```bash
uv run pytest tests/test_viewer.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
