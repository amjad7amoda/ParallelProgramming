"""
Test product endpoint performance with/without Redis caching.
Measures response times for list, detail, and counter endpoints.
"""
import argparse
import sys
import time
import requests
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
CONTEXT_FILE = Path(__file__).parent.parent / "benchmark_context.json"


def login_user(username, password):
    r = requests.post(f"{BASE_URL}/api/users/login/",
                      json={"username": username, "password": password})
    if r.status_code == 200:
        return r.json().get("access")
    return None


def register_user(username, password, role):
    r = requests.post(f"{BASE_URL}/api/users/register/", json={
        "username": username, "email": f"{username}@test.com",
        "password": password, "role": role
    }, timeout=5)
    return r.status_code in (200, 201)


def get_or_create_user(username, password, role):
    token = login_user(username, password)
    if token:
        return token
    register_user(username, password, role)
    return login_user(username, password)


def find_or_create_data():
    ctx = {}
    if CONTEXT_FILE.exists():
        try:
            ctx = json.loads(CONTEXT_FILE.read_text())
            if ctx.get("store_id") and ctx.get("product_ids"):
                r = requests.get(f"{BASE_URL}/api/stores/{ctx['store_id']}/", timeout=5)
                if r.status_code == 200:
                    print(f"  Reusing existing data: Store {ctx['store_id']}, Product {ctx['product_id']}")
                    return ctx
        except Exception:
            pass

    print("  Creating test data...")

    token = get_or_create_user("cache_owner", "CacheTest123!", "STORE_OWNER")
    if not token:
        print("  ERROR: Could not get store owner token")
        return {}

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(f"{BASE_URL}/api/stores/", headers=headers,
                      json={"name": "Cache Test Store", "description": "Store for cache testing"}, timeout=5)
    if r.status_code == 201:
        store_id = r.json().get("id")
    else:
        print(f"  Store creation: {r.status_code} {r.text[:100]}")
        return {}

    product_ids = []
    for i in range(1, 4):
        payload = {"name": f"Cache Test Product {i}", "description": f"Product {i}",
                   "price": str(10.00 * i), "stock": 100}
        r = requests.post(f"{BASE_URL}/api/stores/{store_id}/products/",
                          headers=headers, json=payload, timeout=5)
        if r.status_code == 201:
            pid = r.json().get("id")
            if pid:
                product_ids.append(pid)
        else:
            print(f"  Product {i} failed: {r.status_code} {r.text[:120]}")

    if not product_ids:
        print("  ERROR: No products created")
        return {}

    ctx = {"store_id": store_id, "product_id": product_ids[0],
           "product_ids": product_ids}
    CONTEXT_FILE.write_text(json.dumps(ctx, indent=2))
    print(f"  Store {store_id}, Products: {product_ids}")
    return ctx


def measure(label, fn, iterations=5):
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)
    avg = sum(times) / len(times)
    best = min(times)
    worst = max(times)
    print(f"  {label:45s}  avg={avg:8.2f}ms  best={best:8.2f}ms  worst={worst:8.2f}ms")
    return {"avg": round(avg, 2), "best": round(best, 2), "worst": round(worst, 2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["redis", "no-redis"], default="redis")
    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print(f"#  CACHE TEST — Mode: {args.mode}")
    print(f"{'#'*60}")

    try:
        requests.get(f"{BASE_URL}/api/stores/", timeout=5)
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect. Start the Django server first.")
        sys.exit(1)

    ctx = find_or_create_data()
    if not ctx.get("store_id"):
        print("ERROR: Failed to set up test data.")
        sys.exit(1)

    store_id = ctx["store_id"]
    pid = ctx["product_id"]

    token = get_or_create_user("cache_customer", "CacheTest123!", "CUSTOMER")
    if not token:
        print("ERROR: Could not get customer token")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    results = {}

    def g(url):
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r

    def p(url):
        r = requests.post(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r

    print("\n  --- Product List ---")
    results["list_cold"] = measure("list (cold, first hit)",
        lambda: g(f"{BASE_URL}/api/stores/{store_id}/products/"), iterations=3)
    results["list_warm"] = measure("list (warm, cached)",
        lambda: g(f"{BASE_URL}/api/stores/{store_id}/products/"), iterations=15)

    print("\n  --- Product Detail ---")
    results["detail_cold"] = measure("detail (cold, first hit)",
        lambda: g(f"{BASE_URL}/api/stores/{store_id}/products/{pid}/"), iterations=3)
    results["detail_warm"] = measure("detail (warm, cached)",
        lambda: g(f"{BASE_URL}/api/stores/{store_id}/products/{pid}/"), iterations=15)

    print("\n  --- Counters ---")
    results["increment_view"] = measure("increment_view",
        lambda: p(f"{BASE_URL}/api/stores/{store_id}/products/{pid}/increment_view/"),
        iterations=15)
    results["increment_like"] = measure("increment_like",
        lambda: p(f"{BASE_URL}/api/stores/{store_id}/products/{pid}/increment_like/"),
        iterations=15)

    total_avg = sum(r["avg"] for r in results.values())
    count = len(results)
    overall_avg = total_avg / count

    print(f"\n{'='*60}")
    print(f"  SUMMARY — Mode: {args.mode}")
    print(f"{'='*60}")
    print(f"  {'Test':30s} {'Avg(ms)':>8s} {'Best(ms)':>8s} {'Worst(ms)':>8s}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8}")
    for name, d in results.items():
        print(f"  {name:30s} {d['avg']:8.2f} {d['best']:8.2f} {d['worst']:8.2f}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8}")
    print(f"  {'OVERALL AVERAGE':30s} {overall_avg:8.2f}ms")
    print()

    return results


if __name__ == "__main__":
    main()
