# check_infra.py
"""
Pre-flight health check for The Village Healer (no third-party dependencies).

1. vLLM cluster: GET http://10.0.10.70:8000/v1/models and confirm the Qwen3-VL model is listed.
2. FastMCP server: POST an MCP `initialize` request to http://127.0.0.1:9000/mcp
   (streamable HTTP). This fails if the server is down OR running a different transport.

Run:  python check_infra.py
"""

import json
import time
import urllib.error
import urllib.request

CLUSTER_MODELS_URL = "http://10.0.10.70:8000/v1/models"
EXPECTED_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
MCP_URL = "http://127.0.0.1:9000/mcp"


def _call(url, payload=None, headers=None, timeout=5):
    """Return (status_code, body_text, latency_ms). Raises urllib errors on failure."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data:
        req.add_header("Content-Type", "application/json")

    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.getcode(), body, (time.time() - start) * 1000


def check_cluster() -> bool:
    print(f"📡 Testing vLLM cluster ({CLUSTER_MODELS_URL})...")
    try:
        status, body, ms = _call(CLUSTER_MODELS_URL)
        ids = [m.get("id") for m in json.loads(body).get("data", [])]
        print(f"   HTTP {status} in {ms:.0f}ms | models: {ids}")
        if EXPECTED_MODEL in ids:
            print(f"✅ Model '{EXPECTED_MODEL}' is available.")
            return True
        print(f"❌ Cluster is up but '{EXPECTED_MODEL}' is not listed.")
        return False
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"⚠️ Cluster reachable but requires an API key (HTTP {e.code}). Set a real api_key in agent.py.")
            return True
        print(f"❌ Cluster returned HTTP {e.code}.")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Cannot reach the cluster: {e.reason}")
        print("   Check VPN / network routing / port.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def check_mcp() -> bool:
    print(f"📡 Testing FastMCP server ({MCP_URL})...")
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "check_infra", "version": "0.1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    try:
        status, body, ms = _call(MCP_URL, payload=init, headers=headers)
        if status == 200 and "result" in body:
            print(f"✅ MCP handshake OK (HTTP {status}, {ms:.0f}ms).")
            return True
        print(f"❌ Unexpected MCP response (HTTP {status}): {body[:200]}")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("❌ HTTP 404 at /mcp. The server is probably running SSE transport.")
            print("   MCP_Server.py must call mcp.run(transport='http', ..., path='/mcp').")
        else:
            print(f"❌ MCP server returned HTTP {e.code}.")
        return False
    except urllib.error.URLError as e:
        print(f"❌ Cannot reach the MCP server: {e.reason}")
        print("   Start it first:  uv run python MCP_Server.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("🏥 The Village Healer: Infrastructure Health Check")
    print("=" * 50 + "\n")

    cluster_ok = check_cluster()
    print("-" * 50)
    mcp_ok = check_mcp()

    print("\n" + "=" * 50)
    if cluster_ok and mcp_ok:
        print("🎉 ALL SYSTEMS GO: run `uv run adk web Village_Healer --port 8085`")
    else:
        print("🛑 BLOCKED: fix the failures above first.")
    print("=" * 50)