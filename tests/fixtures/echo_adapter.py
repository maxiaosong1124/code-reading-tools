from coderead.dap import DapMessageBuffer, encode_message

import sys


buffer = DapMessageBuffer()
seq = 1

while True:
    chunk = sys.stdin.buffer.read1(8192)
    if not chunk:
        break
    for message in buffer.feed(chunk):
        command = message["command"]
        if command == "next":
            sys.stdout.buffer.write(
                encode_message(
                    {
                        "seq": seq,
                        "type": "event",
                        "event": "stopped",
                        "body": {"reason": "step", "threadId": 1},
                    }
                )
            )
            seq += 1
            sys.stdout.buffer.flush()
            continue
        if command == "stackTrace":
            sys.stdout.buffer.write(
                encode_message(
                    {
                        "seq": seq,
                        "type": "response",
                        "request_seq": message["seq"],
                        "success": True,
                        "command": "stackTrace",
                        "body": {
                            "stackFrames": [
                                {
                                    "id": 1,
                                    "name": "main",
                                    "source": {"path": "/repo/app.py"},
                                    "line": 10,
                                    "column": 1,
                                }
                            ]
                        },
                    }
                )
            )
            seq += 1
            sys.stdout.buffer.flush()
            continue
        sys.stdout.buffer.write(
            encode_message(
                {
                    "seq": seq,
                    "type": "response",
                    "request_seq": message["seq"],
                    "success": True,
                    "command": command,
                }
            )
        )
        seq += 1
        sys.stdout.buffer.flush()
