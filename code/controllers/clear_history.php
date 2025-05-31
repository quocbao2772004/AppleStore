<?php
header('Content-Type: application/json');

// Get POST data
$data = json_decode(file_get_contents('php://input'), true);
$user_id = $data['user_id'] ?? null;
$session_id = $data['session_id'] ?? null;

if (!$user_id || !$session_id) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing user_id or session_id']);
    exit;
}

// Path to history file
$history_file = __DIR__ . '/data/history.json';

// Read current history
if (file_exists($history_file)) {
    $history = json_decode(file_get_contents($history_file), true);
} else {
    $history = [];
}

// Remove the specific session for the user
if (isset($history[$user_id][$session_id])) {
    unset($history[$user_id][$session_id]);
    
    // If user has no more sessions, remove the user entry
    if (empty($history[$user_id])) {
        unset($history[$user_id]);
    }
    
    // Save updated history
    if (file_put_contents($history_file, json_encode($history, JSON_PRETTY_PRINT))) {
        echo json_encode(['success' => true]);
    } else {
        http_response_code(500);
        echo json_encode(['error' => 'Could not save history file']);
    }
} else {
    echo json_encode(['success' => true, 'message' => 'No history found to clear']);
} 