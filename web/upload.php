<?php
session_start();
include 'navbar.php';

echo "<h2>Upload PDF</h2>";

if ($_SERVER["REQUEST_METHOD"] === "POST" && isset($_FILES["pdf_file"])) {
    $upload_dir = "/var/www/html/uploads/";
    if (!is_dir($upload_dir)) {
        mkdir($upload_dir, 0777, true);
    }

    $file_tmp = $_FILES["pdf_file"]["tmp_name"];
    $file_name = basename($_FILES["pdf_file"]["name"]);
    $target_path = $upload_dir . $file_name;

    if (move_uploaded_file($file_tmp, $target_path)) {
        echo "<p>File uploaded successfully: $file_name</p>";

        // Run Python inside the venv to extract text
        $python = "/opt/venv/bin/python3";
        $script = "/var/www/html/python/pdf_to_text.py";
        $command = escapeshellcmd("$python $script " . escapeshellarg($target_path));
        $output = shell_exec($command . " 2>&1");

        if ($output) {
            $_SESSION["pdf_text"] = $output;
            echo "<p><strong>Text extracted and saved to session.</strong></p>";
            echo "<pre>" . htmlspecialchars(substr($output, 0, 1000)) . "</pre>"; // show preview
        } else {
            echo "<p>Error: No output from Python script.</p>";
        }
    } else {
        echo "<p>Error uploading file.</p>";
    }
} else {
    echo '
    <form method="POST" enctype="multipart/form-data">
        <label for="pdf_file">Choose a PDF file:</label><br>
        <input type="file" name="pdf_file" accept=".pdf" required><br><br>
        <input type="submit" value="Upload and Convert">
    </form>';
}
?>