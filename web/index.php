<?php
session_start();
require_once "controller.php";

// Initialize chat history
if (!isset($_SESSION["chat_history"])) {
    $_SESSION["chat_history"] = [];
}

// Handle AJAX requests
if ($_SERVER["REQUEST_METHOD"] === "POST" && isset($_POST["ajax"])) {
    $user_input = trim($_POST["user_input"] ?? "");
    $response = "";
    $duration = 0.0;

    if ($user_input !== "") {
        try {
            $start_time = microtime(true);
            $response = run_llm($user_input);
            $duration = round(microtime(true) - $start_time, 2);

            $_SESSION["chat_history"][] = [
                "user" => $user_input,
                "assistant" => $response,
                "duration" => $duration
            ];
        } catch (Exception $e) {
            $response = "Error: " . $e->getMessage();
        }
    }

    header("Content-Type: application/json");
    echo json_encode([
        "assistant" => $response,
        "duration" => $duration
    ]);
    exit;
}

include 'navbar.php';
?>

<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
    <title>AI Chat</title>
    <style>
        /* Keep all your existing styles */
        body { display:flex; flex-direction:column; height:100vh; margin:0; font-family:Arial, sans-serif; background-color:#f8f9fa; }
        .chat-container { flex:1; overflow-y:auto; padding:20px; background:#f0f0f0; border-radius:10px; margin:0 20px 10px 20px; box-shadow:0 2px 6px rgba(0,0,0,0.1); }
        .chat-message { margin-bottom:15px; padding:10px; border-radius:8px; background-color:white; box-shadow:0 1px 3px rgba(0,0,0,0.1); }
        .chat-message.user { border-left:4px solid #FF6F00; }
        .chat-message.assistant { border-left:4px solid #232D4B; }
        .input-container { display:flex; padding:10px 20px; background:#fff; border-top:1px solid #ccc; box-shadow:0 -1px 4px rgba(0,0,0,0.05); }
        .input-container textarea { flex:1; height:60px; padding:10px; font-size:14px; border-radius:15px; border:1px solid #ccc; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05); resize:none; outline:none; }
        .input-container button { margin-left:10px; padding:0 20px; font-size:14px; cursor:pointer; background-color:#FF6F00; color:white; border:none; border-radius:15px; transition: background 0.2s; }
        .input-container button:hover:enabled { background-color:#e65a00; }
        .input-container button:disabled { background-color:#ccc; cursor:not-allowed; }
        .typing-indicator { display:flex; align-items:center; margin-bottom:15px; }
        .typing-indicator .dot { width:8px; height:8px; margin:0 2px; background-color:#232D4B; border-radius:50%; animation:blink 1.4s infinite both; }
        .typing-indicator .dot:nth-child(2) { animation-delay:0.2s; }
        .typing-indicator .dot:nth-child(3) { animation-delay:0.4s; }
        @keyframes blink { 0%,80%,100% { opacity:0; } 40% { opacity:1; } }
        .response-time { color:gray; font-size:0.85em; margin-left:10px; }
    </style>
</head>
<body>

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
                <?php if (isset($entry["duration"])): ?>
                    <div class="response-time">Response time: <?php echo htmlspecialchars($entry["duration"]); ?>s</div>
                <?php endif; ?>
            </div>
        <?php endforeach; ?>
    <?php else: ?>
        <p id="noMessages" style="text-align:center;">No messages yet.</p>
    <?php endif; ?>
</div>

<div class="input-container">
    <textarea id="userInput" placeholder="Type your message..."></textarea>
    <button id="sendBtn">Send</button>
</div>

<script>
const container = document.getElementById("chatContainer");
const input = document.getElementById("userInput");
const btn = document.getElementById("sendBtn");
const noMessages = document.getElementById("noMessages");

function scrollBottom() { container.scrollTop = container.scrollHeight; }

function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    btn.disabled = true;
    if (noMessages) noMessages.remove();

    container.innerHTML += `
        <div class="chat-message user">
            <strong>You:</strong><pre>${text}</pre>
        </div>
    `;
    scrollBottom();
    input.value = "";

    // Typing indicator with live timer
    const typingIndicator = document.createElement("div");
    typingIndicator.className = "typing-indicator";
    typingIndicator.innerHTML = `
        <strong>Assistant:</strong>
        <div class="dot"></div><div class="dot"></div><div class="dot"></div>
        <div class="response-time" id="liveTimer">Response time: 0.0s</div>
    `;
    container.appendChild(typingIndicator);
    scrollBottom();

    let seconds = 0.0;
    const timerInterval = setInterval(() => {
        seconds += 0.1;
        document.getElementById("liveTimer").innerText = `Response time: ${seconds.toFixed(1)}s`;
    }, 100);

    fetch("", {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: "ajax=1&user_input=" + encodeURIComponent(text)
    })
    .then(res => res.json())
    .then(data => {
        clearInterval(timerInterval);
        typingIndicator.remove();

        const elapsed = data.duration ? data.duration.toFixed(2) : seconds.toFixed(1);

        if (data.assistant) {
            container.innerHTML += `
                <div class="chat-message assistant">
                    <strong>Assistant:</strong><pre>${data.assistant}</pre>
                    <div class="response-time">Response time: ${elapsed}s</div>
                </div>
            `;
            scrollBottom();
        }
        btn.disabled = false;
    })
    .catch(err => {
        clearInterval(timerInterval);
        typingIndicator.remove();
        container.innerHTML += `
            <div class="chat-message assistant">
                <strong>Assistant:</strong><pre>Error: ${err.message}</pre>
            </div>
        `;
        scrollBottom();
        btn.disabled = false;
    });
}

btn.addEventListener("click", sendMessage);
input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

scrollBottom();
</script>

</body>
</html>