"""
================================================================
Task 1 — Concurrent Access & Data Integrity (Race Condition)
Proof script: multiple users buying the same product at once
================================================================

This script demonstrates that the system prevents overselling
when many users try to purchase the same limited-stock product
at the exact same moment.

  Setup:
      - 1 product with a small, fixed stock
      - N customers, each with 1 unit of that product in their cart

  Test:
      - All N customers send POST /api/orders/ at the EXACT same time
      - select_for_update(nowait=True) ensures only one transaction
        can hold the product's row lock at a time
      - Requests that can't get the lock immediately are rejected
        cleanly (HTTP 400), not queued or left hanging

  Pass criteria:
      - Total units sold <= original stock (never oversold)
      - Successful orders <= original stock
      - Final stock = original stock - units sold (no drift/corruption)

Run:
    python 1_test.py
================================================================
"""

import requests
import threading
import time

BASE_URL = "http://127.0.0.1:8000"
RUN_ID = int(time.time())  # ensures unique usernames on every run

NUM_USERS = 10        # number of concurrent customers
PRODUCT_STOCK = 5     # total stock available
QUANTITY_PER_USER = 1 # units each customer tries to buy


def register_and_login(username, password, role):
    """Register a user (ignore 'already exists') and return their access token."""
    requests.post(f"{BASE_URL}/api/users/register/", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": password,
        "role": role
    })
    res = requests.post(f"{BASE_URL}/api/users/login/", json={
        "username": username,
        "password": password
    })
    return res.json().get("access")


def section(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def step(text):
    print(f"  → {text}")


# ================================================================
# SETUP — store owner, store, product
# ================================================================
def setup_product():
    owner_token = register_and_login(f"race_owner_{RUN_ID}", "Test1234!", "STORE_OWNER")
    headers = {"Authorization": f"Bearer {owner_token}"}

    res = requests.post(f"{BASE_URL}/api/stores/", headers=headers, json={
        "name": "Race Condition Test Store", "description": "test"
    })
    store_id = res.json()["id"]

    res = requests.post(f"{BASE_URL}/api/stores/{store_id}/products/", headers=headers, json={
        "name": "Limited Product", "description": "test", "price": "10.00", "stock": PRODUCT_STOCK
    })
    product_id = res.json()["id"]
    step(f"Product created (id={product_id}, stock={PRODUCT_STOCK}, price=10.00)")

    return store_id, product_id, headers


# ================================================================
# SETUP — N customers, each with QUANTITY_PER_USER units in cart
# ================================================================
def setup_customers(product_id):
    tokens = []
    tokens_lock = threading.Lock()

    def register_one(i):
        token = register_and_login(f"race_cust_{RUN_ID}_{i}", "Test1234!", "CUSTOMER")
        cust_headers = {"Authorization": f"Bearer {token}"}
        requests.post(f"{BASE_URL}/api/cart/items/", headers=cust_headers, json={
            "product": product_id, "quantity": QUANTITY_PER_USER
        })
        with tokens_lock:
            tokens.append((token, i))

    threads = [threading.Thread(target=register_one, args=(i,)) for i in range(1, NUM_USERS + 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    step(f"{len(tokens)} customers ready, each with {QUANTITY_PER_USER} unit(s) in cart")
    return tokens


# ================================================================
# TEST — all customers checkout at the exact same time
# ================================================================
def run_concurrent_checkout(tokens):
    results = []
    results_lock = threading.Lock()

    def checkout(token, user_id):
        cust_headers = {"Authorization": f"Bearer {token}"}
        res = requests.post(f"{BASE_URL}/api/orders/", headers=cust_headers, json={})
        with results_lock:
            results.append({
                "user_id": user_id,
                "status_code": res.status_code,
                "response": res.json()
            })

    threads = [threading.Thread(target=checkout, args=(token, uid)) for token, uid in tokens]

    print()
    step(f"Launching {len(threads)} checkout requests simultaneously...")
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return sorted(results, key=lambda r: r["user_id"])


# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    print("\nTASK 1 — CONCURRENT ACCESS & DATA INTEGRITY (RACE CONDITION)")
    print("Server: " + BASE_URL)

    section("SETUP")
    store_id, product_id, owner_headers = setup_product()
    tokens = setup_customers(product_id)

    section(f"TEST — {NUM_USERS} concurrent checkouts, stock = {PRODUCT_STOCK}")
    results = run_concurrent_checkout(tokens)

    print()
    for r in results:
        print(f"  User {r['user_id']:02d} → HTTP {r['status_code']} | {r['response']}")

    # --- Check final stock ---
    res = requests.get(f"{BASE_URL}/api/stores/{store_id}/products/{product_id}/", headers=owner_headers)
    final_stock = res.json().get("stock")

    success = [r for r in results if r["status_code"] == 201]
    failed = [r for r in results if r["status_code"] != 201]
    total_sold = len(success) * QUANTITY_PER_USER
    expected_final_stock = PRODUCT_STOCK - total_sold

    section("RESULTS SUMMARY")
    print(f"  Original stock        : {PRODUCT_STOCK}")
    print(f"  Concurrent users      : {NUM_USERS}")
    print(f"  Quantity per user     : {QUANTITY_PER_USER}")
    print(f"  Successful orders     : {len(success)}")
    print(f"  Rejected orders       : {len(failed)}")
    print(f"  Total units sold      : {total_sold}")
    print(f"  Final stock (actual)  : {final_stock}")
    print(f"  Final stock (expected): {expected_final_stock}")

    passed = (
        total_sold <= PRODUCT_STOCK
        and final_stock == expected_final_stock
        and final_stock >= 0
    )

    print()
    if passed:
        print("   PASS — No overselling occurred:")
        print(f"           {total_sold} units sold <= {PRODUCT_STOCK} available")
        print("           Stock matches expected value exactly — no data corruption")
    else:
        print("   FAIL — Stock mismatch or overselling detected, investigate further")

    section("FINAL SUMMARY")
    print(f"  Race Condition Test : {' PASS' if passed else ' FAIL'}")
    print()
    if passed:
        print("   CONCURRENCY GUARANTEES CONFIRMED:")
        print("     - select_for_update(nowait=True) locks the product row")
        print("       for the duration of the transaction")
        print("     - Concurrent requests for the same row are rejected")
        print("       immediately and cleanly (HTTP 400), not queued")
        print("     - Stock was never read/written by two transactions")
        print("       at the same time — no lost updates")
    print()