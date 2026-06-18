#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$PROJECT_DIR/benchmark/results"
REDIS_CONTAINER="ecommerce_redis_bench"
SERVER_PID=""
PYTHON="$PROJECT_DIR/.venv/bin/python"

# Activate the virtual environment
if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    docker rm -f "$REDIS_CONTAINER" 2>/dev/null || true
    docker rm -f "ecommerce_postgres" 2>/dev/null || true
    echo -e "${GREEN}Cleanup done.${NC}"
}
trap cleanup EXIT INT TERM

ensure_port_free() {
    local port=$1
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null) || true
    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null || true
        sleep 2
        echo "  Port $port freed"
    fi
    return 0
}

wait_for_server() {
    echo -n "  Waiting for server"
    for i in $(seq 1 45); do
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/stores/ 2>/dev/null | grep -qE "200|401|403"; then
            echo -e " ${GREEN}ready!${NC}"; return 0
        fi
        echo -n "."; sleep 1
    done
    echo -e " ${RED}FAILED${NC}"; return 1
}

run_test() {
    local mode=$1
    local out="$RESULTS_DIR/${mode}_output.txt"
    echo -e "${CYAN}Running $mode test...${NC}"
    $PYTHON "$PROJECT_DIR/benchmark/test_product_caching.py" --mode "$mode" 2>&1 | tee "$out"
    echo -e "${GREEN}Saved: $out${NC}"
}

mkdir -p "$RESULTS_DIR"

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  CACHE PERFORMANCE COMPARISON${NC}"
echo -e "${CYAN}  Redis vs DummyCache for Products${NC}"
echo -e "${CYAN}========================================${NC}"

# ── Step 1: Start Redis & PostgreSQL containers ──
echo -e "\n${YELLOW}[1/5] Starting Redis and PostgreSQL containers...${NC}"

# Redis
if docker ps -q --filter "name=$REDIS_CONTAINER" | grep -q .; then
    echo "  Redis container already running, reusing."
else
    docker rm -f "$REDIS_CONTAINER" 2>/dev/null || true
    if docker run -d --rm --name "$REDIS_CONTAINER" -p 6379:6379 redis:7-alpine >/dev/null 2>&1; then
        sleep 2
        echo -e "${GREEN}  Redis started on port 6379${NC}"
    else
        echo -e "${YELLOW}  Could not start Redis container. Checking port 6379...${NC}"
        if timeout 2 bash -c 'echo > /dev/tcp/127.0.0.1/6379' 2>/dev/null; then
            echo -e "${GREEN}  Redis is already accessible on port 6379${NC}"
        else
            echo -e "${RED}  WARNING: Redis not available.${NC}"
        fi
    fi
fi

# PostgreSQL
PG_CONTAINER="ecommerce_postgres"
if docker ps -q --filter "name=$PG_CONTAINER" | grep -q .; then
    echo "  PostgreSQL container already running, reusing."
else
    docker rm -f "$PG_CONTAINER" 2>/dev/null || true
    if docker run -d --rm --name "$PG_CONTAINER" \
        -e POSTGRES_USER=ecommerce \
        -e POSTGRES_PASSWORD=ecommerce \
        -e POSTGRES_DB=ecommerce \
        -p 5432:5432 postgres:16-alpine >/dev/null 2>&1; then
        echo -n "  Waiting for PostgreSQL"
        for i in $(seq 1 30); do
            if docker exec "$PG_CONTAINER" pg_isready -U ecommerce -d ecommerce 2>/dev/null | grep -q "accepting connections"; then
                echo -e " ${GREEN}ready!${NC}"
                break
            fi
            echo -n "."; sleep 1
        done
    else
        echo -e "${YELLOW}  Could not start PostgreSQL container. Checking port 5432...${NC}"
        if timeout 2 bash -c 'echo > /dev/tcp/127.0.0.1/5432' 2>/dev/null; then
            echo -e "${GREEN}  PostgreSQL is already accessible on port 5432${NC}"
        else
            echo -e "${RED}  ERROR: PostgreSQL not available. Aborting.${NC}"
            exit 1
        fi
    fi
fi

