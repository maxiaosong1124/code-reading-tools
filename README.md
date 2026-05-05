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

从 GitHub 安装：

```bash
uv tool install git+https://github.com/USER/REPO.git
```

本地开发版本安装：

```bash
uv tool install --reinstall /home/maxiaosong/work_space/code_reading_tools
```

安装后，在任意要阅读的开源项目根目录启动通用 proxy：

```bash
coderead serve
```

然后在项目已有的 VS Code `launch.json` debug 配置里加一行：

```json
"debugServer": 47111
```

如果需要样例，可以让工具直接输出通用 VS Code 配置：

```bash
coderead samples vscode
```

这个样例不区分普通 Python、vLLM 或其他开源项目；`debugServer` 的接入方式都一样。vLLM 这类项目会在渲染阶段自动识别，不需要启动时指定专用参数。

调试结束后直接渲染最新 session：

```bash
coderead render
```

`render` 会自动找到 `.coderead-traces` 下最新的 `sess_*/events.jsonl`，自动判断普通 Python 或 vLLM，并生成 `.coderead-traces/sess_xxx_output/trace.html`。如果想在调试过程中自动更新页面，可以开一个终端运行：

```bash
coderead watch
```

`watch` 会持续监听最新 trace session，发现 `events.jsonl` 更新后自动重新生成 `trace.html`。测试或脚本里可以使用单次模式：

```bash
coderead watch --once
```

`init` 仍然保留，但只是可选辅助命令：当你想让工具帮你生成 `.vscode/launch.json`、`.vscode/tasks.json` 和 `.coderead/config.json` 时再用。推荐主流程仍然是 `serve` + 手动或模型配置 `debugServer` + `render/watch`。

底层 CLI 仍然保留：

```bash
coderead serve
coderead render
coderead watch
coderead samples vscode
uv run coderead trace --out-dir .coderead-traces
uv run coderead graph --events .coderead-traces/session/events.jsonl --out-dir .coderead-traces/session
uv run coderead graph --events .coderead-traces/session/events.jsonl --out-dir .coderead-traces/session --scenario "验证配置加载路径"
uv run coderead graph --events .coderead-traces/session/events.jsonl --out-dir .coderead-traces/session --view function
uv run coderead graph --events .coderead-traces/session/events.jsonl --out-dir .coderead-traces/session --view line
uv run coderead graph --events .coderead-traces/session/events.jsonl --out-dir .coderead-traces/session --profile vllm --include-path /path/to/vllm/examples --exclude-module torch --exclude-module transformers --exclude-module ray
uv run coderead proxy --out-dir .coderead-traces --real-adapter python -m debugpy.adapter
uv run coderead proxy-server --host 127.0.0.1 --port 47111 --out-dir .coderead-traces --scenario "验证 normalize_numbers 奇偶分支" --real-adapter python -m debugpy.adapter
uv run coderead init --profile default --program app.py --scenario "阅读入口流程"
```

`proxy` command 会创建 trace session directory，并在观察到 DAP `stopped` + `stackTrace` response 后写入 `events.jsonl`。当前实现已通过 subprocess DAP E2E fixture 验证完整 capture 链路，并通过真实 `debugpy.adapter` initialize sanity test 验证 adapter 基础通信。

`graph` command 默认生成 trace-level 阅读图：按真实 debug 时间顺序把连续停靠点合并成片段，过滤常见 Python runtime frame 和 module wrapper，并避免把函数返回画成反向主边。单线程 trace 默认隐藏 thread label，边标签使用 `call` / `return` 这类阅读友好的术语。主线节点保持在外层，step into 的函数作为可点击子流程展示；step over 经过但没有进入的直接函数调用会显示为虚线 call placeholder。生成文件包括 `trace.html`、`graph.json`、`graph.mmd` 和 `trace.md`；其中 `trace.html` 是推荐主入口，左侧显示 Overview，点击子函数后右侧显示 Subflow。Subflow 按真实 debug 停靠顺序展示内部行，因此 loop 和 branch 会保留实际走过的路径；视觉缩进和 loop/branch/return 标记来自 Python AST。Mermaid 图默认不显示 hit count，减少视觉噪声；hit count 保留在 `graph.json` 和 `trace.md` 里。如果需要函数聚合图，可以使用 `--view function`；如果需要查看逐行 debug stop 细节，可以使用 `--view line`。

## vLLM 阅读模式

`render` 默认会自动识别 vLLM trace；底层 `graph --profile vllm` 也可以显式启用 vLLM 阅读模式。vLLM 自身的 Python frame 会被保留，包括源码目录、editable install 和普通 `site-packages/vllm` 安装路径；`torch`、`transformers`、`ray` 等第三方 frame 默认过滤。当前覆盖的模块标签包括：

- `engine`：`vllm/engine/*`
- `async_llm`：`async_llm.py`、`async_llm_engine.py`
- `scheduler`：`scheduler.py`
- `kv_cache`：`kv_cache_*`、`cache_engine.py`、`block_manager`
- `triton_kernel`：`triton`、`fused_moe`、`custom_op`
- `attention`：attention backend 和 attention layers
- `model_executor`：model loading、layers、executor 相关路径
- `worker`：worker 相关路径

如果需要手动调用底层 `graph`，可以显式指定入口脚本目录：

```bash
uv run coderead graph \
  --events .coderead-traces/session/events.jsonl \
  --out-dir .coderead-traces/session_output \
  --profile vllm \
  --include-path /home/user/vllm/examples \
  --exclude-module torch \
  --exclude-module transformers \
  --exclude-module ray
```

`trace.html` 会在顶部显示 profile、include/exclude 配置，并在节点上显示 vLLM module badge，方便区分 scheduler、engine、kv cache、triton kernel 等路径。`--profile vllm` 下 Overview 会按连续 module 分成 module lane，例如 `engine -> scheduler -> kv_cache -> model_executor`，长 trace 会先呈现模块级路径，再在 lane 内展开具体函数步骤。连续重复的同一函数片段会折叠成一个节点并显示 `xN`，用于压缩 decode loop、scheduler loop 这类重复路径；这不是全局 hit count，只表示相邻重复片段的折叠次数。当前 profile 主要针对 Python 层阅读；CUDA kernel 和 C++ 扩展后续需要接入 gdb/cuda-gdb 或 tree-sitter。

## VS Code 试用示例

仓库已包含一个可以手动验证的 Python debugpy 示例：

- 示例代码：`examples/python_debuggee/app.py`
- VS Code 配置：`examples/python_debuggee/.vscode/launch.json`
- 中文说明：`docs/vscode-debugpy-example.md`

先在仓库根目录启动通用 proxy：

```bash
uv run coderead serve
```

然后用 VS Code 打开 `examples/python_debuggee`，选择 `CodeRead: Python debugpy 示例` 开始调试。

## 当前限制

- `stackTrace` request 由 proxy 注入到底层 adapter，当前完整 stopped capture 使用 DAP fixture 验证；真实 VS Code + debugpy stopped flow 仍需要后续手动配置验证。
- 当前 capture 只记录 stop 后的 stack frames，不记录 scopes、variables 或 CUDA block/thread metadata。
- 当前还没有 VS Code extension，需要手动配置 adapter proxy。
