<?php
function run_llm($input, $top_k = 5, $top_per_label = 5) {
    // Build the payload object
    $payloadObj = ["user_input" => $input];
    
    // Add chat history from sessionStorage (if available via POST)
    if (isset($_POST["payload"])) {
        $decodedPayload = json_decode($_POST["payload"], true);
        if ($decodedPayload) {
            // Merge the decoded payload (contains history and transcript)
            $payloadObj = array_merge($payloadObj, $decodedPayload);
        }
    }
    
    // Add transcript from session if available
    if (isset($_SESSION["pdf_text"]) && !empty($_SESSION["pdf_text"])) {
        $payloadObj["transcript"] = $_SESSION["pdf_text"];
    }
    
    // Encode the complete payload as JSON
    $payload = json_encode($payloadObj);
    
    // Escape the payload for shell
    $escaped = escapeshellarg($payload);
    $top_k = intval($top_k);
    $top_per_label = intval($top_per_label);

    // Run the Python script - send payload as -q parameter
    $cmd = "python3 /var/www/html/python/main_web.py -q $escaped -k $top_k -l $top_per_label 2>&1";
    $output = shell_exec($cmd);
    
    // Log raw output for debugging
    error_log("Raw Python output: " . $output);

    if (empty($output)) {
        return json_encode([
            "assistant" => "Error: Python script returned no output",
            "raw_nodes" => [],
            "raw_edges" => []
        ]);
    }

    // Check if output contains HTML error (like PHP warnings)
    if (strpos($output, '<br />') !== false || strpos($output, '<b>') !== false) {
        // Strip HTML tags and return as error
        $clean_error = strip_tags($output);
        error_log("Python script error: " . $clean_error);
        return json_encode([
            "assistant" => "Error: " . $clean_error,
            "raw_nodes" => [],
            "raw_edges" => []
        ]);
    }

    // Try to decode JSON from Python output
    $decoded = json_decode($output, true);
    if ($decoded && isset($decoded['assistant'])) {
        return json_encode([
            "assistant" => $decoded['assistant'],
            "raw_nodes" => $decoded['raw_nodes'] ?? [],
            "raw_edges" => $decoded['raw_edges'] ?? []
        ]);
    }

    // If JSON parsing failed, check if it's a Python error
    if (json_last_error() !== JSON_ERROR_NONE) {
        error_log("JSON decode error: " . json_last_error_msg());
        error_log("Output was: " . $output);
        
        return json_encode([
            "assistant" => "Error: Invalid response from Python script. Check server logs.",
            "raw_nodes" => [],
            "raw_edges" => []
        ]);
    }

    // Fallback: wrap raw output
    return json_encode([
        "assistant" => $output,
        "raw_nodes" => [],
        "raw_edges" => []
    ]);
}
?>