# ── Step 2: Run migrations ──
# Use PostgreSQL (container 'ecommerce_postgres' must be running on localhost:5432)
export DJANGO_DB_ENGINE='django.db.backends.postgresql'
export POSTGRES_DB='ecommerce'
export POSTGRES_USER='ecommerce'
export POSTGRES_PASSWORD='ecommerce'
export POSTGRES_HOST='127.0.0.1'
export POSTGRES_PORT='5432'
export DJANGO_DB_NAME='ecommerce'
export DJANGO_DB_USER='ecommerce'
export DJANGO_DB_PASSWORD='ecommerce'
export DJANGO_DB_HOST='127.0.0.1'
export DJANGO_DB_PORT='5432'
# Point Redis to localhost (Docker hostname 'redis' only works inside Docker)
export REDIS_LOCATION='redis://127.0.0.1:6379/1'

echo -e "\n${YELLOW}[2/5] Applying migrations...${NC}"
cd "$PROJECT_DIR"
$PYTHON manage.py migrate --noinput 2>&1 | tail -3

# ── Step 3: Test WITH Redis ──
echo -e "\n${YELLOW}[3/5] Testing WITH Redis...${NC}"
ensure_port_free 8000
NO_REDIS=false $PYTHON manage.py runserver 0.0.0.0:8000 --noreload &
SERVER_PID=$!
wait_for_server || echo -e "${RED}  Server did not start${NC}"
run_test "redis"

# ── Step 4: Switch to NO-Redis ──
echo -e "\n${YELLOW}[4/5] Switching to WITHOUT Redis...${NC}"
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""; sleep 2; ensure_port_free 8000

NO_REDIS=true $PYTHON manage.py runserver 0.0.0.0:8000 --noreload &
SERVER_PID=$!
wait_for_server || echo -e "${RED}  Server did not start${NC}"
run_test "no-redis"

# ── Step 5: Generate comparison ──
echo -e "\n${YELLOW}[5/5] Generating comparison report...${NC}"

COMPARISON="$RESULTS_DIR/cache_comparison_report.txt"
{
    echo "============================================================"
    echo "  PRODUCT CACHING: REDIS vs NO-REDIS"
    echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================"
    echo ""
    echo "--- WITH REDIS (summary) ---"
    if [ -f "$RESULTS_DIR/redis_output.txt" ]; then
        sed -n '/SUMMARY/,/^$/p' "$RESULTS_DIR/redis_output.txt"
    fi
    echo ""
    echo "--- WITHOUT REDIS (summary) ---"
    if [ -f "$RESULTS_DIR/no-redis_output.txt" ]; then
        sed -n '/SUMMARY/,/^$/p' "$RESULTS_DIR/no-redis_output.txt"
    fi
    echo ""
    echo "============================================================"
    echo "  RAW OUTPUT: WITH REDIS"
    echo "============================================================"
    cat "$RESULTS_DIR/redis_output.txt" 2>/dev/null
    echo ""
    echo "============================================================"
    echo "  RAW OUTPUT: WITHOUT REDIS"
    echo "============================================================"
    cat "$RESULTS_DIR/no-redis_output.txt" 2>/dev/null
} > "$COMPARISON"

echo -e "${GREEN}  Report: $COMPARISON${NC}"

# ── Print side-by-side ──
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${GREEN}  QUICK COMPARISON${NC}"
echo -e "${CYAN}========================================${NC}"
if [ -f "$RESULTS_DIR/redis_output.txt" ] && [ -f "$RESULTS_DIR/no-redis_output.txt" ]; then
    echo ""
    printf "  %-30s %10s %10s\n" "Test" "Redis(ms)" "NoRedis(ms)"
    printf "  %-30s %10s %10s\n" "------------------------------" "----------" "----------"
    for name in list_cold list_warm detail_cold detail_warm increment_view increment_like; do
        r_avg=$(grep "^  $name " "$RESULTS_DIR/redis_output.txt" 2>/dev/null | awk '$2 ~ /^[0-9]/ {print $2; exit}')
        n_avg=$(grep "^  $name " "$RESULTS_DIR/no-redis_output.txt" 2>/dev/null | awk '$2 ~ /^[0-9]/ {print $2; exit}')
        [ -n "$r_avg" ] && printf "  %-30s %10.2f %10.2f\n" "$name" "$r_avg" "$n_avg"
    done
    echo ""
    r_overall=$(grep "OVERALL AVERAGE" "$RESULTS_DIR/redis_output.txt" 2>/dev/null | awk '{print $3}' | sed 's/ms//')
    n_overall=$(grep "OVERALL AVERAGE" "$RESULTS_DIR/no-redis_output.txt" 2>/dev/null | awk '{print $3}' | sed 's/ms//')
    printf "  %-30s %10.2f %10.2f\n" "OVERALL AVERAGE" "$r_overall" "$n_overall"
fi
echo ""
