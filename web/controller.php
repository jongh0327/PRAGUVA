<?php
function run_llm($input, $top_k = 5, $top_per_label = 5) {
    $escaped = escapeshellarg($input);
    $top_k = intval($top_k);
    $top_per_label = intval($top_per_label);

    $cmd = "python3 /var/www/html/python/main_web.py -q $escaped -k $top_k -l $top_per_label 2>&1";
    $output = shell_exec($cmd);

    return $output;
}