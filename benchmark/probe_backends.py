import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


LOGIN_PATH = '/api/users/login/'


def login_and_get_token(base_url, username, password):
    payload = json.dumps({
        'username': username,
        'password': password,
    }).encode('utf-8')
    request = Request(
        f'{base_url}{LOGIN_PATH}',
        data=payload,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode('utf-8'))
    return data.get('access')


def fetch_backend_header(base_url, path, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = Request(f'{base_url}{path}', method='GET', headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            backend_id = response.headers.get('X-Backend-Server', 'missing')
            return response.status, backend_id
    except HTTPError as error:
        backend_id = error.headers.get('X-Backend-Server', 'missing') if error.headers else 'missing'
        return error.code, backend_id


def main():
    parser = argparse.ArgumentParser(description='Probe load balancer backends via X-Backend-Server header')
    parser.add_argument('--host', default='http://localhost:8080', help='Base URL of the load balancer')
    parser.add_argument('--path', default='/api/stores/', help='API path to request')
    parser.add_argument('--count', '-n', type=int, default=10, help='Number of requests to make')
    parser.add_argument('--no-auth', action='store_true', help='Do not authenticate before requests')
    parser.add_argument('--username', default='benchmark_owner')
    parser.add_argument('--password', default='Benchmark123!')
    args = parser.parse_args()

    token = None
    if not args.no_auth:
        try:
            token = login_and_get_token(args.host, args.username, args.password)
        except Exception as e:
            print('Login failed:', e)
            return

    for index in range(args.count):
        status_code, backend_id = fetch_backend_header(args.host, args.path, token)
        print(f'{index + 1}: {status_code} {backend_id}')


if __name__ == '__main__':
    main()