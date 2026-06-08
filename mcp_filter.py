"""
mcp_filter.py
Proxy wrapper for the Elastic MCP server.
Strips non-JSON-RPC lines (e.g. OpenTelemetry telemetry JSON)
from stdout before they reach the Python MCP client parser.
"""

import subprocess
import sys
import os
import threading

MCP_BIN = os.path.join(os.environ.get("APPDATA", ""), "npm", "mcp-server-elasticsearch.cmd")


def main():
    server = subprocess.Popen(
        [MCP_BIN],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # suppress stderr noise
        env={**os.environ, "ELASTIC_OTEL_NODE_ENABLED": "false", "OTEL_SDK_DISABLED": "true"},
    )

    def filter_stdout():
        """Only forward lines that look like JSON-RPC messages."""
        for raw_line in server.stdout:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if line and "jsonrpc" in line:
                sys.stdout.buffer.write(raw_line)
                sys.stdout.buffer.flush()

    def pipe_stdin():
        """Forward stdin from Python MCP client to the server."""
        for raw_line in sys.stdin.buffer:
            try:
                server.stdin.write(raw_line)
                server.stdin.flush()
            except BrokenPipeError:
                break

    t1 = threading.Thread(target=filter_stdout, daemon=True)
    t2 = threading.Thread(target=pipe_stdin, daemon=True)
    t1.start()
    t2.start()
    server.wait()


if __name__ == "__main__":
    main()
