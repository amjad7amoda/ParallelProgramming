# ParallelProgramming

## E-commerce Load Balancing Lab

This project is a Django REST e-commerce API for a college report on non-functional requirements. The core workflow is database-backed through Django ORM models:

- users register and automatically receive a cart
- cart items are stored in the database
- orders are created from the cart and reduce stock inside a transaction
- payments are stored in the database and mark the order as paid
- JWT logout blacklisting also uses the database-backed Simple JWT blacklist app

There is no Redis backend in the current codebase.

## Docker Stack

- `docker-compose.yml` runs the API directly against PostgreSQL for the no-load-balancer baseline + Redis Backend
- `docker-compose.lb.yml` runs three Django app containers behind Nginx with round-robin upstreams
- `docker-compose.least.yml` runs the same stack with Nginx `least_conn` upstreams

Typical local commands:

```bash
docker compose up --build
docker compose -f docker-compose.lb.yml up --build
docker compose -f docker-compose.least.yml up --build
```

## Benchmark Workflow

Use the benchmark seed command first:

```bash
python manage.py migrate
python manage.py seed_benchmark_data
```

That command creates a deterministic benchmark store and product and writes `benchmark_context.json` with the IDs used by the load test.

Run Locust from `benchmark/locustfile.py` with 100 users. The scenario creates a unique customer, registers it, logs in, adds the seeded product to cart, creates an order, and completes payment.

To capture the summary in the plain-text comparison file, use `benchmark/run_benchmark.ps1` and point it at either `http://localhost:8000` for the direct baseline or `http://localhost:8080` for the Nginx stack.

Example:

```powershell
.enchmark
un_benchmark.ps1 -HostUrl http://localhost:8000 -Label "Baseline without load balancer"
.enchmark
un_benchmark.ps1 -HostUrl http://localhost:8080 -Label "Nginx round robin"
```

## Algorithm Choice

Round robin is the baseline Nginx algorithm because the API is stateless at the HTTP layer and the workload is mostly short write requests. Least connections is also included because checkout bursts can create uneven response times when the database is under contention. The benchmark compares both to see which one gives better throughput and tail latency for this specific project.

## Results File

Record the output of the three runs in `benchmark/benchmark_results.txt`:

1. direct app access with PostgreSQL only
2. Nginx round robin
3. Nginx least connections

The file is plain text so it can be pasted directly into the report.
