"""
agent_mcp.py
CampusVoice agent using the Elastic MCP server + Gemini function calling.
Uses a direct JSON-RPC client (no SDK) to reliably communicate with the
Elastic MCP server on Windows, filtering out telemetry noise from stdout.
"""

import os
import sys
import json
import time
import threading
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"

# Cross-platform MCP binary path
# On Windows: %APPDATA%\npm\mcp-server-elasticsearch.cmd
# On Linux (Cloud Run): /usr/local/bin/mcp-server-elasticsearch
if sys.platform == "win32":
    MCP_BIN = os.path.join(os.environ.get("APPDATA", ""), "npm", "mcp-server-elasticsearch.cmd")
else:
    MCP_BIN = "mcp-server-elasticsearch"

SYSTEM_PROMPT = """You are CampusVoice, an AI analyst that helps administrators, counselors,
and students understand what students really think about universities.

You have access to an Elasticsearch index called 'campus_reviews' containing real student
reviews from Rate My Professors for:
- University of Tennessee Knoxville (school_tag: "utk")
- Vanderbilt University (school_tag: "vanderbilt")
- Georgia Institute of Technology (school_tag: "gatech")
- University of Florida (school_tag: "uf")
- University of Michigan (school_tag: "umich")
- UCLA (school_tag: "ucla")
- Duke University (school_tag: "duke")

Each document contains: school, school_tag, professor_name, department, course,
comment, helpful_rating (1-5), clarity_rating (1-5), difficulty_rating (1-5),
avg_rating, category, date.

When answering:
1. Use the search tool to find relevant reviews — filter by school_tag when asked
2. If comparing two schools, search each separately
3. Synthesize patterns — cite numbers, quote reviews briefly
4. Be direct. Start with findings, no preamble.
5. NEVER use aggregations (aggs/aggregations key) in queries — they return 0 results.
   Instead, fetch reviews with a high 'size' (e.g. 50-100) and sort by avg_rating or helpful_rating descending to find top professors or trends.
   Example for "most praised professors": search with size:50, sort by avg_rating desc, filter by school_tag."""


# ── Simple synchronous JSON-RPC client ────────────────────────────────────────

