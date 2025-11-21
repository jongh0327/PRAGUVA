<?php
session_start();
include 'navbar.php';
require_once "controller.php";

// Initialize history array
if (!isset($_SESSION["chat_history"])) {
    $_SESSION["chat_history"] = [];
}

// Handle form submission
$response = "";
if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $user_input = trim($_POST["user_input"] ?? "");
    if ($user_input !== "") {
        $response = run_llm($user_input);

        $_SESSION["chat_history"][] = [
            "user" => $user_input,
            "assistant" => $response
        ];
    }
}
?>
<!DOCTYPE html>
<html>
<head>
    <title>AI Chat</title>
    <link rel="stylesheet" href="styles.css">
    <style>
        body {
            display: flex;
            flex-direction: column;
            height: 100vh;
            margin: 0;
            font-family: Arial, sans-serif;
            background-color: #f8f9fa;
        }
        h1 {
            text-align: center;
            margin: 10px 0;
            color: black; /* Keep title black */
        }
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f0f0f0;
            border-radius: 10px;
            margin: 0 20px 10px 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }
        .chat-message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .chat-message.user {
            border-left: 4px solid #FF6F00;
        }
        .chat-message.assistant {
            border-left: 4px solid #232D4B;
        }

        /* Input area styling */
        .input-container {
            display: flex;
            padding: 10px 20px;
            background: #fff;
            border-top: 1px solid #ccc;
            box-shadow: 0 -1px 4px rgba(0,0,0,0.05);
        }
        .input-container textarea {
            flex: 1;
            height: 60px;
            padding: 10px;
            font-size: 14px;
            border-radius: 15px;
            border: 1px solid #ccc;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
            resize: none;
            outline: none;
        }
        .input-container button {
            margin-left: 10px;
            padding: 0 20px;
            font-size: 14px;
            cursor: pointer;
            background-color: #FF6F00;
            color: white;
            border: none;
            border-radius: 15px;
            transition: background 0.2s;
        }
        .input-container button:hover {
            background-color: #e65a00;
        }
    </style>
</head>
<body>
<!--
<h1>AI Chat</h1>
-->
<div class="chat-container" id="chatContainer">
    <?php if (!empty($_SESSION["chat_history"])): ?>
        <?php foreach ($_SESSION["chat_history"] as $entry): ?>
            <div class="chat-message user">
                <strong>You:</strong>
                <pre><?php echo htmlspecialchars($entry["user"]); ?></pre>
            </div>
            <div class="chat-message assistant">
                <strong>Assistant:</strong>
                <pre><?php echo htmlspecialchars($entry["assistant"]); ?></pre>
            </div>
        <?php endforeach; ?>
    <?php else: ?>
        <p style="text-align:center;">No messages yet.</p>
    <?php endif; ?>
</div>

<div class="input-container">
    <form method="POST" style="width:100%; display:flex;">
        <textarea name="user_input" required placeholder="Type your message..."></textarea>
        <button type="submit">Send</button>
    </form>
</div>

<script>
    // Scroll to bottom on page load
    const chatContainer = document.getElementById("chatContainer");
    chatContainer.scrollTop = chatContainer.scrollHeight;
</script>

</body>
</html>