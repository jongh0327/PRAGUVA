<?php
function run_llm($input) {
    $escaped = escapeshellarg($input);

    // EXACT behavior of your old run_python.php
    $cmd = "python3 /var/www/html/python/main_web.py -q $escaped -s bfs 2>&1";
    $output = shell_exec($cmd);

    return $output; // return so index.php can display it
}
