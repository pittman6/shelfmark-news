default: refresh

sync:
    @echo "Syncing dependencies..."
    uv sync

test:
    @echo "Running tests..."
    uv run pytest -v

lint:
    @echo "Running linter..."
    ruff check

run:
    @echo "Starting shelfmark-news server..."
    uv run shelfmark-news

up:
    @echo "Starting container..."
    docker compose up -d

down:
    @echo "Stopping container..."
    docker compose down

build:
    @echo "Building Docker image..."
    docker compose build

refresh:
    @echo "Rebuilding and restarting container..."
    docker compose down
    docker compose build
    docker compose up -d

watch:
    #!/usr/bin/env bash
    cleanup() { kill $log_pid 2>/dev/null; exit 0; }
    trap cleanup INT TERM
    last="" log_pid=""
    while true; do
        new=$(docker inspect -f {{ "'{{.Id}}'" }} shelfmark-news 2>/dev/null) || true
        if [ "$new" != "$last" ] && [ -n "$new" ]; then
            [ -z "$log_pid" ] || kill "$log_pid" 2>/dev/null
            docker logs -f --tail 0 "$new" 2>&1 &
            log_pid=$!
            last="$new"
        fi
        sleep 2
    done