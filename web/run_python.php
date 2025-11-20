<?php
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $user_input = $_POST["user_input"] ?? "";
    $escaped_input = escapeshellarg($user_input);

    // Run main_web.py in BFS mode
    $command = "python3 /var/www/html/python/main_web.py -q $escaped_input -s bfs 2>&1";
    $output = shell_exec($command);

    echo nl2br(htmlspecialchars($output));
} else {
    echo "No input received.";
}
?>