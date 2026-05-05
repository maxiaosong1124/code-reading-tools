# vLLM Repeat Folding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `--profile vllm` 的 `trace.html` 中折叠连续重复的 module/function 片段，让 vLLM decode loop、scheduler loop、worker loop 的阅读路径更紧凑。

**Architecture:** 保持 `FlowGraph` 原始 trace 不变，只在 viewer payload 阶段对 vLLM `module_lane` 内的相邻重复 `function_container` 做折叠，并在静态 HTML/JS 中用 `xN` badge 表示重复次数。非 vLLM profile 不启用该行为，避免影响普通源码阅读视图。

**Tech Stack:** Python 3.12+、静态 HTML/CSS/JS、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 vLLM function repeat folding RED 测试。
- [x] 实现 `repeat_count` payload 折叠。
- [x] 更新静态 HTML/CSS/JS repeat badge 渲染。
- [x] 更新 README vLLM profile 说明。
- [x] 运行 targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
uv run pytest tests/test_viewer.py tests/test_profiles.py tests/test_cli.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
