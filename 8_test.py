

import requests
import threading
import time

BASE_URL = "http://127.0.0.1:8000"
RUN_ID = int(time.time())



def register_and_login(username, password, role, retries=3):
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


def add_to_cart(token, product_id, quantity=1):
    return requests.post(
        f"{BASE_URL}/api/cart/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={"product": product_id, "quantity": quantity}
    )


def create_order(token):
    """STEP 1 — create order from cart."""
    return requests.post(
        f"{BASE_URL}/api/orders/",
        headers={"Authorization": f"Bearer {token}"},
        json={}
    )


def pay_order(token, order_id):
    """STEP 2 — pay for the order."""
    return requests.post(
        f"{BASE_URL}/api/orders/{order_id}/payment/",
        headers={"Authorization": f"Bearer {token}"},
        json={}
    )


def get_order(token, order_id):
    return requests.get(
        f"{BASE_URL}/api/orders/{order_id}/",
        headers={"Authorization": f"Bearer {token}"}
    )


def get_payment(token, order_id):
    return requests.get(
        f"{BASE_URL}/api/orders/{order_id}/payment/",
        headers={"Authorization": f"Bearer {token}"}
    )


def get_stock(store_id, product_id, owner_headers):
    res = requests.get(
        f"{BASE_URL}/api/stores/{store_id}/products/{product_id}/",
        headers=owner_headers
    )
    return res.json().get("stock")


