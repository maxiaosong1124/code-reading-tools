from coderead.dap import DapMessageBuffer, encode_message


def test_encode_message_uses_content_length_header():
    payload = encode_message({"seq": 1, "type": "request", "command": "initialize"})

    header, body = payload.split(b"\r\n\r\n", 1)
    assert header.startswith(b"Content-Length: ")
    assert int(header.removeprefix(b"Content-Length: ")) == len(body)
    assert b'"command":"initialize"' in body


def test_parses_one_complete_framed_message():
    buffer = DapMessageBuffer()
    encoded = encode_message({"seq": 2, "type": "event", "event": "stopped"})

    messages = buffer.feed(encoded)

    assert messages == [{"seq": 2, "type": "event", "event": "stopped"}]


def test_parses_multiple_messages_arriving_in_chunks():
    buffer = DapMessageBuffer()
    first = encode_message({"seq": 1, "type": "request", "command": "next"})
    second = encode_message({"seq": 2, "type": "event", "event": "stopped"})
    combined = first + second

    assert buffer.feed(combined[:7]) == []
    messages = buffer.feed(combined[7:25])
    assert messages == []
    messages = buffer.feed(combined[25:])

    assert messages == [
        {"seq": 1, "type": "request", "command": "next"},
        {"seq": 2, "type": "event", "event": "stopped"},
    ]
