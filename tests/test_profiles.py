from coderead.models import StackFrame, TraceEvent
from coderead.profiles import apply_trace_profile, classify_vllm_module


def frame(function: str, file: str, line: int = 1) -> StackFrame:
    return StackFrame(function=function, file=file, line=line, language="python")


def stopped(event_id: str, function: str, file: str) -> TraceEvent:
    top = frame(function, file)
    return TraceEvent(
        id=event_id,
        session_id="sess_vllm",
        timestamp="2026-05-05T10:00:00.000Z",
        adapter="debugpy",
        event_type="stopped",
        reason="step",
        command_before_stop="next",
        thread_id=1,
        top_frame=top,
        stack=[top],
    )


def test_vllm_profile_keeps_vllm_frames_and_filters_common_third_party_modules():
    events = [
        stopped("evt_01", "step", "/repo/vllm/vllm/engine/llm_engine.py"),
        stopped("evt_02", "forward", "/repo/vllm/.venv/lib/python3.12/site-packages/torch/nn/modules/module.py"),
        stopped("evt_03", "generate", "/repo/vllm/.venv/lib/python3.12/site-packages/transformers/generation/utils.py"),
        stopped("evt_04", "schedule", "/repo/vllm/vllm/core/scheduler.py"),
        stopped("evt_05", "remote", "/repo/vllm/.venv/lib/python3.12/site-packages/ray/actor.py"),
    ]

    filtered = apply_trace_profile(events, profile="vllm", include_paths=[], exclude_paths=[], exclude_modules=[])

    assert [(event.id, event.top_frame.function) for event in filtered] == [
        ("evt_01", "step"),
        ("evt_04", "schedule"),
    ]
    assert filtered[0].metadata["profile"] == "vllm"
    assert filtered[0].metadata["vllm_module"] == "engine"
    assert filtered[1].metadata["vllm_module"] == "scheduler"


def test_vllm_profile_respects_include_path_for_entry_scripts():
    events = [
        stopped("evt_01", "main", "/repo/examples/offline_inference.py"),
        stopped("evt_02", "step", "/repo/vllm/vllm/engine/llm_engine.py"),
        stopped("evt_03", "forward", "/repo/.venv/lib/python3.12/site-packages/torch/nn/modules/module.py"),
    ]

    filtered = apply_trace_profile(
        events,
        profile="vllm",
        include_paths=["/repo/examples"],
        exclude_paths=[],
        exclude_modules=[],
    )

    assert [event.top_frame.file for event in filtered] == [
        "/repo/examples/offline_inference.py",
        "/repo/vllm/vllm/engine/llm_engine.py",
    ]
    assert filtered[0].metadata["vllm_module"] == "entry"


def test_vllm_profile_keeps_installed_vllm_package_frames():
    events = [
        stopped("evt_01", "step", "/repo/.venv/lib/python3.12/site-packages/vllm/engine/llm_engine.py"),
        stopped("evt_02", "forward", "/repo/.venv/lib/python3.12/site-packages/torch/nn/modules/module.py"),
    ]

    filtered = apply_trace_profile(events, profile="vllm", include_paths=[], exclude_paths=[], exclude_modules=[])

    assert [(event.id, event.top_frame.function) for event in filtered] == [
        ("evt_01", "step"),
    ]
    assert filtered[0].metadata["vllm_module"] == "engine"


def test_classify_vllm_module_covers_core_reading_areas():
    cases = {
        "/repo/vllm/vllm/engine/llm_engine.py": "engine",
        "/repo/vllm/vllm/engine/async_llm_engine.py": "async_llm",
        "/repo/vllm/vllm/v1/engine/async_llm.py": "async_llm",
        "/repo/vllm/vllm/core/scheduler.py": "scheduler",
        "/repo/vllm/vllm/v1/core/scheduler.py": "scheduler",
        "/repo/vllm/vllm/triton_utils/kernels.py": "triton_kernel",
        "/repo/vllm/vllm/model_executor/layers/fused_moe/fused_moe.py": "triton_kernel",
        "/repo/vllm/vllm/attention/backends/flash_attn.py": "attention",
        "/repo/vllm/vllm/worker/cache_engine.py": "kv_cache",
        "/repo/vllm/vllm/v1/core/kv_cache_manager.py": "kv_cache",
        "/repo/vllm/vllm/model_executor/model_loader/loader.py": "model_executor",
        "/repo/vllm/vllm/worker/worker.py": "worker",
    }

    assert {path: classify_vllm_module(path) for path in cases} == cases
