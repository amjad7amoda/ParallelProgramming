#!/bin/bash

# Script to run Redis performance test with Redis DISABLED
# This uses Django's dummy cache backend to simulate no Redis

echo "=== RUNNING REDIS PERFORMANCE TEST (WITHOUT REDIS) ==="
echo "This test uses Django's dummy cache backend"
echo "Make sure:"
echo "1. Docker containers are running (docker-compose up)"
echo "2. Django server is running with NO_REDIS=true"
echo "3. Test data has been setup (python benchmark/setup_redis_test_data.py)"
echo ""

cd "$(dirname "$0")/.."

# Run Locust with Redis performance test
# Using environment variable to disable Redis
export NO_REDIS=true

locust -f benchmark/redis_performance_test.py \
    --host=http://127.0.0.1:8000 \
    --users=50 \
    --spawn-rate=10 \
    --run-time=2m \
    --headless \
    --html=benchmark/results/redis_disabled_report.html \
    --csv=benchmark/results/redis_disabled_stats

echo ""
echo "=== TEST COMPLETE ==="
echo "Results saved to benchmark/results/redis_disabled_report.html"
echo "CSV stats saved to benchmark/results/redis_disabled_stats_*"
