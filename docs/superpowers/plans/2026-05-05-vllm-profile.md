# vLLM Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加 `--profile vllm`，让用户 debug vLLM Python 层时自动过滤第三方噪声，并在图中标识 engine、scheduler、async_llm、triton_kernel、kv_cache 等 vLLM 模块。

**Architecture:** 新增 `coderead.profiles`，集中处理 trace event 过滤、path/module include/exclude 和 vLLM module classification。`coderead graph` 在 build graph 前应用 profile，在 build graph 后给 `FlowNode.metadata` 写入 module 信息；viewer 读取 metadata 显示 module badge。

**Tech Stack:** Python 3.12+、标准库 `pathlib`、pytest、静态 HTML/CSS/JS、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 vLLM profile 过滤测试。
- [x] 写 vLLM module classification 测试。
- [x] 实现 `coderead.profiles`。
- [x] 接入 `coderead graph --profile vllm`、`--include-path`、`--exclude-path`、`--exclude-module`。
- [x] 在 `trace.html` 中显示 profile metadata 和 vLLM module badge。
- [x] 更新 README 使用说明。
- [x] 运行 targeted tests、全量 pytest 和 compileall。
- [x] 优化 Overview 可读性：过滤注释/空行，并把 Python 多行 statement 压缩为单个主流程节点。
- [x] 修复真实 vLLM trace 可读性：Subflow 合并多行参数 statement，Overview 长调用显示短摘要。

## 验证命令

```bash
uv run pytest tests/test_profiles.py tests/test_cli.py tests/test_viewer.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
