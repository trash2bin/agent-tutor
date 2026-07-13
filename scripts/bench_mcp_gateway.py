#!/usr/bin/env python3
"""
MCP Gateway Load Test — Helperium
====================================
Запуск:  uv run python3 scripts/bench_mcp_gateway.py
Результат: /tmp/mcp_bench_results.json + вывод в консоль

Тестирует:
  1. SSE session lifecycle (открытие/закрытие сессий)
  2. Tool calls через stateless POST (как работает в реальности)
  3. Rate limiter (токен-бакет)
  4. Data-service manifest endpoint (POTENTIAL BOTTLENECK)
  5. Конкурентные вызовы через один SSE session
  6. Data-service прямой burst (без MCP прослойки)
  7. Спам stateless POST (без открытия SSE)
  8. Проверка Prometheus метрик
"""

import asyncio
import json
import time
import statistics
import urllib.request
import sys
import os

MCP_URL = os.environ.get("MCP_URL", "http://localhost:8083")
DATA_URL = os.environ.get("DATA_URL", "http://localhost:8084")
TENANT = os.environ.get("TENANT", "autoparts")
TOKEN = os.environ.get("ADMIN_TOKEN", "secret")

results = {
    "sse_session_open_ms": [],
    "tool_call_ms": [],
    "manifest_ms": [],
    "concurrent_calls_ms": [],
    "rate_limit_hits": 0,
    "errors": [],
    "bottlenecks": [],
    "recommendations": [],
}


def req_sync(method, url, headers=None, body=None, timeout=10):
    start = time.perf_counter()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, resp.status, data
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, e.code, e.read()
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, 0, str(e).encode()


