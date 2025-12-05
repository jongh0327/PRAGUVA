<?php
// Start output buffering FIRST to catch any whitespace/errors
ob_start();

// Start session before any output
session_start();
require_once "controller.php";

// Initialize chat history
if (!isset($_SESSION["chat_history"])) {
    $_SESSION["chat_history"] = [];
}

// Handle AJAX requests BEFORE any HTML output
if ($_SERVER["REQUEST_METHOD"] === "POST" && isset($_POST["ajax"])) {
    // Clean any output buffer that might have accumulated
    ob_clean();
    
    $user_input = trim($_POST["user_input"] ?? "");
    $top_k = intval($_POST["top_k"] ?? 5);
    $top_per_label = intval($_POST["top_per_label"] ?? 5);
    $response = "";
    $duration = 0.0;
    $graph = [];

    if ($user_input !== "") {
        try {
            $start_time = microtime(true);
            
            // Call the Python script via controller
            $output = run_llm($user_input, $top_k, $top_per_label);
            
            // Log the raw output for debugging
            error_log("Python output: " . $output);
            
            $decoded = json_decode($output, true);

            if ($decoded && isset($decoded['assistant'])) {
                $response = $decoded['assistant'];
                $graph = $decoded['graph'] ?? [];
            } else {
                // If JSON decode failed, treat entire output as response
                $response = $output;
            }

            $duration = round(microtime(true) - $start_time, 2);

            // Save to session chat history
            $_SESSION["chat_history"][] = [
                "user" => $user_input,
                "assistant" => $response,
                "graph" => $graph,
                "duration" => $duration
            ];

            // Keep only last 10 messages
            if (count($_SESSION["chat_history"]) > 10) {
                $_SESSION["chat_history"] = array_slice($_SESSION["chat_history"], -10);
            }

        } catch (Exception $e) {
            $response = "Error: " . $e->getMessage();
            error_log("Exception in AJAX handler: " . $e->getMessage());
        }
    }

    header("Content-Type: application/json");
    echo json_encode([
        "assistant" => $response,
        "graph" => $graph,
        "duration" => $duration
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

// Include navbar AFTER session_start and AJAX handling
include 'navbar.php';

// Flush the output buffer
ob_end_flush();
?>

<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
    <title>AI Chat</title>
    <style>
        body { 
            display: flex; 
            flex-direction: column; 
            height: 100vh; 
            margin: 0; 
            font-family: Arial, sans-serif; 
            background-color: #f8f9fa; 
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
            position: relative; 
        }
        .chat-message.user { 
            border-left: 4px solid #FF6F00; 
        }
        .chat-message.assistant { 
            border-left: 4px solid #232D4B; 
        }
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
        .input-container button:hover:enabled { 
            background-color: #e65a00; 
        }
        .input-container button:disabled { 
            background-color: #ccc; 
            cursor: not-allowed; 
        }
        .typing-indicator { 
            display: flex; 
            align-items: center; 
            margin-bottom: 15px; 
        }
        .typing-indicator .dot { 
            width: 8px; 
            height: 8px; 
            margin: 0 2px; 
            background-color: #232D4B; 
            border-radius: 50%; 
            animation: blink 1.4s infinite both; 
        }
        .typing-indicator .dot:nth-child(2) { 
            animation-delay: 0.2s; 
        }
        .typing-indicator .dot:nth-child(3) { 
            animation-delay: 0.4s; 
        }
        @keyframes blink { 
            0%, 80%, 100% { opacity: 0; } 
            40% { opacity: 1; } 
        }
        .response-time { 
            color: gray; 
            font-size: 0.85em; 
            margin-top: 5px; 
        }
        .graph-btn { 
            position: absolute; 
            top: 10px; 
            right: 10px; 
            padding: 4px 10px; 
            font-size: 12px; 
            cursor: pointer; 
            border: none; 
            border-radius: 5px; 
            background: #FF6F00; 
            color: white; 
        }
        .graph-btn:hover {
            background: #e65a00;
        }
        #settingsModal { 
            display: none; 
            position: fixed; 
            top: 50%; 
            left: 50%; 
            transform: translate(-50%, -50%);
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.3); 
            z-index: 1000; 
            width: 250px; 
        }
        #settingsModal h3 { 
            margin-top: 0; 
        }
        #graphModal { 
            display: none; 
            position: fixed; 
            top: 50%; 
            left: 50%; 
            transform: translate(-50%, -50%);
            background: white; 
            padding: 10px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.3); 
            z-index: 2000; 
            width: 80%; 
            height: 80%; 
        }
        #graphModal #cy { 
            width: 100%; 
            height: calc(100% - 60px); 
            margin-top: 50px;
        }
        #graphModal .graph-modal-close { 
            position: absolute; 
            top: 10px; 
            right: 10px; 
            background: #FF6F00; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            padding: 5px 10px; 
            cursor: pointer; 
            z-index: 2001; 
        }
        #nodeInfo {
            position: absolute;
            top: 50px;
            left: 10px;
            right: 10px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 10px;
            max-height: 200px;
            overflow-y: auto;
            display: none;
            z-index: 2001;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        #nodeInfo h4 {
            margin: 0 0 10px 0;
            color: #232D4B;
            border-bottom: 2px solid #FF6F00;
            padding-bottom: 5px;
        }
        #nodeInfo .info-row {
            margin: 5px 0;
            font-size: 13px;
        }
        #nodeInfo .info-label {
            font-weight: bold;
            color: #666;
        }
        #nodeInfo .close-info {
            position: absolute;
            top: 5px;
            right: 5px;
            background: #FF6F00;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 2px 8px;
            cursor: pointer;
            font-size: 12px;
        }
    </style>
    <script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js"></script>
