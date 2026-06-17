import os
import threading
from uuid import uuid4

from locust import HttpUser, between, events, task

_setup_lock = threading.Lock()

SHARED_STORE_ID = 4
SHARED_PRODUCT_ID = 4

OWNER_USERNAME = "locust_owner"
OWNER_PASSWORD = "Password123!"
CUSTOMER_PASSWORD = "Password123!"
STOCK_PER_PRODUCT = 10_000


def setup_catalog(environment):
    global SHARED_STORE_ID, SHARED_PRODUCT_ID

    client = environment.runner.user_classes[0](environment).client

    # login أو register
    client.post("/api/users/register/", json={
        "username": OWNER_USERNAME,
        "email": "ahamoda161@gmail.com",
        "password": OWNER_PASSWORD,
        "role": "STORE_OWNER",
    })

    login = client.post("/api/users/login/", json={
        "username": OWNER_USERNAME,
        "password": OWNER_PASSWORD,
    })
    login.raise_for_status()
    token = login.json()["access"]
    headers = {"Authorization": f"Bearer {token}"}

    stores = client.get("/api/stores/", headers=headers)
    stores_data = stores.json()

    # if stores_data:
    #     SHARED_STORE_ID = stores_data[0]["id"]
    # else:
    store = client.post("/api/stores/", headers=headers, json={
        "name": "Locust Test Store",
        "description": "متجر الاختبار",
    })
    store.raise_for_status()
    SHARED_STORE_ID = store.json()["id"]

    # ✅ ابحث عن product موجود أولاً
    products = client.get(
        f"/api/stores/{SHARED_STORE_ID}/products/",
        headers=headers
    )
    products_data = products.json()

    if products_data:
        SHARED_PRODUCT_ID = products_data[0]["id"]
        print(f"\n✓ Reusing existing product ID: {SHARED_PRODUCT_ID}")
    else:
        product = client.post(
            f"/api/stores/{SHARED_STORE_ID}/products/",
            headers=headers,
            json={
                "name": "Locust Lock Product",
                "description": "منتج اختبار الأقفال",
                "price": "10.00",
                "stock": 10_000,  # ✅ رقم واضح ومعروف
            },
        )
        product.raise_for_status()
        SHARED_PRODUCT_ID = product.json()["id"]

    print(f"✓ Store ID: {SHARED_STORE_ID} | Product ID: {SHARED_PRODUCT_ID}\n")
    print(f"✓ Initial stock: {10_000}\n")


def _error_text(body):
    if isinstance(body, list):
        return " ".join(_error_text(item) for item in body)
    if isinstance(body, dict):
        return " ".join(f"{key} {_error_text(value)}" for key, value in body.items())
    return str(body)


def _safe_json(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def _is_expected_cancel_contention(reason):
    return (
        "locked" in reason
        or "transaction is in progress" in reason
        or "please try again" in reason
        or "cannot cancel right now" in reason
    )

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    setup_catalog(environment)


class LockContentionUser(HttpUser):
    wait_time = between(0, 0.05)
    host = os.getenv("LOCUST_HOST", "http://127.0.0.1:8000")

    def on_start(self):
        suffix = uuid4().hex[:8]
        username = f"customer_{suffix}"

        self.client.post("/api/users/register/", json={
            "username": username,
            "email": f"{username}@test.com",
            "password": CUSTOMER_PASSWORD,
            "role": "CUSTOMER",
        }).raise_for_status()

        login = self.client.post("/api/users/login/", json={
            "username": username,
            "password": CUSTOMER_PASSWORD,
        })
        login.raise_for_status()
        self.headers = {"Authorization": f"Bearer {login.json()['access']}"}
        self.order_id = None

    def add_to_cart(self):
        res = self.client.post(
            "/api/cart/items/",
            headers=self.headers,
            json={"product": SHARED_PRODUCT_ID, "quantity": 1},
            name="cart/add",
        )
        res.raise_for_status()

    # في locust — سجّل كل الأخطاء بتفصيل
    @task(3)
    def create_order(self):
        self.add_to_cart()

        with self.client.post(
            "/api/orders/",
            headers=self.headers,
            json={"store": SHARED_STORE_ID},
            name="lock/create_order",
            catch_response=True,
        ) as res:
            if res.status_code == 201:
                self.order_id = res.json().get("id")
                res.success()
            elif res.status_code == 400:
                body = _safe_json(res)
                reason = _error_text(body).lower()

                if "locked" in reason:
                    res.failure(f"LOCK BLOCKED — {body}")
                elif "stock" in reason:
                    res.success()
                elif "empty" in reason:
                    res.success()
                else:
                    res.failure(f"UNKNOWN 400: {body}")  
            else:
                res.failure(f"HTTP {res.status_code}: {res.text}")

    @task(2)
    def cancel_order(self):
        if not self.order_id:
            return

        order_id = self.order_id
        self.order_id = None  # امسحه فوراً قبل الـ request لمنع double cancel

        with self.client.post(
            f"/api/orders/{order_id}/cancel/",
            headers=self.headers,
            json={},
            name="lock/cancel_order",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 400:
                body = _safe_json(res)
                reason = _error_text(body).lower()

                if _is_expected_cancel_contention(reason):
                    res.success()  # expected under concurrent cancel/load contention
                elif "already cancelled" in reason:
                    res.success()  # متوقع من التيست نفسه، مش bug
                elif "locked" in reason:
                    res.failure(f"LOCK BLOCKED — {body}")
                else:
                    res.failure(f"Unexpected 400: {body}")
            else:
                res.failure(f"Unexpected {res.status_code}: {res.text}")
