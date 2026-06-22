"""
locustfile.py
شغل السكريبت بـ:
    locust -f locustfile.py --host=http://127.0.0.1:8000

بعدها افتح المتصفح على:
    http://localhost:8089

وحدد:
    Number of users: 100
    Ramp up: 10 (أو أي رقم بدك)

ملاحظة: لازم تشغل seed_stress_data.py مرة واحدة قبل تشغيل هذا السكريبت
عشان يكون عندك 100 يوزر (loadtest_user_0 .. loadtest_user_99) جاهزين.
"""

import random
import threading

from locust import HttpUser, task, between

NUM_SEEDED_USERS = 100
PASSWORD = "Test1234!"

_user_pool = list(range(NUM_SEEDED_USERS))
_pool_lock = threading.Lock()


def get_next_username():
    with _pool_lock:
        if not _user_pool:
            _user_pool.extend(range(NUM_SEEDED_USERS))
        idx = _user_pool.pop()
    return f"loadtest_user_{idx}"


class EcommerceUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.username = get_next_username()
        self.access_token = None
        self.store_id = None
        self.product_ids = []
        self._checkout_lock = threading.Lock()

        self.login()
        self.discover_store_and_products()

    def login(self, retries=3):
        for _ in range(retries):
            try:
                resp = self.client.post(
                    "/api/users/login/",
                    json={"username": self.username, "password": PASSWORD},
                    name="/api/users/login/",
                )
                if resp.status_code == 200:
                    self.access_token = resp.json().get("access")
                    return
            except Exception:
                pass
            import time
            time.sleep(1)
        self.access_token = None

    @property
    def auth_headers(self):
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def discover_store_and_products(self):
        if not self.access_token:
            return

        resp = self.client.get(
            "/api/stores/",
            headers=self.auth_headers,
            name="/api/stores/ [discover]",
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data["results"] if isinstance(data, dict) else data
            if results:
                self.store_id = results[0]["id"]

        if self.store_id:
            resp = self.client.get(
                f"/api/stores/{self.store_id}/products/",
                headers=self.auth_headers,
                name="/api/stores/{id}/products/ [discover]",
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data["results"] if isinstance(data, dict) else data
                self.product_ids = [p["id"] for p in results]

    # ------------------- Tasks -------------------

    @task(5)
    def browse_products(self):
        if not self.store_id:
            return
        self.client.get(
            f"/api/stores/{self.store_id}/products/",
            headers=self.auth_headers,
            name="/api/stores/{id}/products/",
        )

    @task(3)
    def add_to_cart(self):
        if not self.product_ids:
            return
        product_id = random.choice(self.product_ids)
        self.client.post(
            "/api/cart/items/",
            json={"product": product_id, "quantity": random.randint(1, 3)},
            headers=self.auth_headers,
            name="/api/cart/items/ [add]",
        )

    @task(2)
    def view_cart(self):
        if not self.access_token:
            return
        self.client.get(
            "/api/cart/items/",
            headers=self.auth_headers,
            name="/api/cart/items/ [list]",
        )

    @task(1)
    def checkout(self):
        if not self.access_token or not self.product_ids:
            return

        if not self._checkout_lock.acquire(blocking=False):
            return

        try:
            # 1. أضف منتج للسلة
            product_id = random.choice(self.product_ids)
            add_resp = self.client.post(
                "/api/cart/items/",
                json={"product": product_id, "quantity": random.randint(1, 3)},
                headers=self.auth_headers,
                name="/api/cart/items/ [add]",
            )
            if add_resp.status_code not in (200, 201):
                return

            # 2. عمل الأوردر
            with self.client.post(
                "/api/orders/",
                json={},
                headers=self.auth_headers,
                name="/api/orders/ [checkout]",
                catch_response=True,
            ) as resp:
                if resp.status_code != 201:
                    try:
                        error_msg = resp.json()
                    except Exception:
                        error_msg = resp.text
                    resp.failure(f"Checkout failed ({resp.status_code}): {error_msg}")
                    return
                order_id = resp.json().get("id")
                if not order_id:
                    resp.failure("Checkout response missing order ID")
                    return
                resp.success()

            # 3. الدفع
            with self.client.post(
                f"/api/orders/{order_id}/payment/",
                json={},
                headers=self.auth_headers,
                name="/api/orders/{id}/payment/ [pay]",
                catch_response=True,
            ) as pay_resp:
                if pay_resp.status_code != 201:
                    try:
                        error_msg = pay_resp.json()
                    except Exception:
                        error_msg = pay_resp.text
                    pay_resp.failure(f"Payment failed ({pay_resp.status_code}): {error_msg}")
                else:
                    pay_resp.success()

        finally:
            self._checkout_lock.release()