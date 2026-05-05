# AGENTS.md

## 本仓库工作规则

- 始终遵循 `/home/maxiaosong/.codex/RTK.md`：所有 shell 命令默认使用 `rtk` 前缀。
- 回复用户和编写仓库文档时始终使用中文；专业术语保留英文，例如 DAP、Trace Proxy、debugpy、JSONL、Mermaid、pytest。
- Python 环境管理始终使用 `uv`；运行 Python、pytest、compileall 或工具脚本时使用 `rtk uv run ...`，不要直接使用 `python3 -m ...`、裸 `pytest` 或其他 Python 环境管理方式。
- 每完成一个功能或阶段性任务，必须运行对应测试或验证命令，并在回复中说明验证结果。
- 实施过程中必须实时更新实施文档中的进度 checkbox；每完成一个 step 或 task，就同步更新对应计划文件。
- 不要在没有用户明确要求的情况下回滚用户已有改动。
- 代码实现优先保持小步提交、小范围修改，并遵循现有设计文档。
