<?php
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $user_input = $_POST["user_input"] ?? "";
    $escaped_input = escapeshellarg($user_input);

    // Run main.py with a -q argument
    $command = "python3 /var/www/html/python/main_web.py -q $escaped_input 2>&1";
    $output = shell_exec($command);
    echo nl2br(htmlspecialchars($output));
} else {
    echo "No input received.";
}
?>