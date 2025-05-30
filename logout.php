<?php
require_once 'includes/functions.php';
require_once 'includes/auth.php';

// Start session if not already started
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// Log out the user
$result = logoutUser();

// Set flash message
if ($result['success']) {
    setFlashMessage('success', 'You have been successfully logged out.');
} else {
    setFlashMessage('error', 'An error occurred during logout.');
}

// Redirect to home page
redirect('index.php');