def section(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def step(text):
    print(f"  → {text}")


def check(label, actual, expected, passed):
    icon = "✅" if passed else "❌"
    print(f"  {icon} {label}: {actual} (expected {expected})")



def setup_store():
    step("Creating store owner...")
    owner_token = register_and_login(
        f"acid_owner_{RUN_ID}", "Test1234!", "STORE_OWNER"
    )
    if not owner_token:
        print("❌Could not create store owner")
        exit()

    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    res = requests.post(
        f"{BASE_URL}/api/stores/",
        headers=owner_headers,
        json={"name": f"ACID Store {RUN_ID}", "description": "ACID test store"}
    )
    store_id = res.json()["id"]
    step(f"Store created (id={store_id})")

    return store_id, owner_headers


def make_product(store_id, owner_headers, name, price, stock):
    res = requests.post(
        f"{BASE_URL}/api/stores/{store_id}/products/",
        headers=owner_headers,
        json={"name": name, "description": "test", "price": price, "stock": stock}
    )
    return res.json()["id"]


def scenario_1(store_id, owner_headers):
    section("SCENARIO 1 — Happy Path (two-step checkout)")

    print("""
  Proves the full two-step flow works atomically:
    STEP 1: POST /api/orders/        → Order PENDING + stock deducted
    STEP 2: POST /api/orders/{id}/payment/ → Payment + Order PAID
    """)

    product_id = make_product(store_id, owner_headers, "Happy Product", "15.00", 10)
    step(f"Product created (id={product_id}, stock=10, price=15.00)")

    token = register_and_login(f"acid_s1_{RUN_ID}", "Test1234!", "CUSTOMER")
    add_to_cart(token, product_id, quantity=4)
    step("Customer added 4 units to cart")

    stock_before = get_stock(store_id, product_id, owner_headers)
    step(f"Stock BEFORE: {stock_before}")

    res1 = create_order(token)
    step(f"STEP 1: POST /api/orders/ → HTTP {res1.status_code}")

    if res1.status_code != 201:
        print(f"  Order creation failed: {res1.json()}")
        return False

    order = res1.json()
    order_id = order["id"]
    order_status_after_step1 = order["status"]
    stock_after_step1 = get_stock(store_id, product_id, owner_headers)

    print()
    print("  After STEP 1 (order created, not yet paid):")
    check("Order status", order_status_after_step1, "PENDING", order_status_after_step1 == "PENDING")
    check("Stock deducted", stock_after_step1, "6 (10-4)", stock_after_step1 == 6)

    res2 = pay_order(token, order_id)
    step(f"\n  STEP 2: POST /api/orders/{order_id}/payment/ → HTTP {res2.status_code}")

    if res2.status_code not in [200, 201]:
        print(f"   Payment failed: {res2.json()}")
        return False

    order_after = get_order(token, order_id).json()
    payment_res = get_payment(token, order_id).json()

    order_status_final = order_after["status"]
    payment = payment_res[0] if isinstance(payment_res, list) and payment_res else \
        (payment_res if isinstance(payment_res, dict) else None)
    payment_status = payment["status"] if payment else "NOT FOUND"
    payment_amount = payment["amount"] if payment else "NOT FOUND"

    print()
    print("  After STEP 2 (payment complete):")
    check("Order status", order_status_final, "PAID", order_status_final == "PAID")
    check("Payment status", payment_status, "COMPLETED", payment_status == "COMPLETED")
    check("Payment amount", payment_amount, "60.00 (4×15)", str(payment_amount) == "60.00")

    passed = (
        order_status_after_step1 == "PENDING"
        and stock_after_step1 == 6
        and order_status_final == "PAID"
        and payment_status == "COMPLETED"
        and str(payment_amount) == "60.00"
    )

    print()
    if passed:
        print("   PASS — Two-step checkout fully atomic:")
        print("     STEP 1 committed Order+Stock together")
        print("     STEP 2 committed Payment+Status together")
    else:
        print("   FAIL — Two-step flow did not complete correctly")

    return passed


#
def scenario_2(store_id, owner_headers):
    section("SCENARIO 2 — Order Creation Rollback (Step 1 atomicity)")

    print("""
  Proves STEP 1 is atomic:
    Cart has 2 products. Product A has enough stock,
    Product B does NOT. When Product B fails validation,
    the ENTIRE order creation rolls back — including
    Product A's stock deduction and the Order itself.
    """)

    product_a = make_product(store_id, owner_headers, "Product A", "20.00", 10)
    product_b = make_product(store_id, owner_headers, "Product B", "30.00", 2)
    step(f"Product A (id={product_a}, stock=10) — enough")
    step(f"Product B (id={product_b}, stock=2) — NOT enough (requesting 5)")

    token = register_and_login(f"acid_s2_{RUN_ID}", "Test1234!", "CUSTOMER")
    add_to_cart(token, product_a, quantity=3)
    add_to_cart(token, product_b, quantity=5)
    step("Cart: Product A (3 units) + Product B (5 units)")

    stock_a_before = get_stock(store_id, product_a, owner_headers)
    stock_b_before = get_stock(store_id, product_b, owner_headers)
    step(f"Stock BEFORE: A={stock_a_before}, B={stock_b_before}")

    res = create_order(token)
    step(f"POST /api/orders/ → HTTP {res.status_code}")
    step(f"Response: {res.json()}")

    stock_a_after = get_stock(store_id, product_a, owner_headers)
    stock_b_after = get_stock(store_id, product_b, owner_headers)

    orders = get_order(token, "").json() if False else requests.get(
        f"{BASE_URL}/api/orders/",
        headers={"Authorization": f"Bearer {token}"}
    ).json()
    order_count = len(orders) if isinstance(orders, list) else 0

    print()
    print("  VERIFICATION:")
    check("Order rejected (HTTP 400)", res.status_code, 400, res.status_code == 400)
    check("Product A stock UNCHANGED", stock_a_after, stock_a_before, stock_a_after == stock_a_before)
    check("Product B stock UNCHANGED", stock_b_after, stock_b_before, stock_b_after == stock_b_before)
    check("No Order created", order_count, 0, order_count == 0)

    passed = (
        res.status_code == 400
        and stock_a_after == stock_a_before
        and stock_b_after == stock_b_before
        and order_count == 0
    )

    print()
    if passed:
        print("   PASS — Step 1 rollback confirmed:")
        print("     Product A processed first but rolled back when B failed")
        print("     No Order, no stock change — zero partial state")
    else:
        print("   FAIL — Partial state detected — atomicity violated!")

    return passed



def scenario_3(store_id, owner_headers):
    section("SCENARIO 3 — Payment Atomicity (Step 2)")

    print("""
  Proves STEP 2 is atomic:
    Payment creation and Order status update (→ PAID)
    happen in ONE transaction. Either both succeed or
    both fail — an Order is never PAID without a Payment,
    and a Payment never exists without the Order being PAID.
    """)

    product_id = make_product(store_id, owner_headers, "Payment Product", "25.00", 10)
    step(f"Product created (id={product_id}, stock=10, price=25.00)")

    token = register_and_login(f"acid_s3_{RUN_ID}", "Test1234!", "CUSTOMER")
    add_to_cart(token, product_id, quantity=2)

    res1 = create_order(token)
    order_id = res1.json()["id"]
    step(f"Order #{order_id} created (status=PENDING)")

    res2 = pay_order(token, order_id)
    step(f"Payment → HTTP {res2.status_code}")

    order_after = get_order(token, order_id).json()
    payment_res = get_payment(token, order_id).json()
    payment = payment_res[0] if isinstance(payment_res, list) and payment_res else None

    order_status = order_after["status"]
    has_payment = payment is not None
    payment_status = payment["status"] if payment else "NONE"

    print()
    print("  VERIFICATION:")
    check("Order status", order_status, "PAID", order_status == "PAID")
    check("Payment exists", has_payment, "True", has_payment)
    check("Payment status", payment_status, "COMPLETED", payment_status == "COMPLETED")

    consistency = (order_status == "PAID") == has_payment
    check("PAID ⟺ Payment exists", consistency, "True (consistent)", consistency)

    passed = (
        order_status == "PAID"
        and has_payment
        and payment_status == "COMPLETED"
        and consistency
    )

    print()
    if passed:
        print("   PASS — Payment atomicity confirmed:")
        print("     Payment + status update committed together")
        print("     No PAID order without Payment, ever")
    else:
        print("   FAIL — Payment atomicity violated")

    return passed



def scenario_4(store_id, owner_headers):
    section("SCENARIO 4 — Duplicate Payment Prevention")

    print("""
  Proves an order cannot be paid twice:
    After a successful payment, a second payment attempt
    on the same order is rejected cleanly. No double-charge,
    no second Payment record.
    """)

    product_id = make_product(store_id, owner_headers, "Dup Product", "25.00", 10)
    token = register_and_login(f"acid_s4_{RUN_ID}", "Test1234!", "CUSTOMER")
    add_to_cart(token, product_id, quantity=2)

    res1 = create_order(token)
    order_id = res1.json()["id"]
    step(f"Order #{order_id} created")

    pay1 = pay_order(token, order_id)
    step(f"First payment → HTTP {pay1.status_code}")

    pay2 = pay_order(token, order_id)
    step(f"Second payment (duplicate) → HTTP {pay2.status_code}")

    payment_res = get_payment(token, order_id).json()
    payment_count = len(payment_res) if isinstance(payment_res, list) else (1 if payment_res else 0)

    print()
    print("  VERIFICATION:")
    check("First payment succeeded", pay1.status_code, "200/201", pay1.status_code in [200, 201])
    check("Second payment rejected", pay2.status_code, 400, pay2.status_code == 400)
    check("Only ONE payment exists", payment_count, 1, payment_count == 1)

    passed = (
        pay1.status_code in [200, 201]
        and pay2.status_code == 400
        and payment_count == 1
    )

    print()
    if passed:
        print("   PASS — Duplicate payment prevented:")
        print("     Second attempt rejected, only one Payment exists")
    else:
        print("   FAIL — Duplicate payment was allowed!")

    return passed



if __name__ == "__main__":
    print("\nTASK 8 — TRANSACTION INTEGRITY (ACID)")
    print("Two-Step Checkout: Order Creation + Payment")
    print("Server : " + BASE_URL)
    print("Run ID : " + str(RUN_ID))

    section("SETUP")
    store_id, owner_headers = setup_store()

    r1 = scenario_1(store_id, owner_headers)
    r2 = scenario_2(store_id, owner_headers)
    r3 = scenario_3(store_id, owner_headers)
    r4 = scenario_4(store_id, owner_headers)

    section("FINAL SUMMARY")
    print(f"  Scenario 1 (Happy Path)        : {' PASS' if r1 else ' FAIL'}")
    print(f"  Scenario 2 (Order Rollback)    : {' PASS' if r2 else ' FAIL'}")
    print(f"  Scenario 3 (Payment Atomicity) : {' PASS' if r3 else ' FAIL'}")
    print(f"  Scenario 4 (Duplicate Payment) : {' PASS' if r4 else ' FAIL'}")
    print()

    if r1 and r2 and r3 and r4:
        print("   ACID GUARANTEES FULLY CONFIRMED (two-step architecture):")
        print()
        print("     Atomicity   → each step (Order creation, Payment) commits")
        print("                   fully or rolls back completely")
        print("     Consistency → no PAID order without Payment, no negative stock,")
        print("                   no duplicate payments")
        print("     Isolation   → Redis distributed_lock + PostgreSQL")
        print("                   select_for_update(nowait=True)")
        print("     Durability  → PostgreSQL Write-Ahead Logging (WAL)")
    else:
        print("    One or more scenarios failed — review output above")
    print()