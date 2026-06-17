import json
import os
import random
from pathlib import Path
from uuid import uuid4

from locust import HttpUser, task, between


BASE_DIR = Path(__file__).resolve().parent.parent
CONTEXT_FILE = Path(os.getenv('BENCHMARK_CONTEXT_FILE', BASE_DIR / 'benchmark_context.json'))


def load_context():
    if CONTEXT_FILE.exists():
        return json.loads(CONTEXT_FILE.read_text(encoding='utf-8'))
    return {
        'store_id': int(os.getenv('BENCHMARK_STORE_ID', '1')),
        'product_id': int(os.getenv('BENCHMARK_PRODUCT_ID', '1')),
        'quantity': int(os.getenv('BENCHMARK_QUANTITY', '1')),
    }


class EcommerceUser(HttpUser):
    wait_time = between(1, 3)
    bench_context = load_context()

    def on_start(self):
        self.username = f'benchmark_{uuid4().hex[:10]}'
        self.password = 'Benchmark123!'
        self.access_token = None
        self.completed = False
        self._register_and_login()

    def _auth_headers(self):
        return {'Authorization': f'Bearer {self.access_token}'} if self.access_token else {}

    def _register_and_login(self):
        register_payload = {
            'username': self.username,
            'email': f'{self.username}@example.com',
            'password': self.password,
            'role': 'CUSTOMER',
        }
        register_response = self.client.post('/api/users/register/', json=register_payload)
        register_response.raise_for_status()

        login_response = self.client.post('/api/users/login/', json={
            'username': self.username,
            'password': self.password,
        })
        login_response.raise_for_status()
        self.access_token = login_response.json()['access']

    @task
    def purchase_flow(self):
        if self.completed:
            return

        headers = self._auth_headers()
        store_id = self.bench_context['store_id']
        product_id = self.bench_context['product_id']
        quantity = self.bench_context['quantity']

        products_response = self.client.get(f'/api/stores/{store_id}/products/', headers=headers)
        products_response.raise_for_status()

        cart_response = self.client.post(
            '/api/cart/items/',
            headers=headers,
            json={'product': product_id, 'quantity': quantity},
        )
        cart_response.raise_for_status()

        order_response = self.client.post('/api/orders/', headers=headers, json={})
        order_response.raise_for_status()
        order_id = order_response.json()['id']

        payment_response = self.client.post(
            f'/api/orders/{order_id}/payment/',
            headers=headers,
            json={},
        )
        payment_response.raise_for_status()

        self.completed = True