import json
import os
import uuid
from pathlib import Path

from locust import HttpUser, task, between, events
from locust.stats import stats_printer
import time


BASE_DIR = Path(__file__).resolve().parent.parent
CONTEXT_FILE = Path(os.getenv('BENCHMARK_CONTEXT_FILE', BASE_DIR / 'benchmark_context.json'))


def load_context():
    if CONTEXT_FILE.exists():
        try:
            return json.loads(CONTEXT_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


class RedisPerformanceUser(HttpUser):
    """
    Locust user for testing Redis caching performance on product endpoints.
    Tests the endpoints that use Redis caching:
    - Product list (cached with 5-minute TTL)
    - Product retrieve (cached with 10-minute TTL)
    - increment_view (uses Redis INCR)
    - increment_like (uses Redis INCR)
    """
    
    wait_time = between(0.5, 2.0)
    ctx = load_context()
    
    def on_start(self):
        """Register and login a unique user for each simulated user"""
        self.username = f"redis_test_{uuid.uuid4().hex[:8]}"
        self.password = "RedisTest123!"
        
        # Register
        try:
            r = self.client.post('/api/users/register/', json={
                'username': self.username,
                'email': f'{self.username}@example.com',
                'password': self.password,
                'role': 'CUSTOMER',
            })
        except Exception:
            pass
        
        # Login
        try:
            login = self.client.post('/api/users/login/', json={
                'username': self.username, 
                'password': self.password
            })
            if login.status_code == 200:
                token = login.json().get('access')
                if token:
                    self.auth_headers = {'Authorization': f'Bearer {token}'}
                else:
                    self.auth_headers = {}
            else:
                self.auth_headers = {}
        except Exception:
            self.auth_headers = {}
        
        # Get store_id and product_id from context or defaults
        self.store_id = self.ctx.get('store_id', 1)
        self.product_id = self.ctx.get('product_id', 1)
    
    @task(10)
    def list_products(self):
        """Test product list endpoint (uses Redis caching)"""
        r = self.client.get(
            f'/api/stores/{self.store_id}/products/', 
            headers=getattr(self, 'auth_headers', {})
        )
        if r.status_code >= 500:
            r.raise_for_status()
    
    @task(5)
    def retrieve_product(self):
        """Test product retrieve endpoint (uses Redis caching)"""
        r = self.client.get(
            f'/api/stores/{self.store_id}/products/{self.product_id}/', 
            headers=getattr(self, 'auth_headers', {})
        )
        if r.status_code >= 500:
            r.raise_for_status()
    
    @task(2)
    def increment_view(self):
        """Test increment_view endpoint (uses Redis INCR)"""
        r = self.client.post(
            f'/api/stores/{self.store_id}/products/{self.product_id}/increment_view/', 
            headers=getattr(self, 'auth_headers', {})
        )
        if r.status_code >= 500:
            r.raise_for_status()
    
    @task(1)
    def increment_like(self):
        """Test increment_like endpoint (uses Redis INCR)"""
        r = self.client.post(
            f'/api/stores/{self.store_id}/products/{self.product_id}/increment_like/', 
            headers=getattr(self, 'auth_headers', {})
        )
        if r.status_code >= 500:
            r.raise_for_status()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print summary when test stops"""
    print("\n" + "="*60)
    print("REDIS PERFORMANCE TEST SUMMARY")
    print("="*60)
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"Min response time: {environment.stats.total.min_response_time:.2f}ms")
    print(f"Max response time: {environment.stats.total.max_response_time:.2f}ms")
    print(f"Requests/s: {environment.stats.total.total_rps:.2f}")
    print("="*60)
