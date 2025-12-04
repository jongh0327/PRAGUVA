<?php
function run_llm($input, $top_k = 5, $top_per_label = 5) {
    $escaped = escapeshellarg($input);
    $top_k = intval($top_k);
    $top_per_label = intval($top_per_label);

    // Run the Python script
    $cmd = "python3 /var/www/html/python/main_web.py -q $escaped -k $top_k -l $top_per_label 2>&1";
    $output = shell_exec($cmd);
    
    // Log raw output for debugging
    error_log("Raw Python output: " . $output);

    if (empty($output)) {
        return json_encode([
            "assistant" => "Error: Python script returned no output",
            "graph" => []
        ]);
    }

    // Check if output contains HTML error (like PHP warnings)
    if (strpos($output, '<br />') !== false || strpos($output, '<b>') !== false) {
        // Strip HTML tags and return as error
        $clean_error = strip_tags($output);
        error_log("Python script error: " . $clean_error);
        return json_encode([
            "assistant" => "Error: " . $clean_error,
            "graph" => []
        ]);
    }

    // Try to decode JSON from Python output
    $decoded = json_decode($output, true);
    if ($decoded && isset($decoded['assistant'])) {
        return json_encode([
            "assistant" => $decoded['assistant'],
            "graph" => $decoded['graph'] ?? []
        ]);
    }

    // If JSON parsing failed, check if it's a Python error
    if (json_last_error() !== JSON_ERROR_NONE) {
        error_log("JSON decode error: " . json_last_error_msg());
        error_log("Output was: " . $output);
        
        return json_encode([
            "assistant" => "Error: Invalid response from Python script. Check server logs.",
            "graph" => []
        ]);
    }

    // Fallback: wrap raw output
    return json_encode([
        "assistant" => $output,
        "graph" => []
    ]);
}
?>