#!/bin/bash
# Start the LLM server in the background and then start Apache

set -e

echo "Starting LLM Server..."

# Activate virtual environment
source /opt/venv/bin/activate

# Start LLM server in background, redirect output to log file
nohup python3 /var/www/html/python/llm_server.py > /var/log/llm_server.log 2>&1 &
LLM_PID=$!

echo "LLM Server PID: $LLM_PID"

# Wait for server to be ready (max 60 seconds)
echo "Waiting for LLM Server to be ready..."
timeout=60
elapsed=0
while [ $elapsed -lt $timeout ]; do
    if grep -q "SERVER_READY" /var/log/llm_server.log 2>/dev/null; then
        echo "✓ LLM Server is ready!"
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
    
    # Check if process is still running
    if ! kill -0 $LLM_PID 2>/dev/null; then
        echo "ERROR: LLM Server died during startup"
        cat /var/log/llm_server.log
        exit 1
    fi
done

if [ $elapsed -ge $timeout ]; then
    echo "ERROR: LLM Server failed to start within ${timeout}s"
    cat /var/log/llm_server.log
    exit 1
fi

# Show last few lines of log
echo "Last lines of LLM server log:"
tail -5 /var/log/llm_server.log

echo "Starting Apache..."

# Start Apache in foreground (this keeps the container running)
# When Apache stops, the container will stop, but LLM server will continue running
exec apache2-foreground