#!/bin/bash
# Management script for LLM server (run inside Docker container)

SOCKET_PATH="/tmp/llm_server.sock"
LOG_FILE="/var/log/llm_server.log"
SCRIPT_PATH="/var/www/html/python/llm_server.py"

case "$1" in
    status)
        if [ -e "$SOCKET_PATH" ]; then
            echo "✓ Socket exists at $SOCKET_PATH"
            PID=$(pgrep -f "llm_server.py")
            if [ -n "$PID" ]; then
                echo "✓ Server is running (PID: $PID)"
            else
                echo "✗ Socket exists but no process found"
            fi
        else
            echo "✗ Socket not found"
            echo "✗ Server is not running"
        fi
        
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "Last 10 lines of log:"
            tail -10 "$LOG_FILE"
        fi
        ;;
    
    start)
        if [ -e "$SOCKET_PATH" ]; then
            echo "Server is already running"
            exit 1
        fi
        
        echo "Starting LLM server..."
        source /opt/venv/bin/activate
        python3 "$SCRIPT_PATH" > "$LOG_FILE" 2>&1 &
        echo "Started with PID: $!"
        
        # Wait for ready
        echo "Waiting for server to be ready..."
        timeout=30
        elapsed=0
        while [ $elapsed -lt $timeout ]; do
            if grep -q "SERVER_READY" "$LOG_FILE" 2>/dev/null; then
                echo "✓ Server is ready!"
                exit 0
            fi
            sleep 1
            elapsed=$((elapsed + 1))
        done
        
        echo "✗ Server did not become ready in time"
        tail -20 "$LOG_FILE"
        exit 1
        ;;
    
    stop)
        PID=$(pgrep -f "llm_server.py")
        if [ -n "$PID" ]; then
            echo "Stopping server (PID: $PID)..."
            kill $PID
            sleep 2
            
            # Force kill if still running
            if kill -0 $PID 2>/dev/null; then
                echo "Force killing..."
                kill -9 $PID
            fi
            
            echo "✓ Server stopped"
        else
            echo "Server is not running"
        fi
        
        # Clean up socket
        if [ -e "$SOCKET_PATH" ]; then
            rm "$SOCKET_PATH"
            echo "✓ Removed socket file"
        fi
        ;;
    
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    
    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "Log file not found: $LOG_FILE"
        fi
        ;;
    
    test)
        if [ ! -e "$SOCKET_PATH" ]; then
            echo "✗ Server is not running"
            exit 1
        fi
        
        echo "Testing server with query: 'test query'..."
        python3 << 'EOF'
import socket
import json

SOCKET_PATH = "/tmp/llm_server.sock"

try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    
    request = json.dumps({"query": "What is machine learning?", "top_k": 2}) + "\n"
    sock.sendall(request.encode())
    
    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
        if b"\n" in response:
            break
    
    sock.close()
    
    data = json.loads(response.decode().strip())
    if "error" in data:
        print(f"✗ Error: {data['error']}")
    else:
        print(f"✓ Success!")
        print(f"Answer: {data['answer'][:200]}...")
except Exception as e:
    print(f"✗ Failed: {e}")
EOF
        ;;
    
    *)
        echo "Usage: $0 {status|start|stop|restart|logs|test}"
        echo ""
        echo "Commands:"
        echo "  status   - Check if server is running"
        echo "  start    - Start the server"
        echo "  stop     - Stop the server"
        echo "  restart  - Restart the server"
        echo "  logs     - Tail the log file"
        echo "  test     - Send a test query"
        exit 1
        ;;
esac