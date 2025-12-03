<?php
/**
 * Simple test page to diagnose issues
 */
error_reporting(E_ALL);
ini_set('display_errors', 1);

echo "<pre>";
echo "=== LLM Server Test ===\n\n";

// Check if run_llm.php exists
if (!file_exists('run_llm.php')) {
    echo "❌ ERROR: run_llm.php not found!\n";
    echo "Files in current directory:\n";
    print_r(scandir('.'));
    exit;
}

echo "✓ run_llm.php exists\n\n";

// Try to include it
try {
    require_once "run_llm.php";
    echo "✓ run_llm.php loaded successfully\n\n";
} catch (Exception $e) {
    echo "❌ ERROR loading run_llm.php: " . $e->getMessage() . "\n";
    exit;
}

// Check if function exists
if (!function_exists('run_llm')) {
    echo "❌ ERROR: run_llm() function not found!\n";
    exit;
}

echo "✓ run_llm() function exists\n\n";

// Use the updated socket location
$socket_path = '/tmp/llm_server.sock';
echo "Socket path: $socket_path\n";
echo "Socket exists: " . (file_exists($socket_path) ? "✓ YES" : "❌ NO") . "\n\n";

// Test socket connection first
echo "=== Testing Socket Connection ===\n";
$sock = @socket_create(AF_UNIX, SOCK_STREAM, 0);
if ($sock) {
    if (@socket_connect($sock, $socket_path)) {
        echo "✓ Socket connection successful\n";
        socket_close($sock);
    } else {
        echo "❌ Socket connection FAILED: " . socket_strerror(socket_last_error($sock)) . "\n";
        socket_close($sock);
    }
} else {
    echo "❌ Cannot create socket: " . socket_strerror(socket_last_error()) . "\n";
}
echo "\n";

// Try TWO queries to see if second is faster

echo "=== Query 1 ===\n";
$start1 = microtime(true);
$result1 = run_llm("Who is Scott Acton?");
$duration1 = round((microtime(true) - $start1), 2);
echo "Duration: {$duration1}s\n";
echo "Result: " . htmlspecialchars(substr($result1, 0, 100)) . "...\n\n";

echo "=== Query 2 (should be faster!) ===\n";
$start2 = microtime(true);
$result2 = run_llm("Who is Caroline Crockett?");
$duration2 = round((microtime(true) - $start2), 2);
echo "Duration: {$duration2}s\n";
echo "Result: " . htmlspecialchars(substr($result2, 0, 100)) . "...\n\n";

echo "=== Speed Comparison ===\n";
echo "Query 1: {$duration1}s\n";
echo "Query 2: {$duration2}s\n";
if ($duration2 < $duration1 * 0.5) {
    echo "✓ Second query is significantly faster! Socket server working!\n";
} else {
    echo "❌ No speedup detected. Likely using fallback method.\n";
}
echo "\n✓ Test completed!\n";
echo "</pre>";
?>