</head>
<body>

<div class="chat-container" id="chatContainer">
    <?php if (!empty($_SESSION["chat_history"])): ?>
        <?php foreach ($_SESSION["chat_history"] as $entry): ?>
            <div class="chat-message user">
                <strong>You:</strong>
                <pre><?php echo htmlspecialchars($entry["user"]); ?></pre>
            </div>
            <div class="chat-message assistant" data-graph='<?php echo htmlspecialchars(json_encode($entry["graph"]), ENT_QUOTES, 'UTF-8'); ?>'>
                <strong>Assistant:</strong>
                <pre><?php echo htmlspecialchars($entry["assistant"]); ?></pre>
                <button class="graph-btn">Graph</button>
                <?php if (isset($entry["duration"])): ?>
                    <div class="response-time">Response time: <?php echo htmlspecialchars($entry["duration"]); ?>s</div>
                <?php endif; ?>
            </div>
        <?php endforeach; ?>
    <?php else: ?>
        <p id="noMessages" style="text-align:center; color:#999;">No messages yet. Start a conversation!</p>
    <?php endif; ?>
</div>

<div class="input-container">
    <textarea id="userInput" placeholder="Type your message..."></textarea>
    <button id="sendBtn">Send</button>
    <button id="settingsBtn">⚙️</button>
</div>

<!-- Settings modal -->
<div id="settingsModal">
    <h3>Search Settings</h3>
    <div style="margin-bottom:10px;">
        <label for="topK"># Starting Nodes:</label>
        <span id="topKVal" style="display:inline-block; width:30px; text-align:right;">5</span>
        <input type="range" id="topK" min="1" max="20" value="5" style="width:100%;">
    </div>
    <div style="margin-bottom:10px;">
        <label for="topPerLabel"># Nodes per Hop per Label:</label>
        <span id="topPerLabelVal" style="display:inline-block; width:35px; text-align:right;">5</span>
        <input type="range" id="topPerLabel" min="0" max="100" value="5" style="width:100%;">
    </div>
    <button id="closeSettings" style="margin-top:10px; width:100%;">Close</button>
</div>

<!-- Graph Modal -->
<div id="graphModal">
    <button class="graph-modal-close" id="closeGraphModal">X</button>
    <div id="nodeInfo">
        <button class="close-info" id="closeNodeInfo">×</button>
        <h4>Node Information</h4>
        <div id="nodeInfoContent"></div>
    </div>
    <div id="cy"></div>
</div>

<script>
const container = document.getElementById("chatContainer");
const input = document.getElementById("userInput");
const btn = document.getElementById("sendBtn");
const settingsBtn = document.getElementById("settingsBtn");
const modal = document.getElementById("settingsModal");
const closeSettings = document.getElementById("closeSettings");
const topKSlider = document.getElementById("topK");
const topPerLabelSlider = document.getElementById("topPerLabel");
const topKVal = document.getElementById("topKVal");
const topPerLabelVal = document.getElementById("topPerLabelVal");
const noMessages = document.getElementById("noMessages");

