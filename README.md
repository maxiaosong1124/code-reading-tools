# Debug Flow Trace Tool

这是一个源码阅读辅助工具的 MVP。目标是在用户正常使用 VS Code 调试时，记录实际执行路径，并生成可回顾的 flow graph。

## 当前范围

- Offline trace events 到 flow graph 的推导。
- JSONL trace events 读写。
- Mermaid flowchart 导出。
- DAP `Content-Length` framing。
- Experimental DAP proxy 入口。
- DAP capture：观察 `next`、`stepIn`、`stepOut`、`continue`、`pause` commands，在 `stopped` event 后注入 `stackTrace` request，并把 `stackTrace` response 转成 `TraceEvent` 写入 JSONL。

## 暂不覆盖

- 完整 VS Code extension。
- 完整 cuda-gdb metadata enrichment。
- Web viewer。
- 静态还原所有源码分支和循环。

## 计划使用方式

当前 CLI：

```bash
uv run coderead trace --out-dir .coderead-traces
uv run coderead graph --events .coderead-traces/session/events.jsonl --out-dir .coderead-traces/session
uv run coderead proxy --out-dir .coderead-traces --real-adapter python -m debugpy.adapter
```

`proxy` command 会创建 trace session directory，并在观察到 DAP `stopped` + `stackTrace` response 后写入 `events.jsonl`。当前实现已通过 subprocess DAP E2E fixture 验证完整 capture 链路，并通过真实 `debugpy.adapter` initialize sanity test 验证 adapter 基础通信。

## 当前限制

- `stackTrace` request 由 proxy 注入到底层 adapter，当前完整 stopped capture 使用 DAP fixture 验证；真实 VS Code + debugpy stopped flow 仍需要后续手动配置验证。
- 当前 capture 只记录 stop 后的 stack frames，不记录 scopes、variables 或 CUDA block/thread metadata。
- 当前还没有 VS Code extension，需要手动配置 adapter proxy。