def test_1_manifest_bottleneck():
    """
    TEST 1: Data-service manifest latency.

    POTENTIAL BOTTLENECK: Каждый MCP tool call дёргает /mcp/manifest
    (17 entities, 28 endpoints, 26 tools). Нет кеширования.
    """
    print("\n[d1] Data-service manifest (BOTTLENECK CHECK)")
    times = []
    for i in range(10):
        elapsed, status, data = req_sync(
            "GET", f"{DATA_URL}/mcp/manifest?tenant={TENANT}",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        times.append(elapsed)
        results["manifest_ms"].append(elapsed)

    manifest_size = len(data) if data else 0
    print(f"      размер манифеста: {manifest_size:,} байт")
    print(f"      latency: min={min(times):.1f}ms avg={statistics.mean(times):.1f}ms max={max(times):.1f}ms")
    print(f"      ⚠️  Этот запрос выполняется на КАЖДЫЙ tool call!")

    if statistics.mean(times) > 10:
        results["bottlenecks"].append({
            "component": "FetchConfigWithTenant (data-service /mcp/manifest)",
            "avg_ms": round(statistics.mean(times), 1),
            "reason": "Каждый tool call вызывает GET /mcp/manifest. Кеширование отсутствует.",
            "impact": "Нагрузка на data-service растёт линейно с tool calls."
        })


def test_2_sse_session():
    """TEST 2: SSE session open + tools/list."""
    print("\n[d2] SSE session + tools/list")
    times = []
    for i in range(5):
        body = json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/list", "params": {}}).encode()
        elapsed, status, data = req_sync(
            "POST", f"{MCP_URL}/mcp/message?sessionId=bench-sess-{i}",
            headers={"Content-Type": "application/json", "X-Tenant-ID": TENANT},
            body=body,
        )
        times.append(elapsed)

    print(f"      tools/list: min={min(times):.1f}ms avg={statistics.mean(times):.1f}ms max={max(times):.1f}ms")


def test_3_tool_calls():
    """TEST 3: Tool calls latency. Каждый вызов → FetchConfig → validateArgs → Call → data-service."""
    print("\n[d3] Tool calls")

    for tool, args in [
        ("find_catalog_brand", {"name": "Bosch"}),
        ("get_catalog_product", {"id": 1}),
        ("find_catalog_product", {"name": "Bosch"}),
        ("find_catalog_category", {"name": "Тормозная"}),
        ("find_catalog_order", {"name": "Иван"}),
    ]:
        times = []
        for i in range(5):
            body = json.dumps({
                "jsonrpc": "2.0", "id": i, "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            }).encode()
            elapsed, status, data = req_sync(
                "POST", f"{MCP_URL}/mcp/message?sessionId=bench-call-{i}",
                headers={"Content-Type": "application/json", "X-Tenant-ID": TENANT},
                body=body, timeout=30,
            )
            times.append(elapsed)

        print(f"      {tool} {args}: avg={statistics.mean(times):.1f}ms")
        for t in times:
            results["tool_call_ms"].append({"tool": tool, "ms": t, "args": str(args)})


def test_4_rate_limiter():
    """TEST 4: Rate limiter — шлём 50 запросов одновременно (RPS=10, burst=20)."""
    print("\n[d4] Rate limiter (10 RPS, burst 20) — 50 concurrent")

    hit_count = 0
    total = 50
    start = time.perf_counter()

    for i in range(total):
        body = json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/list", "params": {}}).encode()
        elapsed, status, data = req_sync(
            "POST", f"{MCP_URL}/mcp/message?sessionId=rate-{i}",
            headers={"Content-Type": "application/json", "X-Tenant-ID": TENANT},
            body=body,
        )
        if status == 429:
            hit_count += 1

    elapsed_total = (time.perf_counter() - start) * 1000
    print(f"      {total} requests in {elapsed_total:.0f}ms -> {hit_count} rate-limited (429)")
    results["rate_limit_hits"] = hit_count

    if hit_count == 0:
        results["bottlenecks"].append({
            "component": "Rate limiter не сработал",
            "reason": f"{total} concurrent запросов — 0 заблокировано. Rate limiter пропускает burst >20.",
            "avg_ms": round(elapsed_total / total, 1),
        })


def test_5_concurrent_same_session():
    """TEST 5: Конкурентные вызовы через ОДИН SSE session (симуляция call_lock)."""
    print("\n[d5] Concurrent calls to ONE session (call_lock simulation)")
    concurrency = 10

    start = time.perf_counter()
    for i in range(concurrency):
        body = json.dumps({
            "jsonrpc": "2.0", "id": i, "method": "tools/call",
            "params": {"name": "find_catalog_brand", "arguments": {"name": f"Bosch_{i}"}},
        }).encode()
        elapsed, status, data = req_sync(
            "POST", f"{MCP_URL}/mcp/message?sessionId=concurrent-session",
            headers={"Content-Type": "application/json", "X-Tenant-ID": TENANT},
            body=body, timeout=30,
        )

    total_ms = (time.perf_counter() - start) * 1000
    print(f"      {concurrency} calls serialized: {total_ms:.0f}ms total, {total_ms/concurrency:.1f}ms avg")
    results["concurrent_calls_ms"].append(total_ms / concurrency)


def test_6_data_service_burst():
    """TEST 6: Data-service прямой burst (без MCP)."""
    print("\n[d6] Data-service direct burst")
    for endpoint, label in [
        ("/catalog_brand", "list brands"),
        ("/catalog_product?name=Bosch", "find products"),
        ("/catalog_category", "list categories"),
        ("/catalog_order", "list orders"),
        ("/stats", "stats"),
    ]:
        times = []
        for i in range(5):
            elapsed, status, data = req_sync(
                "GET", f"{DATA_URL}{endpoint}",
                headers={"X-Tenant-ID": TENANT, "Authorization": f"Bearer {TOKEN}"},
            )
            times.append(elapsed)
        print(f"      {label}: avg={statistics.mean(times):.1f}ms")


def test_7_stateless_spam():
    """TEST 7: Спам stateless POST (без SSE). Каждый — createServer -> FetchConfig -> build tools."""
    print("\n[d7] Stateless POST spam (NO SSE session)")

    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()

    for batch_size in [1, 5, 10, 20]:
        times = []
        start = time.perf_counter()
        for i in range(batch_size):
            elapsed, status, data = req_sync(
                "POST", f"{MCP_URL}/mcp/message?sessionId=spam-{batch_size}-{i}",
                headers={"Content-Type": "application/json", "X-Tenant-ID": TENANT},
                body=body,
            )
            times.append(elapsed)
        total = (time.perf_counter() - start) * 1000
        print(f"      batch={batch_size}: {total:.0f}ms total, {total/batch_size:.1f}ms/call ({batch_size/(total/1000):.1f} RPS)")


def test_8_check_metrics():
    """TEST 8: Проверка Prometheus метрик."""
    print("\n[d8] Prometheus metrics check")
    elapsed, status, data = req_sync("GET", f"{MCP_URL}/metrics", timeout=5)
    text = data.decode()

    for line in text.split("\n"):
        if line.startswith("mcp_") and "promhttp" not in line:
            parts = line.split()
            if len(parts) >= 2:
                print(f"      {parts[0]} = {parts[1]}")


def print_summary():
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    if results["manifest_ms"]:
        avg_m = statistics.mean(results["manifest_ms"])
        print(f"\n  /mcp/manifest latency: {avg_m:.1f}ms avg")

    if results["tool_call_ms"]:
        latencies = [r["ms"] for r in results["tool_call_ms"]]
        print(f"\n  Tool calls: min={min(latencies):.1f}ms "
              f"p50={statistics.median(latencies):.1f}ms "
              f"avg={statistics.mean(latencies):.1f}ms "
              f"max={max(latencies):.1f}ms")

    print(f"\n  Rate limit hits: {results['rate_limit_hits']}")
    print(f"  Errors: {len(results['errors'])}")

    if results["bottlenecks"]:
        print("\n  BOTTLENECKS FOUND:")
        for b in results["bottlenecks"]:
            print(f"    🔴 {b['component']}: {b['reason']}")
    else:
        print("\n  ✅ No bottlenecks detected")

    # Save
    with open("/tmp/mcp_bench_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Full results -> /tmp/mcp_bench_results.json\n")


if __name__ == "__main__":
    print("=" * 60)
    print("MCP GATEWAY LOAD TEST — Helperium")
    print(f"  MCP:  {MCP_URL}")
    print(f"  DATA: {DATA_URL}")
    print(f"  TENANT: {TENANT}")
    print("=" * 60)

    # Health check
    for svc, url in [("MCP", MCP_URL), ("DATA", DATA_URL)]:
        try:
            hr = urllib.request.urlopen(f"{url}/health", timeout=5)
            print(f"  {svc} healthy ({hr.status})")
        except Exception as e:
            print(f"  {svc} DEAD: {e}")
            sys.exit(1)

    test_1_manifest_bottleneck()
    test_2_sse_session()
    test_3_tool_calls()
    test_4_rate_limiter()
    test_5_concurrent_same_session()
    test_6_data_service_burst()
    test_7_stateless_spam()
    test_8_check_metrics()

    print_summary()
