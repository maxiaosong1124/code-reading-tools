# Debugpy E2E Validation 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按任务执行。本计划使用 checkbox (`- [ ]`) 跟踪进度。

**目标:** 用真实 `debugpy.adapter` 做端到端验证，证明 proxy 可以在 DAP 会话中捕获 `stopped` + `stackTrace` 并产出 `events.jsonl`，同时不把内部注入的 `stackTrace` response 泄漏给 client。

**架构:** 新增一个 DAP test client fixture，通过 `coderead proxy --real-adapter python -m debugpy.adapter` 启动真实 adapter。测试使用 DAP 协议完成 initialize、launch、setBreakpoints、configurationDone、continue/next 等流程，并检查 trace session 输出。为避免干扰真实 client，`DapTraceCapture` 要返回哪些 adapter messages 属于内部请求 response，proxy observer 负责从转发流中过滤这些 messages。

**Tech Stack:** Python 3.12 standard library、uv、pytest、debugpy、DAP、JSONL。

---

## 执行规则

- 每完成一个 step，立即把本文件对应 checkbox 从 `[ ]` 改为 `[x]`。
- 每完成一个功能或 task，运行本计划中对应测试命令。
- Python 环境和命令统一使用 `uv`；验证命令使用 `rtk uv run ...`。
- 新增文档和面向用户说明使用中文；专业术语保留英文。
- 遵循 TDD：先写 failing test，再实现。

## 文件结构

- 修改 `pyproject.toml`：增加 dev dependency `debugpy`。
- 修改 `src/coderead/dap_capture.py`：支持过滤内部 `stackTrace` response。
- 修改 `src/coderead/proxy.py`：observer 可返回 replacement bytes，用于过滤转发流。
- 修改 `src/coderead/cli.py`：adapter observer 使用 replacement bytes。
- 创建 `tests/test_debugpy_e2e.py`：真实 debugpy adapter 端到端测试。
- 创建 `tests/fixtures/debuggee.py`：被调试 Python 示例脚本。
- 修改 `README.md`：记录 debugpy E2E 验证方式和当前状态。

## Task 1: 内部 response 过滤能力

**Files:**
- Modify: `tests/test_dap_capture.py`
- Modify: `tests/test_proxy.py`
- Modify: `src/coderead/dap_capture.py`
- Modify: `src/coderead/proxy.py`
- Modify: `src/coderead/cli.py`

- [x] **Step 1: 编写 failing tests**

新增 tests：

- `DapTraceCapture` 收到内部 `stackTrace` response 后生成事件，并返回过滤后的 adapter bytes，不再包含该 response。
- `_pipe` 支持 observer 返回 replacement bytes，写 replacement 而不是原始 chunk。

- [x] **Step 2: 运行 targeted tests 并确认失败**

Run: `rtk uv run pytest tests/test_dap_capture.py tests/test_proxy.py -q`

Expected: fails because capture/proxy 还不支持 replacement bytes。

- [x] **Step 3: 实现内部 response 过滤**

实现：

- `CapturedAdapterChunk` 或等价返回结构，包含 `inject_to_adapter` 和 `forward_to_client`。
- `DapTraceCapture.observe_adapter_bytes` 对内部 `stackTrace` response 生成 event，但不转发给 client。
- `_pipe` 支持 observer replacement bytes。

- [x] **Step 4: 运行 targeted tests 并确认通过**

Run: `rtk uv run pytest tests/test_dap_capture.py tests/test_proxy.py -q`

Expected: all tests pass。

## Task 2: Debugpy E2E 测试

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/fixtures/debuggee.py`
- Create: `tests/test_debugpy_e2e.py`

- [x] **Step 1: 增加 debugpy dev dependency**

在 `pyproject.toml` 的 dev dependency group 中加入 `debugpy>=1.8`。

- [x] **Step 2: 编写 failing debugpy E2E test**

创建真实 DAP client test：

- 启动 `uv run coderead proxy --out-dir TMP --real-adapter python -m debugpy.adapter`。
- 通过 stdin/stdout DAP framing 与 proxy 通信。
- 完成 initialize、launch、setBreakpoints、configurationDone。
- 收到 breakpoint `stopped` 后发送 `continue` 或 `next`。
- 等待 trace `events.jsonl` 出现并至少包含一个 event。

- [x] **Step 3: 运行 debugpy E2E test 并确认失败或暴露问题**

Run: `rtk uv run pytest tests/test_debugpy_e2e.py -q`

Expected: 初次运行可能失败，失败信息应指向真实 DAP 流程或 proxy wiring 问题。

- [x] **Step 4: 修复 E2E 暴露的问题**

根据失败信息修复 DAP launch path、event 等待、response filtering 或 session discovery，不改变已验证的 trace core 行为。

- [x] **Step 5: 运行 debugpy E2E test 并确认通过**

Run: `rtk uv run pytest tests/test_debugpy_e2e.py -q`

Expected: all tests pass。

## Task 3: 文档和完整验证

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-05-debugpy-e2e-validation.md`

- [x] **Step 1: 更新 README**

补充真实 debugpy E2E 已验证路径、运行命令和当前限制。

- [x] **Step 2: 运行完整 tests**

Run: `rtk uv run pytest -q`

Expected: all tests pass。

- [x] **Step 3: 运行 compile check**

Run: `rtk uv run python -m compileall src tests`

Expected: compilation succeeds。

- [x] **Step 4: 检查 git status**

Run: `rtk git status --short`

Expected: only intended files are modified or added。

- [ ] **Step 5: 提交 debugpy E2E validation**

Run:

```bash
git add .
git commit -m "test: validate debugpy DAP capture end to end"
```

Expected: commit succeeds。
