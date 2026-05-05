# Universal Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CodeRead 的推荐使用方式改成安装一次、所有开源项目统一接入：`coderead serve` 启动通用 DAP proxy，项目只需要在已有 `launch.json` 中加 `debugServer`，`coderead render/watch` 自动识别普通 Python 或 vLLM。

**Architecture:** 保留现有 `proxy-server`、`init` 作为底层/可选命令，新增面向用户的 `serve` 和 `samples vscode`。`workflow` 增加 `auto` profile：渲染时检查 trace 路径，若命中 vLLM 源码或 installed package，则应用 vLLM profile，否则走 default profile。

**Tech Stack:** Python 3.12+、DAP debugServer、VS Code `launch.json` sample、pytest、uv。

---

## 进度

- [x] 创建实施计划。
- [x] 写 `coderead samples vscode` RED 测试。
- [x] 写 `coderead render` auto profile RED 测试。
- [x] 写 `coderead serve` parser/command RED 测试。
- [x] 实现 auto profile detection 和 sample 输出。
- [x] 接入 `serve`、`samples vscode` CLI。
- [x] 更新 README，把 `init` 降级为可选辅助命令。
- [x] 运行 targeted tests、全量 pytest 和 compileall。

## 验证命令

```bash
uv run pytest tests/test_cli.py tests/test_profiles.py -q
uv run pytest -q
uv run python -m compileall src tests examples
```
