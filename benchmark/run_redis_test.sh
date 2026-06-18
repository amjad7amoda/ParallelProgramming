#!/bin/bash

# Script to run Redis performance test with Redis enabled
# This is the baseline test with Redis caching active

echo "=== RUNNING REDIS PERFORMANCE TEST (WITH REDIS) ==="
echo "Make sure:"
echo "1. Docker containers are running (docker-compose up)"
echo "2. Django server is running"
echo "3. Test data has been setup (python benchmark/setup_redis_test_data.py)"
echo ""

cd "$(dirname "$0")/.."

# Run Locust with Redis performance test
# -f: locustfile
# --host: target URL
# --users: number of simulated users
# --spawn-rate: users spawned per second
# --run-time: duration of test
# --headless: run without web UI
# --html: output HTML report

locust -f benchmark/redis_performance_test.py \
    --host=http://127.0.0.1:8000 \
    --users=50 \
    --spawn-rate=10 \
    --run-time=2m \
    --headless \
    --html=benchmark/results/redis_enabled_report.html \
    --csv=benchmark/results/redis_enabled_stats

echo ""
echo "=== TEST COMPLETE ==="
echo "Results saved to benchmark/results/redis_enabled_report.html"
echo "CSV stats saved to benchmark/results/redis_enabled_stats_*"