const graphModal = document.getElementById("graphModal");
const closeGraphModal = document.getElementById("closeGraphModal");
const nodeInfo = document.getElementById("nodeInfo");
const nodeInfoContent = document.getElementById("nodeInfoContent");
const closeNodeInfo = document.getElementById("closeNodeInfo");

let topK = parseInt(topKSlider.value);
let topPerLabel = parseInt(topPerLabelSlider.value);

// Update slider values
topKSlider.addEventListener("input", () => { 
    topK = parseInt(topKSlider.value); 
    topKVal.innerText = topK; 
});
topPerLabelSlider.addEventListener("input", () => { 
    topPerLabel = parseInt(topPerLabelSlider.value); 
    topPerLabelVal.innerText = topPerLabel; 
});

// Settings modal
settingsBtn.addEventListener("click", () => { modal.style.display = "block"; });
closeSettings.addEventListener("click", () => { modal.style.display = "none"; });

// Graph modal
closeGraphModal.addEventListener("click", () => {
    graphModal.style.display = "none";
    nodeInfo.style.display = "none";
    document.getElementById("cy").innerHTML = "";
});

closeNodeInfo.addEventListener("click", () => {
    nodeInfo.style.display = "none";
});

function scrollBottom() { 
    container.scrollTop = container.scrollHeight; 
}

// Graph button listener (event delegation)
container.addEventListener("click", e => {
    if (e.target.classList.contains("graph-btn")) {
        const assistantDiv = e.target.closest(".chat-message.assistant");
        const graphDataStr = assistantDiv.getAttribute("data-graph");
        try {
            const graphData = JSON.parse(graphDataStr || "{}");
            openGraphModal(graphData);
        } catch (err) {
            console.error("Failed to parse graph data:", err);
            alert("Error loading graph data");
        }
    }
});

function openGraphModal(graph) {
    if (!graph.nodes) graph.nodes = [];
    if (!graph.edges) graph.edges = [];
    
    graphModal.style.display = "block";
    nodeInfo.style.display = "none";
    
    // Clear previous graph
    document.getElementById('cy').innerHTML = "";
    
    // Store full node data for info panel
    const nodeDataMap = {};
    graph.nodes.forEach(n => {
        nodeDataMap[n.data.id] = n.data;
    });
    
    // Create Cytoscape visualization
    const cy = cytoscape({
        container: document.getElementById('cy'),
        elements: [
            ...graph.nodes.map(n => ({ 
                data: { 
                    id: n.data.id, 
                    label: n.data.name || n.data.label || n.data.id 
                } 
            })),
            ...graph.edges.map(e => ({ 
                data: { 
                    id: e.data.id, 
                    source: e.data.source, 
                    target: e.data.target, 
                    label: e.data.type 
                } 
            }))
        ],
        style: [
            { 
                selector: 'node', 
                style: { 
                    'content': 'data(label)', 
                    'background-color': '#232D4B', 
                    'color': '#000000', 
                    'font-weight': 'bold',
                    'text-valign': 'center', 
                    'text-halign': 'center',
                    'font-size': '11px',
                    'width': '60px',
                    'height': '60px',
                    'text-outline-color': '#ffffff',
                    'text-outline-width': 2
                } 
            },
            { 
                selector: 'node:selected', 
                style: { 
                    'background-color': '#FF6F00',
                    'border-width': 3,
                    'border-color': '#e65a00'
                } 
            },
            { 
                selector: 'edge', 
                style: { 
                    'width': 2, 
                    'line-color': '#FF6F00', 
                    'target-arrow-color': '#FF6F00', 
                    'target-arrow-shape': 'triangle', 
                    'curve-style': 'bezier', 
                    'label': 'data(label)', 
                    'font-size': 9, 
                    'text-rotation': 'autorotate',
                    'color': '#000000',
                    'font-weight': 'bold',
                    'text-outline-color': '#ffffff',
                    'text-outline-width': 1
                } 
            }
        ],
        layout: { 
            name: 'cose', 
            animate: true,
            padding: 10
        }
    });
    
    // Add click handler for nodes
    cy.on('tap', 'node', function(evt) {
        const node = evt.target;
        const nodeId = node.id();
        const fullData = nodeDataMap[nodeId];
        
        if (fullData) {
            displayNodeInfo(fullData);
        }
    });
    
    // Hide info panel when clicking on background
    cy.on('tap', function(evt) {
        if (evt.target === cy) {
            nodeInfo.style.display = "none";
        }
    });
}

