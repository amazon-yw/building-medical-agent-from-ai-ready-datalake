#!/bin/bash
# Demo warm-up: force Lambda cold start + create Livy sessions + cache schema
echo "🔥 Warming up all MCP servers..."

python3 << 'PYEOF'
import boto3, json, threading, time

REGION = "us-west-2"
lc = boto3.client("lambda", region_name=REGION)

LAMBDAS = ["fhir-mcp-server", "fhir-mcp-legacy"]

# Force cold start
print("Forcing cold start...")
for fn in LAMBDAS:
    cfg = lc.get_function_configuration(FunctionName=fn)
    env = cfg["Environment"]["Variables"]
    env["FORCE_RESTART"] = str(int(time.time()))
    lc.update_function_configuration(FunctionName=fn, Environment={"Variables": env})
    lc.get_waiter("function_updated_v2").wait(FunctionName=fn)
    print(f"  ✅ {fn} restarted")

# Warm up with schema queries
print("\nCreating Livy sessions + caching schema...")
def warmup(fn):
    start = time.time()
    calls = [
        ("list_tables", {}),
        ("get_table_schema", {"table_name": "patient" if "legacy" not in fn else "tbl_01"}),
        ("run_custom_query", {"query": "SELECT 1"}),
    ]
    for tool, args in calls:
        resp = lc.invoke(FunctionName=fn,
            Payload=json.dumps({"toolName": tool, "arguments": args}))
        result = json.loads(resp["Payload"].read())
        status = "✅" if result.get("status") == "success" else "❌"
        print(f"  {status} {fn} → {tool} ({time.time()-start:.0f}s)")

threads = [threading.Thread(target=warmup, args=(fn,)) for fn in LAMBDAS]
for t in threads: t.start()
for t in threads: t.join()

print(f"\n🎉 All sessions ready! (valid for 1 hour)")
PYEOF
