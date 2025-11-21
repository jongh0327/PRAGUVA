<?php
session_start();
include 'navbar.php';

echo "<h2>Upload Transcript</h2>";

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
?>

<!DOCTYPE html>
<html>
<head>
    <title>Upload Transcript</title>
    <!-- Bootstrap CSS CDN -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding: 20px;
            font-family: Arial, sans-serif;
        }
        h2 {
            color: #000; /* Keep black title */
            margin-bottom: 20px;
        }
        .upload-form {
            max-width: 600px;
            margin-bottom: 30px;
        }
        .pdf-preview {
            max-height: 400px;
            overflow: auto;
            border: 1px solid #ccc;
            padding: 10px;
            border-radius: 5px;
        }
        .pdf-preview textarea {
            width: 100%;
            height: 300px;
            border: none;
            resize: none;
            background-color: #f9f9f9;
            font-family: monospace;
        }
        .btn-uva {
            background-color: #232d4b; /* UVA dark blue background */
            color: #f9f9f9;
            font-weight: bold;
        }
        .btn-uva:hover {
            background-color: #1a2035;
            color: #ff8200;
        }
    </style>
</head>
<body>

<?php if ($message): ?>
    <div class="alert alert-info"><?php echo htmlspecialchars($message); ?></div>
<?php endif; ?>

<div class="upload-form">
    <form method="POST" enctype="multipart/form-data">
        <div class="mb-3">
            <label for="pdf_file" class="form-label">Choose a PDF file:</label>
            <input type="file" name="pdf_file" accept=".pdf" required class="form-control">
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

</body>
</html>
