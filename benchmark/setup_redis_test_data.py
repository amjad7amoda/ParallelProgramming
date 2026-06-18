"""
Setup script for Redis performance testing.
Creates test data: store owner, store, and products.
"""
import requests
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
CONTEXT_FILE = Path(__file__).parent.parent / "benchmark_context.json"

def setup_test_data():
    print("=== SETTING UP REDIS PERFORMANCE TEST DATA ===\n")
    
    # 1. Register store owner
    print("1. Registering store owner...")
    res = requests.post(f"{BASE_URL}/api/users/register/", json={
        "username": "redis_test_owner",
        "email": "redis_owner@test.com",
        "password": "RedisTest123!",
        "role": "STORE_OWNER"
    })
    if res.status_code == 201:
        print("✅ Store owner registered")
    else:
        print(f"⚠️  Store owner registration: {res.status_code} - {res.json()}")
    
    # 2. Login as store owner
    print("\n2. Logging in as store owner...")
    res = requests.post(f"{BASE_URL}/api/users/login/", json={
        "username": "redis_test_owner",
        "password": "RedisTest123!"
    })
    if res.status_code == 200:
        owner_token = res.json().get("access")
        print("✅ Store owner logged in")
    else:
        print(f"❌ Login failed: {res.json()}")
        return
    
    headers = {"Authorization": f"Bearer {owner_token}"}
    
    # 3. Create a store
    print("\n3. Creating store...")
    res = requests.post(f"{BASE_URL}/api/stores/", headers=headers, json={
        "name": "Redis Performance Test Store",
        "description": "Store for Redis caching performance testing"
    })
    if res.status_code == 201:
        store_id = res.json().get("id")
        print(f"✅ Store created → id={store_id}")
    else:
        print(f"❌ Store creation failed: {res.json()}")
        return
    
    # 4. Create multiple products for testing
    print("\n4. Creating products...")
    product_ids = []
    for i in range(1, 6):
        res = requests.post(
            f"{BASE_URL}/api/stores/{store_id}/products/",
            headers=headers,
            json={
                "name": f"Redis Test Product {i}",
                "description": f"Product {i} for Redis caching performance test",
                "price": f"{10.00 * i}.00",
                "stock": 100
            }
        )
        if res.status_code == 201:
            product_id = res.json().get("id")
            product_ids.append(product_id)
            print(f"✅ Product {i} created → id={product_id}")
        else:
            print(f"❌ Product {i} creation failed: {res.json()}")
    
    # 5. Save context for Locust tests
    context = {
        "store_id": store_id,
        "product_id": product_ids[0] if product_ids else 1,
        "all_product_ids": product_ids
    }
    
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context, f, indent=2)
    
    print(f"\n✅ Test data setup complete!")
    print(f"📝 Context saved to {CONTEXT_FILE}")
    print(f"🏪 Store ID: {store_id}")
    print(f"📦 Product IDs: {product_ids}")
    print(f"🎯 Primary Product ID: {context['product_id']}")

if __name__ == "__main__":
    try:
        setup_test_data()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the API. Make sure the server is running at http://127.0.0.1:8000")
    except Exception as e:
        print(f"❌ Error: {e}")