class MCPClient:
    """Minimal MCP client that communicates over stdio JSON-RPC."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._responses = {}
        self._msg_id = 0

    def start(self):
        # Verify binary exists before attempting to spawn
        if sys.platform != "win32":
            import shutil
            resolved = shutil.which(MCP_BIN)
            if not resolved:
                raise RuntimeError(
                    f"MCP binary not found: {MCP_BIN!r}. "
                    "Ensure @elastic/mcp-server-elasticsearch is installed globally."
                )
        self._proc = subprocess.Popen(
            [MCP_BIN],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={
                **os.environ,
                "ES_URL": os.getenv("ELASTICSEARCH_URL"),
                "ES_API_KEY": os.getenv("ELASTICSEARCH_API_KEY"),
                "ELASTIC_OTEL_NODE_ENABLED": "false",
                "OTEL_SDK_DISABLED": "true",
                "ELASTIC_APM_ACTIVE": "false",
            },
        )
        # Background reader thread — filters out non-JSON-RPC lines
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        # MCP handshake
        self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "campus-voice", "version": "1.0"},
        })
        resp = self._wait(self._msg_id, timeout=30)
        # Send initialized notification (no response expected)
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self._write(notif)

    def _read_loop(self):
        for raw in self._proc.stdout:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line or "jsonrpc" not in line:
                continue
            try:
                msg = json.loads(line)
                if "id" in msg:
                    with self._lock:
                        self._responses[msg["id"]] = msg
            except Exception:
                pass

    def _write(self, obj):
        data = json.dumps(obj).encode() + b"\n"
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def _send(self, method, params=None):
        self._msg_id += 1
        msg = {"jsonrpc": "2.0", "id": self._msg_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._write(msg)
        return self._msg_id

    def _wait(self, msg_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if msg_id in self._responses:
                    return self._responses.pop(msg_id)
            time.sleep(0.05)
        raise TimeoutError(f"No MCP response for id={msg_id} after {timeout}s")

    def list_tools(self):
        msg_id = self._send("tools/list")
        resp = self._wait(msg_id)
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments):
        msg_id = self._send("tools/call", {"name": name, "arguments": arguments})
        resp = self._wait(msg_id, timeout=30)
        if "error" in resp:
            return f"Tool error: {resp['error']}"
        content = resp.get("result", {}).get("content", [])
        return content[0].get("text", "No results") if content else "No results"

    def close(self):
        if self._proc:
            self._proc.terminate()


# ── Gemini tool conversion ─────────────────────────────────────────────────────

GEMINI_UNSUPPORTED_KEYS = {"$schema", "additionalProperties", "additional_properties", "$defs", "definitions"}

def clean_schema(obj):
    """Recursively remove keys that Gemini's function calling doesn't support."""
    if isinstance(obj, dict):
        return {k: clean_schema(v) for k, v in obj.items() if k not in GEMINI_UNSUPPORTED_KEYS}
    if isinstance(obj, list):
        return [clean_schema(i) for i in obj]
    return obj

def tool_to_function_declaration(tool):
    schema = clean_schema(tool.get("inputSchema", {}))
    schema.pop("$schema", None)
    return types.FunctionDeclaration(
        name=tool["name"],
        description=tool.get("description", ""),
        parameters=schema or None,
    )


# ── Main agent loop ────────────────────────────────────────────────────────────

def ask(question: str) -> str:
    mcp = MCPClient()
    start_time = time.time()
    try:
        mcp.start()

        tools = mcp.list_tools()
        print(f"  🔌 Elastic MCP tools: {[t['name'] for t in tools]}")

        # Guard against empty tool list — passing empty Tool to Gemini errors
        gemini_tools = [
            types.Tool(function_declarations=[tool_to_function_declaration(t) for t in tools])
        ] if tools else None

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        messages = [
            types.Content(
                role="user",
                parts=[types.Part(text=f"{SYSTEM_PROMPT}\n\nQuestion: {question}")],
            )
        ]

        for iteration in range(8):
            # Hard time budget — leave headroom before Cloud Run's 300s kills the request
            if time.time() - start_time > 85:
                break

            # After 4 tool rounds, stop offering tools so Gemini must produce text
            use_tools = gemini_tools if iteration < 5 else None

            # Retry on 503 UNAVAILABLE with backoff
            response = None
            for attempt in range(5):
                try:
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=messages,
                        config=types.GenerateContentConfig(tools=use_tools),
                    )
                    break
                except Exception as e:
                    if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < 4:
                        time.sleep(3 * (attempt + 1))  # 3s, 6s, 9s, 12s
                    else:
                        raise
            if response is None:
                raise RuntimeError("Gemini API unavailable after retries")

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                # Empty/None response — retry next iteration rather than giving up
                continue
            parts = candidate.content.parts
            messages.append(types.Content(role="model", parts=parts))

            function_calls = [p for p in parts if p.function_call]
            if not function_calls:
                # Filter out Gemini 2.5 Flash internal "thinking" parts before returning
                text = "\n".join(
                    p.text for p in parts
                    if hasattr(p, "text") and p.text and not getattr(p, "thought", False)
                )
                if text:
                    return text
                # All parts were internal thoughts with no text — retry next iteration
                continue

            tool_results = []
            for part in function_calls:
                fc = part.function_call
                print(f"  🔧 {fc.name}({str(dict(fc.args))[:120]})")
                result_text = mcp.call_tool(fc.name, dict(fc.args))
                tool_results.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": result_text},
                        )
                    )
                )
            # function_response parts only — never mix text into this Content
            messages.append(types.Content(role="user", parts=tool_results))

        return "I searched but couldn't find enough information to answer that question clearly."

    finally:
        mcp.close()


if __name__ == "__main__":
    print(ask("What are students at UTK complaining about most?"))
