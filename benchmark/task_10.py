from locust import HttpUser, task, between

class ECommerceUser(HttpUser):
    wait_time = between(0.5, 2)
    store_id = 1  
    username = "benchmark_user"
    password = "benchmark123"  
    token = None

    def on_start(self):
        creds = {"username": self.username, "password": self.password}
        with self.client.post("/api/users/login/", json=creds, catch_response=True) as response:
            if response.status_code == 200:
                self.token = response.json().get("access")
                print("✅ Login successful.")
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                response.failure("Login failed")

    @task(1)
    def list_products(self):
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get(
            f"/api/stores/{self.store_id}/products/",
            headers=headers,
            name="/api/stores/[id]/products/"
        )
