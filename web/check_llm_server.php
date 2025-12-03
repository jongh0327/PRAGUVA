<?php
/**
 * Health check script to verify LLM server is running
 * Access via: http://localhost:8080/check_llm_server.php
 */

define('SOCKET_PATH', '/tmp/llm_server.sock');

header('Content-Type: application/json');

$status = array(
    'socket_exists' => file_exists(SOCKET_PATH),
    'socket_readable' => is_readable(SOCKET_PATH),
    'socket_writable' => is_writable(SOCKET_PATH),
    'can_connect' => false,
    'test_query_success' => false,
    'response_time_ms' => null,
    'error' => null
);

// Check if we can connect
if ($status['socket_exists']) {
    $socket = @socket_create(AF_UNIX, SOCK_STREAM, 0);
    if ($socket !== false) {
        socket_set_option($socket, SOL_SOCKET, SO_RCVTIMEO, array('sec' => 5, 'usec' => 0));
        socket_set_option($socket, SOL_SOCKET, SO_SNDTIMEO, array('sec' => 5, 'usec' => 0));
        
        if (@socket_connect($socket, SOCKET_PATH)) {
            $status['can_connect'] = true;
            
            // Try a simple test query
            $start_time = microtime(true);
            $request = json_encode(array(
                "query" => "test",
                "top_k" => 1
            )) . "\n";
            
            if (socket_write($socket, $request, strlen($request)) !== false) {
                $response = "";
                while ($chunk = socket_read($socket, 4096)) {
                    $response .= $chunk;
                    if (strpos($response, "\n") !== false) {
                        break;
                    }
                }
                
                $end_time = microtime(true);
                $status['response_time_ms'] = round(($end_time - $start_time) * 1000, 2);
                
                $data = json_decode(trim($response), true);
                if ($data !== null) {
                    $status['test_query_success'] = true;
                }
            }
            
            socket_close($socket);
        } else {
            $status['error'] = "Cannot connect: " . socket_strerror(socket_last_error($socket));
            socket_close($socket);
        }
    } else {
        $status['error'] = "Cannot create socket: " . socket_strerror(socket_last_error());
    }
} else {
    $status['error'] = "Socket file does not exist at " . SOCKET_PATH;
}

// Overall health
$status['healthy'] = $status['can_connect'] && $status['test_query_success'];

// Pretty print
echo json_encode($status, JSON_PRETTY_PRINT);