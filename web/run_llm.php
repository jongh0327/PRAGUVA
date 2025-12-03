<?php

define('SOCKET_PATH', '/tmp/llm_server.sock');
define('TIMEOUT', 120);

/**
 * Fallback: Run Python directly
 */
function run_llm_fallback($input, $top_k = 5) {
    $escaped = escapeshellarg($input);
    $cmd = "python3 /var/www/html/python/main_web.py -q $escaped 2>&1";
    $output = shell_exec($cmd);
    return $output ?: "Error: No output from Python";
}

/**
 * Send a query to the persistent LLM server
 */
function run_llm($input, $top_k = 5) {

    if (!file_exists(SOCKET_PATH)) {
        error_log("LLM socket not found, using fallback method");
        return run_llm_fallback($input, $top_k);
    }

    $socket = @socket_create(AF_UNIX, SOCK_STREAM, 0);
    if (!$socket) {
        error_log("Socket create failed");
        return run_llm_fallback($input, $top_k);
    }

    socket_set_option($socket, SOL_SOCKET, SO_RCVTIMEO, ['sec' => TIMEOUT, 'usec' => 0]);
    socket_set_option($socket, SOL_SOCKET, SO_SNDTIMEO, ['sec' => 10, 'usec' => 0]);

    if (!@socket_connect($socket, SOCKET_PATH)) {
        $err = socket_strerror(socket_last_error($socket));
        socket_close($socket);
        error_log("Connect failed: $err");
        return run_llm_fallback($input, $top_k);
    }

    $request = json_encode([
        "query" => $input,
        "top_k" => $top_k
    ]) . "\n";

    socket_write($socket, $request, strlen($request));

    $response = "";
    while ($chunk = socket_read($socket, 4096)) {
        $response .= $chunk;
        if (strpos($response, "\n") !== false) break;
    }

    socket_close($socket);

    if (!$response) return "Error: No response from LLM server";

    $data = json_decode(trim($response), true);
    if (json_last_error() !== JSON_ERROR_NONE)
        return "Error: Invalid JSON from server";

    if (isset($data['error'])) return "Error: " . $data['error'];

    return $data['answer'] ?? "No answer received";
}