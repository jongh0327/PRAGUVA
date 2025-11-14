<?php
session_start();
include 'navbar.php';

echo "<h2>Upload PDF</h2>";

if ($_SERVER["REQUEST_METHOD"] === "POST" && isset($_FILES["pdf_file"])) {
    $upload_dir = "/var/www/html/uploads/";
    if (!is_dir($upload_dir)) {
        mkdir($upload_dir, 0777, true);
    }

    // --- Move uploaded file to persistent uploads directory ---
    $user_input = $_FILES["pdf_file"]["tmp_name"];  // temporary uploaded file
    $target = $upload_dir . basename($_FILES["pdf_file"]["name"]);

    if (move_uploaded_file($user_input, $target)) {
        echo "<p>File uploaded successfully: " . basename($_FILES["pdf_file"]["name"]) . "</p>";

        // --- Run Python script to extract text ---
        $escaped_input = escapeshellarg($target);
        $command = "python3 /var/www/html/python/pdf_to_text.py $escaped_input 2>&1";
        $output = shell_exec($command);

        if ($output) {
            $_SESSION["pdf_text"] = $output; // Save extracted text in session
            echo "<p><strong>Text extracted and saved to session.</strong></p>";
            echo "<pre>" . htmlspecialchars(substr($output, 0, 1000)) . "</pre>"; // show preview
        } else {
            echo "<p>Error: No output from Python script.</p>";
        }

    } else {
        echo "<p>Error uploading file.</p>";
    }

} else {
    // Upload form
    echo '
    <form method="POST" enctype="multipart/form-data">
        <label for="pdf_file">Choose a PDF file:</label><br>
        <input type="file" name="pdf_file" accept=".pdf" required><br><br>
        <input type="submit" value="Upload and Convert">
    </form>';
}
?>