function displayNodeInfo(data) {
    let html = '';
    
    // Define the order of attributes and which ones to exclude
    const excludeKeys = ['label', 'id', 'topicID', 'paperID', 'instructorID', 'courseID', 'departmentID'];

    if (data.nodeType) {
        html += `<div class="info-row"><span class="info-label">None Type:</span> ${escapeHtml(String(data.nodeType))}</div>`;
    }
    
    // Always display name first if it exists
    if (data.name) {
        html += `<div class="info-row"><span class="info-label">Name:</span> ${escapeHtml(String(data.name))}</div>`;
    }
    
    // Display all other properties except excluded ones
    for (const [key, value] of Object.entries(data)) {
        // Skip if it's in the exclude list or if it's 'name' (already displayed)
        if (excludeKeys.includes(key) || key === 'name' || key === 'nodeType') {
            continue;
        }
        
        if (typeof value === 'object' && value !== null) {
            html += `<div class="info-row"><span class="info-label">${escapeHtml(key)}:</span> ${escapeHtml(JSON.stringify(value, null, 2))}</div>`;
        } else if (value !== undefined && value !== null && value !== '') {
            html += `<div class="info-row"><span class="info-label">${escapeHtml(key)}:</span> ${escapeHtml(String(value))}</div>`;
        }
    }
    
    if (html === '') {
        html = '<div class="info-row">No additional information available</div>';
    }
    
    nodeInfoContent.innerHTML = html;
    nodeInfo.style.display = "block";
}

function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    btn.disabled = true;
    if (noMessages) noMessages.remove();

    // Display user message
    const userDiv = document.createElement("div");
    userDiv.className = "chat-message user";
    userDiv.innerHTML = `<strong>You:</strong><pre>${escapeHtml(text)}</pre>`;
    container.appendChild(userDiv);
    scrollBottom();
    input.value = "";

    // Show typing indicator
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
        const timerEl = document.getElementById("liveTimer");
        if (timerEl) {
            timerEl.innerText = `Response time: ${seconds.toFixed(1)}s`;
        }
    }, 100);

    // Build payload with history and transcript
    const payloadObj = { user_input: text };
    const saved = sessionStorage.getItem("chat_history");
    const history = saved ? JSON.parse(saved) : [];
    payloadObj.history = history.slice(-10);

    <?php if (!empty($_SESSION["pdf_text"])): ?>
        payloadObj.transcript = <?php echo json_encode($_SESSION["pdf_text"]); ?>;
    <?php endif; ?>

    // Send request
    fetch("", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body:
            "ajax=1" +
            "&user_input=" + encodeURIComponent(text) +
            "&payload=" + encodeURIComponent(JSON.stringify(payloadObj)) +
            "&top_k=" + encodeURIComponent(topK) +
            "&top_per_label=" + encodeURIComponent(topPerLabel)
    })
    .then(res => res.json())
    .then(data => {
        clearInterval(timerInterval);
        typingIndicator.remove();

        const elapsed = data.duration ? data.duration.toFixed(2) : seconds.toFixed(1);

        // Extract only the assistant text, not the graph data
        const assistantText = data.assistant || "";
        const graphData = data.graph || {};

        const assistantDiv = document.createElement("div");
        assistantDiv.className = "chat-message assistant";
        assistantDiv.setAttribute("data-graph", JSON.stringify(graphData));
        assistantDiv.innerHTML = `
            <strong>Assistant:</strong><pre>${escapeHtml(assistantText)}</pre>
            <button class="graph-btn">Graph</button>
            <div class="response-time">Response time: ${elapsed}s</div>
        `;
        container.appendChild(assistantDiv);
        scrollBottom();

        // Save to sessionStorage (last 10 messages)
        history.push({ user: text, assistant: assistantText, duration: elapsed });
        sessionStorage.setItem("chat_history", JSON.stringify(history.slice(-10)));

        btn.disabled = false;
    })
    .catch(err => {
        clearInterval(timerInterval);
        typingIndicator.remove();

        const errorDiv = document.createElement("div");
        errorDiv.className = "chat-message assistant";
        errorDiv.innerHTML = `<strong>Assistant:</strong><pre>Error: ${escapeHtml(err.message)}</pre>`;
        container.appendChild(errorDiv);
        scrollBottom();
        btn.disabled = false;
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

btn.addEventListener("click", sendMessage);
input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { 
        e.preventDefault(); 
        sendMessage(); 
    }
});

scrollBottom();
</script>

</body>
</html>