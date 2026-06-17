import argparse
import requests
import sys
import time

def run_sequence_probe(args):
    """Makes sequential requests and prints the backend server for each."""
    backend_hits = []
    print(f"--- Probing {args.host} {args.count} times sequentially ({args.delay:.2f}s delay between requests) ---\n")

    for i in range(args.count):
        try:
            r = requests.get(args.host, timeout=10)
            r.raise_for_status()
            backend_id = r.headers.get('X-Backend-Server', 'missing')
            backend_hits.append(backend_id)
            print(f"Request {i+1}: {backend_id}")
        except requests.exceptions.RequestException as e:
            print(f"Request {i+1}: FAILED ({e})")
            backend_hits.append("FAILED")
        
        if args.delay > 0:
            time.sleep(args.delay)

    print("\n--- Sequence Summary ---")
    print(", ".join(backend_hits))
    print("\n--- Counts ---")
    counts = {}
    for hit in backend_hits:
        counts[hit] = counts.get(hit, 0) + 1
    for k, v in sorted(counts.items()):
        print(f"{k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Probe backends sequentially to observe LB patterns.")
    parser.add_argument('--host', default='http://localhost:8080/api/stores/')
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--delay', type=float, default=0, help="Delay in seconds between requests.")
    args = parser.parse_args()
    run_sequence_probe(args)


if __name__ == '__main__':
    main()
