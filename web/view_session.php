<?php
session_start();
if (isset($_SESSION["pdf_text"])) {
    echo "<h2>PDF Text from Session:</h2>";
    echo "<pre>" . htmlspecialchars($_SESSION["pdf_text"]) . "</pre>";
} else {
    echo "<p>No PDF text found in session.</p>";
}
?>