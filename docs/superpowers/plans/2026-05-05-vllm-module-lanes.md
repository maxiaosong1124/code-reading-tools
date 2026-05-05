# vLLM Module Lanes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `--profile vllm` 的 `trace.html` Overview 中按 vLLM module 分段展示 trace，例如 `engine -> scheduler -> kv_cache -> model_executor`，减少长 trace 中函数节点刷屏。

**Architecture:** 保持 `FlowGraph` 不变，在 viewer payload 阶段识别 `module_label` 并生成 `module_lane` 容器。非 vLLM profile 保持现有 function container；vLLM profile 下先按连续 module 分段，每个 lane 内继续复用已有 node 渲染。

**Tech Stack:** Python 3.12+、静态 HTML/CSS/JS、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 vLLM module lane RED 测试。
- [x] 实现 Overview module lane payload。
- [x] 更新静态 HTML/CSS/JS 渲染 module lane。
- [x] 更新 README vLLM profile 说明。
- [x] 运行 viewer/profile/CLI targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
rtk uv run pytest tests/test_viewer.py tests/test_profiles.py tests/test_cli.py -q
rtk uv run pytest -q
rtk uv run python -m compileall src tests examples
```
