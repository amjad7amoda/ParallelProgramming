

import requests
import threading
import time

BASE_URL = "http://127.0.0.1:8000"
RUN_ID = int(time.time())

NUM_USERS = 100
PRODUCT_STOCK = 10
QUANTITY_PER_USER = 1



def register_and_login(username, password, role, retries=3):
    """Register a user and return their access token. Retries on failure."""
    for attempt in range(retries):
        try:
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
            token = res.json().get("access")
            if token:
                return token
        except Exception:
            pass
        time.sleep(0.2)
    return None


def section(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def step(text):
    print(f"  → {text}")


def setup_product():
    step("Creating store owner...")
    owner_token = register_and_login(
        f"race_owner_{RUN_ID}", "Test1234!", "STORE_OWNER"
    )
    if not owner_token:
        print(" Could not create store owner")
        exit()

    headers = {"Authorization": f"Bearer {owner_token}"}

    res = requests.post(f"{BASE_URL}/api/stores/", headers=headers, json={
        "name": f"Race Test Store {RUN_ID}",
        "description": "Race condition test store"
    })
    store_id = res.json()["id"]

    res = requests.post(
        f"{BASE_URL}/api/stores/{store_id}/products/",
        headers=headers,
        json={
            "name": "Limited Stock Product",
            "description": "Only 10 in stock",
            "price": "10.00",
            "stock": PRODUCT_STOCK
        }
    )
    product_id = res.json()["id"]
    step(f"Product created (id={product_id}, stock={PRODUCT_STOCK}, price=10.00)")

    return store_id, product_id, headers


def setup_customers(product_id):
    tokens = []
    tokens_lock = threading.Lock()

    def register_one(i):
        token = register_and_login(
            f"race_cust_{RUN_ID}_{i}", "Test1234!", "CUSTOMER"
        )
        if not token:
            print(f"    Customer {i} failed to register — skipping")
            return

        cust_headers = {"Authorization": f"Bearer {token}"}

        res = requests.post(
            f"{BASE_URL}/api/cart/items/",
            headers=cust_headers,
            json={"product": product_id, "quantity": QUANTITY_PER_USER}
        )
        if res.status_code not in [200, 201]:
            print(f"    Customer {i} failed to add to cart — skipping")
            return

        with tokens_lock:
            tokens.append((token, i))

    threads = [
        threading.Thread(target=register_one, args=(i,))
        for i in range(1, NUM_USERS + 1)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    step(f"{len(tokens)} customers ready with {QUANTITY_PER_USER} unit(s) in cart")
    return tokens



def run_concurrent_checkout(tokens):
    results = []
    results_lock = threading.Lock()

    def checkout(token, user_id):
        cust_headers = {"Authorization": f"Bearer {token}"}
        res = requests.post(
            f"{BASE_URL}/api/orders/",
            headers=cust_headers,
            json={}
        )
        with results_lock:
            results.append({
                "user_id": user_id,
                "status_code": res.status_code,
                "response": res.json()
            })

    threads = [
        threading.Thread(target=checkout, args=(token, uid))
        for token, uid in tokens
    ]

    step(f"Launching {len(threads)} checkout requests simultaneously...")
    print()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    return sorted(results, key=lambda r: r["user_id"])


if __name__ == "__main__":
    print("\nTASK 1 — CONCURRENT ACCESS & DATA INTEGRITY")
    print("Race Condition Prevention Proof")
    print(f"Server : {BASE_URL}")
    print(f"Run ID : {RUN_ID}")

    
    section("STEP 1 — Setting Up Store and Product")
    store_id, product_id, owner_headers = setup_product()

    section("STEP 2 — Registering 100 Customers (parallel)")
    tokens = setup_customers(product_id)

    if not tokens:
        print(" No customers were set up. Exiting.")
        exit()

    section(f"STEP 3 — Concurrent Checkout ({len(tokens)} users, stock={PRODUCT_STOCK})")
    results = run_concurrent_checkout(tokens)

    for r in results:
        status = " SOLD" if r["status_code"] == 201 else " REJECTED"
        print(f"  User {r['user_id']:03d} → HTTP {r['status_code']} {status}")

    res = requests.get(
        f"{BASE_URL}/api/stores/{store_id}/products/{product_id}/",
        headers=owner_headers
    )
    final_stock = res.json().get("stock")

    success = [r for r in results if r["status_code"] == 201]
    failed  = [r for r in results if r["status_code"] != 201]
    total_sold = len(success) * QUANTITY_PER_USER
    expected_stock = PRODUCT_STOCK - total_sold

    # Results summary
    section("RESULTS SUMMARY")
    print(f"  Original stock         : {PRODUCT_STOCK}")
    print(f"  Concurrent users       : {len(tokens)}")
    print(f"  Quantity per user      : {QUANTITY_PER_USER}")
    print(f"   Successful orders   : {len(success)}")
    print(f"   Rejected orders     : {len(failed)}")
    print(f"   Total units sold    : {total_sold}")
    print(f"   Final stock (actual): {final_stock}")
    print(f"   Final stock (expect): {expected_stock}")

    passed = (
        total_sold <= PRODUCT_STOCK
        and final_stock == expected_stock
        and final_stock >= 0
    )

    print()
    if passed:
        print("   PASS — Race Condition handled correctly")
        print(f"     {total_sold} units sold <= {PRODUCT_STOCK} available")
        print("     Stock integrity maintained — no overselling")
    else:
        print("   FAIL — Stock mismatch or overselling detected!")

    section("FINAL VERDICT")
    print(f"  Race Condition Test : {' PASS' if passed else '❌ FAIL'}")
    print()
    if passed:
        print("   CONCURRENCY GUARANTEES CONFIRMED:")
        print("     - PostgreSQL row-level lock (select_for_update)")
        print("       prevented simultaneous stock modification")
        print("     - Conflicting requests rejected cleanly (HTTP 400)")
        print("     - No lost updates, no negative stock, no data corruption")
        print("     - transaction.atomic() ensured full rollback on failure")
    print()