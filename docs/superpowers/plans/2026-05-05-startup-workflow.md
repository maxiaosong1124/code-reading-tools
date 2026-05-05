# Startup Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前手动启动 proxy、查找 session、执行 graph 的流程压缩成 `coderead init`、`coderead render`、`coderead watch`，让普通 Python 和 vLLM 项目能在 VS Code 中更接近“启动就能用”。

**Architecture:** 新增 `coderead.workflow` 封装项目配置、VS Code 文件生成、最新 trace session 查找、单次 render 和 watch loop。`coderead.cli` 只负责参数解析和调用 workflow；已有 `graph`、`proxy-server` 行为保持兼容。

**Tech Stack:** Python 3.12+、VS Code `launch.json`/`tasks.json`、DAP debugServer、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 `coderead init` RED 测试。
- [x] 写 `coderead render` RED 测试。
- [x] 写 `coderead watch --once` RED 测试。
- [x] 实现 `coderead.workflow`。
- [x] 接入 `init`、`render`、`watch` CLI。
- [x] 更新 README 使用说明。
- [x] 运行 targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
