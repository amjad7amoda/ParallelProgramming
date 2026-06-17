import argparse
import asyncio
import json
import sys

try:
    import aiohttp
except Exception:
    print('aiohttp is required: pip install aiohttp')
    sys.exit(1)

LOGIN_PATH = '/api/users/login/'


async def get_token(session, base, username, password):
    url = f"{base}{LOGIN_PATH}"
    async with session.post(url, json={'username': username, 'password': password}) as r:
        r.raise_for_status()
        data = await r.json()
        return data.get('access')


async def fetch(session, url, headers):
    import time
    start = time.time()
    try:
        async with session.get(url, headers=headers) as r:
            elapsed = time.time() - start
            h = r.headers.get('X-Backend-Server', 'missing')
            return {'backend': h, 'status': r.status, 'elapsed': elapsed, 'error': None}
    except Exception as e:
        return {'backend': 'missing', 'status': None, 'elapsed': None, 'error': str(e)}


async def run_probe(args):
    base = args.host.rstrip('/')
    path = args.path
    url = f"{base}{path}"
    headers = {}
    connector = aiohttp.TCPConnector(limit=args.connector_limit) if args.connector_limit is not None else None
    timeout = aiohttp.ClientTimeout(total=args.timeout) if args.timeout is not None else None
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        if not args.no_auth:
            token = await get_token(session, base, args.username, args.password)
            headers['Authorization'] = f'Bearer {token}'

        sem = asyncio.Semaphore(args.concurrency)

        async def sem_fetch(i):
            async with sem:
                return await fetch(session, url, headers)

        tasks = [asyncio.create_task(sem_fetch(i)) for i in range(args.count)]
        results = await asyncio.gather(*tasks)

    counts = {}
    errors = []
    latencies = []
    for r in results:
        backend = r.get('backend', 'missing') if isinstance(r, dict) else 'missing'
        counts[backend] = counts.get(backend, 0) + 1
        if isinstance(r, dict):
            if r.get('error'):
                errors.append(r)
            if r.get('elapsed'):
                latencies.append(r['elapsed'])

    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'{k}: {v}')

    if errors:
        print('\nSample errors (up to 5):')
        for e in errors[:5]:
            print(f"error={e['error']} status={e.get('status')} backend={e.get('backend')}")

    if latencies:
        import statistics
        print(f"\nRequests: {len(latencies)}, avg latency: {statistics.mean(latencies):.3f}s, p95: {statistics.quantiles(latencies, n=100)[94]:.3f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='http://localhost:8080')
    parser.add_argument('--path', default='/api/stores/')
    parser.add_argument('--count', type=int, default=200)
    parser.add_argument('--concurrency', type=int, default=50)
    parser.add_argument('--timeout', type=float, default=10.0, help='per-request total timeout in seconds')
    parser.add_argument('--connector-limit', type=int, default=None, help='aiohttp TCPConnector limit (None = default)')
    parser.add_argument('--no-auth', action='store_true')
    parser.add_argument('--username', default='benchmark_owner')
    parser.add_argument('--password', default='Benchmark123!')
    args = parser.parse_args()
    asyncio.run(run_probe(args))


if __name__ == '__main__':
    main()
