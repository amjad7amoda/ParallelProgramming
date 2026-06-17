import argparse
import asyncio
import sys
import json

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


async def fetch(session, url, headers, method='GET', body=None):
    import time
    start = time.time()
    try:
        if method.upper() == 'GET':
            async with session.get(url, headers=headers) as r:
                elapsed = time.time() - start
                h = r.headers.get('X-Backend-Server', 'missing')
                return {'backend': h, 'status': r.status, 'elapsed': elapsed, 'error': None}
        else:
            async with session.post(url, headers=headers, json=body) as r:
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

        # warmup
        if args.warmup and args.warmup > 0:
            for _ in range(args.warmup):
                await fetch(session, url, headers, method=args.method, body=args.body)

        sem = asyncio.Semaphore(args.concurrency)

        async def sem_fetch(i):
            async with sem:
                result = await fetch(session, url, headers, method=args.method, body=args.body)
                result['index'] = i
                return result

        tasks = []
        for i in range(args.count):
            tasks.append(asyncio.create_task(sem_fetch(i)))
            if args.stagger > 0:
                await asyncio.sleep(args.stagger)

        results = await asyncio.gather(*tasks)

    counts = {}
    errors = []
    latencies = []
    ordered = sorted(results, key=lambda item: item.get('index', 0))
    for r in results:
        backend = r.get('backend', 'missing') if isinstance(r, dict) else 'missing'
        counts[backend] = counts.get(backend, 0) + 1
        if isinstance(r, dict):
            if r.get('error'):
                errors.append(r)
            if r.get('elapsed'):
                latencies.append(r['elapsed'])

    for r in ordered:
        print(f"Request {r.get('index', '?') + 1}: {r.get('backend', 'missing')}")

    print('\n--- Counts ---')
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'{k}: {v}')

    if errors:
        print('\nSample errors (up to 5):')
        for e in errors[:5]:
            print(f"error={e['error']} status={e.get('status')} backend={e.get('backend')}")

    if latencies:
        import statistics
        p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 100 else max(latencies)
        print(f"\nRequests: {len(latencies)}, avg latency: {statistics.mean(latencies):.3f}s, p95: {p95:.3f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='http://localhost:8080')
    parser.add_argument('--path', default='/api/stores/')
    parser.add_argument('--count', type=int, default=500)
    parser.add_argument('--concurrency', type=int, default=400)
    parser.add_argument('--timeout', type=float, default=30.0)
    parser.add_argument('--connector-limit', type=int, default=0)
    parser.add_argument('--no-auth', action='store_true')
    parser.add_argument('--username', default='benchmark_owner')
    parser.add_argument('--password', default='Benchmark123!')
    parser.add_argument('--method', default='GET')
    parser.add_argument('--body', type=json.loads, default=None)
    parser.add_argument('--warmup', type=int, default=5, help='number of warmup requests (sequential)')
    parser.add_argument('--stagger', type=float, default=0.0, help='delay between starting tasks (seconds)')
    args = parser.parse_args()
    asyncio.run(run_probe(args))


if __name__ == '__main__':
    main()
