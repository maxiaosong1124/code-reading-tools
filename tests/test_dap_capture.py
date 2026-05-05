from coderead.dap import DapMessageBuffer, encode_message
from coderead.dap_capture import DapTraceCapture


def decode_messages(chunks: list[bytes]) -> list[dict]:
    buffer = DapMessageBuffer()
    messages = []
    for chunk in chunks:
        messages.extend(buffer.feed(chunk))
    return messages


def test_records_last_step_command_from_client_request():
    capture = DapTraceCapture(session_id="sess_dap", adapter="debugpy")

    injected = capture.observe_client_bytes(
        encode_message({"seq": 10, "type": "request", "command": "next"})
    )

    assert injected == []
    assert capture.last_step_command == "next"


def test_stopped_event_injects_stack_trace_request_for_thread():
    capture = DapTraceCapture(session_id="sess_dap", adapter="debugpy")

    injected = capture.observe_adapter_bytes(
        encode_message(
            {
                "seq": 11,
                "type": "event",
                "event": "stopped",
                "body": {"reason": "step", "threadId": 7},
            }
        )
    )

    messages = decode_messages(injected)
    assert messages == [
        {
            "seq": 1,
            "type": "request",
            "command": "stackTrace",
            "arguments": {"threadId": 7},
        }
    ]


def test_stack_trace_response_creates_trace_event():
    capture = DapTraceCapture(session_id="sess_dap", adapter="debugpy")
    capture.observe_client_bytes(encode_message({"seq": 10, "type": "request", "command": "stepIn"}))
    injected = capture.observe_adapter_bytes(
        encode_message(
            {
                "seq": 11,
                "type": "event",
                "event": "stopped",
                "body": {"reason": "step", "threadId": 7},
            }
        )
    )
    stack_request = decode_messages(injected)[0]

    capture.observe_adapter_bytes(
        encode_message(
            {
                "seq": 12,
                "type": "response",
                "request_seq": stack_request["seq"],
                "success": True,
                "command": "stackTrace",
                "body": {
                    "stackFrames": [
                        {
                            "id": 100,
                            "name": "forward",
                            "source": {"path": "/repo/model.py"},
                            "line": 81,
                            "column": 5,
                        },
                        {
                            "id": 99,
                            "name": "main",
                            "source": {"path": "/repo/main.py"},
                            "line": 12,
                            "column": 1,
                        },
                    ]
                },
            }
        )
    )

    events = capture.pop_events()
    assert len(events) == 1
    event = events[0]
    assert event.session_id == "sess_dap"
    assert event.adapter == "debugpy"
    assert event.event_type == "stopped"
    assert event.reason == "step"
    assert event.command_before_stop == "stepIn"
    assert event.thread_id == 7
    assert event.top_frame.function == "forward"
    assert event.top_frame.file == "/repo/model.py"
    assert event.top_frame.line == 81
    assert event.top_frame.column == 5
    assert [frame.function for frame in event.stack] == ["forward", "main"]


def test_pop_events_drains_buffer():
    capture = DapTraceCapture(session_id="sess_dap", adapter="debugpy")

    capture._events.append("sentinel")

    assert capture.pop_events() == ["sentinel"]
    assert capture.pop_events() == []
