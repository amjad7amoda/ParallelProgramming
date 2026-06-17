import json
import os
import uuid
from pathlib import Path

from locust import HttpUser, task, between


BASE_DIR = Path(__file__).resolve().parent.parent
CONTEXT_FILE = Path(os.getenv('BENCHMARK_CONTEXT_FILE', BASE_DIR / 'benchmark_context.json'))


def load_context():
    if CONTEXT_FILE.exists():
        try:
            return json.loads(CONTEXT_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


class SimpleUser(HttpUser):
    """State-free user that registers a unique account on start, logs in,
    then performs only GETs (and occasional lightweight register POSTs)
    so requests are deterministic and should succeed.
    """

    wait_time = between(1, 2)
    ctx = load_context()

    def on_start(self):
        # perform a lightweight register + login sequence per simulated user
        self.username = f"load_{uuid.uuid4().hex[:8]}"
        self.password = "LoadTest123!"
        # register
        try:
            r = self.client.post('/api/users/register/', json={
                'username': self.username,
                'email': f'{self.username}@example.com',
                'password': self.password,
                'role': 'CUSTOMER',
            })
        except Exception:
            r = None
        # login if possible
        try:
            login = self.client.post('/api/users/login/', json={'username': self.username, 'password': self.password})
            if login and login.status_code == 200:
                token = login.json().get('access')
                if token:
                    self.auth_headers = {'Authorization': f'Bearer {token}'}
                else:
                    self.auth_headers = {}
            else:
                self.auth_headers = {}
        except Exception:
            self.auth_headers = {}

        self.store_id = self.ctx.get('store_id')
        self.product_id = self.ctx.get('product_id')

    @task(3)
    def list_stores(self):
        r = self.client.get('/api/stores/', headers=getattr(self, 'auth_headers', {}))
        if r.status_code >= 500:
            r.raise_for_status()

    @task(6)
    def list_products(self):
        store_id = self.store_id or 1
        r = self.client.get(f'/api/stores/{store_id}/products/', headers=getattr(self, 'auth_headers', {}))
        if r.status_code >= 500:
            r.raise_for_status()

    @task(1)
    def lightweight_register(self):
        # occasional POST that creates a unique, harmless user (no DB conflicts)
        uname = f"load_{uuid.uuid4().hex[:10]}"
        r = self.client.post('/api/users/register/', json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': 'LoadTest123!',
            'role': 'CUSTOMER',
        })
        # only escalate on server error
        if r.status_code >= 500:
            r.raise_for_status()
