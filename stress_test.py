import threading
import requests

# =============================================
# CONFIGURATION
# =============================================
BASE_URL = "http://127.0.0.1:8000"
NUM_USERS = 10       # 10 concurrent users
PRODUCT_STOCK = 5    # only 5 items in stock
                     # so only 5 users should succeed

# =============================================
# STEP 1: Setup — create store owner + store + product
# =============================================
def setup_test_data():
    print("=== SETTING UP TEST DATA ===\n")

    # 1. Register store owner
    res = requests.post(f"{BASE_URL}/api/users/register/", json={
        "username": "storeowner_test",
        "email": "owner@test.com",
        "password": "Test1234!",
        "role": "STORE_OWNER"
    })
    print(f"Store owner register: {res.status_code}")

    # 2. Login as store owner
    res = requests.post(f"{BASE_URL}/api/users/login/", json={
        "username": "storeowner_test",
        "password": "Test1234!"
    })
    owner_token = res.json().get("access")
    if not owner_token:
        print(f"❌ Could not login as store owner: {res.json()}")
        return None, None
    print("✅ Store owner logged in")

    headers = {"Authorization": f"Bearer {owner_token}"}

    # 3. Create a store
    res = requests.post(f"{BASE_URL}/api/stores/", headers=headers, json={
        "name": "Stress Test Store",
        "description": "Store for stress testing"
    })
    store_id = res.json().get("id")
    if not store_id:
        print(f"❌ Could not create store: {res.json()}")
        return None, None
    print(f"✅ Store created → id={store_id}")

    # 4. Create a product with limited stock
    res = requests.post(
        f"{BASE_URL}/api/stores/{store_id}/products/",
        headers=headers,
        json={
            "name": "Limited Product",
            "description": "Only 5 in stock",
            "price": "10.00",
            "stock": PRODUCT_STOCK
        }
    )
    product_id = res.json().get("id")
    if not product_id:
        print(f"❌ Could not create product: {res.json()}")
        return None, None
    print(f"✅ Product created → id={product_id}, stock={PRODUCT_STOCK}\n")

    return store_id, product_id


# =============================================
# STEP 2: Register customers + add to cart
# =============================================
def setup_customer(user_num, product_id):
    """
    Register a customer, cart is auto-created by User.save()
    Then add the product to their cart
    Returns their token
    """
    username = f"customer_test{user_num}"

    # 1. Register → cart auto-created
    res = requests.post(f"{BASE_URL}/api/users/register/", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "Test1234!",
        "role": "CUSTOMER"
    })
    if res.status_code != 201:
        print(f"❌ Could not register customer {user_num}: {res.json()}")
        return None

    # 2. Login → get token
    res = requests.post(f"{BASE_URL}/api/users/login/", json={
        "username": username,
        "password": "Test1234!"
    })
    token = res.json().get("access")
    if not token:
        print(f"❌ Could not login customer {user_num}: {res.json()}")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Add product to cart
    # Cart is auto-linked to user, so URL is just /api/cart/items/
    res = requests.post(
        f"{BASE_URL}/api/cart/items/",
        headers=headers,
        json={
            "product": product_id,
            "quantity": 3
        }
    )
    if res.status_code not in [200, 201]:
        print(f"❌ Could not add to cart for customer {user_num}: {res.json()}")
        return None

    return token


# =============================================
# STEP 3: Concurrent order placement
# =============================================
results = []
results_lock = threading.Lock()  # to safely append to results list

def place_order(token, user_id):
    """Each thread calls this — places an order"""
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        f"{BASE_URL}/api/orders/",
        headers=headers,
        json={}
    )

    # Lock before writing to shared results list
    with results_lock:
        results.append({
            "user_id": user_id,
            "status_code": response.status_code,
            "response": response.json()
        })
        print(f"User {user_id:02d} → Status: {response.status_code} | {response.json()}")


# =============================================
# MAIN
# =============================================
if __name__ == "__main__":

    # 1. Setup store and product
    store_id, product_id = setup_test_data()
    if not product_id:
        print("❌ Setup failed. Exiting.")
        exit()

    # 2. Register all customers and add product to their carts
    print("=== SETTING UP CUSTOMERS ===\n")
    tokens = []
    for i in range(1, NUM_USERS + 1):
        token = setup_customer(i, product_id)
        if token:
            tokens.append((token, i))
            print(f"✅ Customer {i} ready")
        else:
            print(f"❌ Customer {i} failed setup")

    print(f"\n=== LAUNCHING {len(tokens)} CONCURRENT ORDERS ===")
    print(f"📦 Product stock = {PRODUCT_STOCK}")
    print(f"👥 Users trying to order = {len(tokens)}")
    print(f"Expected: only {PRODUCT_STOCK} should succeed\n")

    # 3. Create all threads
    threads = []
    for token, user_id in tokens:
        t = threading.Thread(target=place_order, args=(token, user_id))
        threads.append(t)

    # 4. Start ALL threads at the exact same time
    for t in threads:
        t.start()

    # 5. Wait for ALL threads to finish
    for t in threads:
        t.join()

    # =============================================
    # RESULTS SUMMARY
    # =============================================
    print("\n" + "="*50)
    print("RESULTS SUMMARY")
    print("="*50)

    success = [r for r in results if r['status_code'] == 201]
    failed  = [r for r in results if r['status_code'] != 201]

    print(f"✅ Successful orders : {len(success)}")
    print(f"❌ Blocked/failed    : {len(failed)}")
    print(f"📦 Original stock    : {PRODUCT_STOCK}")
    print()

    if len(success) <= PRODUCT_STOCK:
        print("🎉 RACE CONDITION HANDLED CORRECTLY!")
        print(f"   Stock was never oversold ({len(success)} ≤ {PRODUCT_STOCK})")
    else:
        print("⚠️  RACE CONDITION DETECTED!")
        print(f"   More orders ({len(success)}) than stock ({PRODUCT_STOCK})!")