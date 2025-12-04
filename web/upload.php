<?php
session_start();

$preview = "";
$message = "";

// Handle form submission
if ($_SERVER["REQUEST_METHOD"] === "POST" && isset($_FILES["pdf_file"])) {
    $upload_dir = "/var/www/html/uploads/";
    if (!is_dir($upload_dir)) {
        mkdir($upload_dir, 0777, true);
    }

    $tmp_file = $_FILES["pdf_file"]["tmp_name"];
    $filename = basename($_FILES["pdf_file"]["name"]);
    $target_path = $upload_dir . $filename;

    if (move_uploaded_file($tmp_file, $target_path)) {
        $message = "File uploaded successfully: $filename";

        // Run Python script to extract text
        $escaped_input = escapeshellarg($target_path);
        $command = "python3 /var/www/html/python/pdf_to_text.py $escaped_input 2>&1";
        $output = shell_exec($command);

        if ($output) {
            // Save only the latest PDF in session
            $_SESSION["pdf_text"] = [
                "filename" => $filename,
                "text" => $output
            ];
            $preview = substr($output, 0, 1000); // show preview
        } else {
            $message = "Error: No output from Python script.";
        }
    } else {
        $message = "Error uploading file.";
    }
}

include 'navbar.php';
?>

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Upload Transcript</title>

    <!-- Bootstrap CSS (same as index.php) -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- Your project's main stylesheet (must match index.php) -->
    <link rel="stylesheet" href="styles.css">

    <style>
        /* Local page tweaks - won't override your global styles.css rules unless needed */
        main.container {
            padding-top: 1rem;
            padding-bottom: 2rem;
        }

        h2 {
            color: #000; /* keep title black like you requested */
            margin: 20px 0;
        }

        .upload-form {
            max-width: 700px;
            margin-bottom: 30px;
        }

        .pdf-preview {
            max-height: 400px;
            overflow: auto;
            border: 1px solid #ccc;
            padding: 10px;
            border-radius: 5px;
            background: #fafafa;
        }

        .pdf-preview textarea {
            width: 100%;
            height: 300px;
            border: none;
            resize: none;
            background-color: transparent;
            font-family: monospace;
        }

        /* UVA button style */
        .btn-uva {
            background-color: #232d4b; /* UVA dark blue */
            color: #f9f9f9;
            font-weight: 700;
            border: none;
        }
        .btn-uva:hover, .btn-uva:focus {
            background-color: #1a2035;
            color: #ff8200;
        }

        @media (max-width: 576px) {
            .upload-form { padding: 0 1rem; }
        }
    </style>
</head>

<body>
<main class="container">
    <h2>Upload Transcript</h2>

    <?php if ($message): ?>
        <div class="alert alert-info"><?php echo htmlspecialchars($message); ?></div>
    <?php endif; ?>

    <div class="upload-form">
        <form method="POST" enctype="multipart/form-data">
            <div class="mb-3">
                <label for="pdf_file" class="form-label">Choose a PDF file:</label>
                <input type="file" id="pdf_file" name="pdf_file" accept=".pdf" required class="form-control">
            </div>
            <div class="d-grid">
                <input type="submit" value="Upload and Convert" class="btn btn-uva w-100">
            </div>
        </form>
    </div>

    <?php if (!empty($_SESSION["pdf_text"])): ?>
        <h3>Latest Uploaded Transcript: <?php echo htmlspecialchars($_SESSION["pdf_text"]["filename"]); ?></h3>
        <div class="pdf-preview">
            <textarea readonly><?php echo htmlspecialchars($_SESSION["pdf_text"]["text"]); ?></textarea>
        </div>
    <?php endif; ?>
</main>

<!-- Bootstrap JS (keeps navbar toggler working) -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

</body>
</html>