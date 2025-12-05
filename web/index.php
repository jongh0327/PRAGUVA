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
    $raw_nodes = [];
    $raw_edges = [];

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
                // Store raw nodes and edges instead of full graph
                $raw_nodes = $decoded['raw_nodes'] ?? [];
                $raw_edges = $decoded['raw_edges'] ?? [];
            } else {
                // If JSON decode failed, treat entire output as response
                $response = $output;
            }

            $duration = round(microtime(true) - $start_time, 2);

            // Save to session chat history with raw data
            $_SESSION["chat_history"][] = [
                "user" => $user_input,
                "assistant" => $response,
                "raw_nodes" => $raw_nodes,
                "raw_edges" => $raw_edges,
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
        "raw_nodes" => $raw_nodes,
        "raw_edges" => $raw_edges,
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
    <link rel="stylesheet" href="styles/chat.css">
    <title>AI Chat</title>
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
            <div class="chat-message assistant" 
                 data-raw-nodes='<?php echo htmlspecialchars(json_encode($entry["raw_nodes"] ?? []), ENT_QUOTES, 'UTF-8'); ?>'
                 data-raw-edges='<?php echo htmlspecialchars(json_encode($entry["raw_edges"] ?? []), ENT_QUOTES, 'UTF-8'); ?>'>
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

// Transform raw nodes/edges to Cytoscape format - ONLY when Graph button is clicked
function transformToCytoscape(rawNodes, rawEdges) {
    const cy_nodes = [];
    for (const n of rawNodes) {
        const node_labels = n.labels || [];
        // Remove "Searchable" from labels
        const filtered_labels = node_labels.filter(label => label !== "Searchable");
        const label_str = filtered_labels.length > 0 ? filtered_labels.join(" | ") : "Initial Node";
        
        cy_nodes.push({
            data: {
                id: n.id,
                label: label_str,
                nodeType: filtered_labels[0] || "Initial",
                ...n.props
            }
        });
    }

    const cy_edges = [];
    for (const r of rawEdges) {
        const source = r.source || r.start || "";
        const target = r.target || r.end || "";
        cy_edges.push({
            data: {
                id: r.id || `${source}_${target}`,
                source: source,
                target: target,
                type: r.type || r.rel_type || ""
            }
        });
    }

    return { nodes: cy_nodes, edges: cy_edges };
}

// Graph button listener (event delegation) - Transform data on-demand
container.addEventListener("click", e => {
    if (e.target.classList.contains("graph-btn")) {
        const assistantDiv = e.target.closest(".chat-message.assistant");
        const rawNodesStr = assistantDiv.getAttribute("data-raw-nodes");
        const rawEdgesStr = assistantDiv.getAttribute("data-raw-edges");
        
        try {
            const rawNodes = JSON.parse(rawNodesStr || "[]");
            const rawEdges = JSON.parse(rawEdgesStr || "[]");
            
            // Transform to Cytoscape format NOW (only when button clicked)
            const graphData = transformToCytoscape(rawNodes, rawEdges);
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
    const excludeKeys = ['label', 'id', 'topicID', 'paperID', 'instructorID', 'courseID', 'departmentID', 'majorID', 'minorID'];

    if (data.nodeType) {
        html += `<div class="info-row"><span class="info-label">Node Type:</span> ${escapeHtml(String(data.nodeType))}</div>`;
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

        // Extract response - raw nodes/edges not transformed yet
        const assistantText = data.assistant || "";
        const rawNodes = data.raw_nodes || [];
        const rawEdges = data.raw_edges || [];

        const assistantDiv = document.createElement("div");
        assistantDiv.className = "chat-message assistant";
        assistantDiv.setAttribute("data-raw-nodes", JSON.stringify(rawNodes));
        assistantDiv.setAttribute("data-raw-edges", JSON.stringify(rawEdges));
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