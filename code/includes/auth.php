<?php
require_once 'functions.php';
require_once __DIR__ . '/../config/database.php';

// Register a new user
function registerUser($name, $email, $password, $phone = null, $address = null, $role = 'customer') {
    global $pdo;
    
    try {
        // Check if email already exists
        $stmt = $pdo->prepare("SELECT id FROM users WHERE email = ?");
        $stmt->execute([$email]);
        
        if ($stmt->rowCount() > 0) {
            return [
                'success' => false,
                'message' => 'Email already exists'
            ];
        }
        
        // Hash password
        $hashedPassword = password_hash($password, PASSWORD_DEFAULT);
        
        // Insert user
        $stmt = $pdo->prepare("INSERT INTO users (name, email, password, phone, address, role) VALUES (?, ?, ?, ?, ?, ?)");
        $stmt->execute([$name, $email, $hashedPassword, $phone, $address, $role]);
        
        return [
            'success' => true,
            'message' => 'Registration successful',
            'user_id' => $pdo->lastInsertId()
        ];
    } catch (PDOException $e) {
        return [
            'success' => false,
            'message' => 'Registration failed: ' . $e->getMessage()
        ];
    }
}

// Login user
function loginUser($email, $password) {
    global $pdo;
    
    try {
        // Get user by email
        $stmt = $pdo->prepare("SELECT id, name, email, password, role FROM users WHERE email = ?");
        $stmt->execute([$email]);
        
        if ($stmt->rowCount() === 0) {
            return [
                'success' => false,
                'message' => 'Invalid email or password'
            ];
        }
        
        $user = $stmt->fetch();
        
        // Verify password
        if (!password_verify($password, $user['password'])) {
            return [
                'success' => false,
                'message' => 'Invalid email or password'
            ];
        }
        
        // Set session variables
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['user_name'] = $user['name'];
        $_SESSION['user_email'] = $user['email'];
        $_SESSION['user_role'] = $user['role'];
        
        return [
            'success' => true,
            'message' => 'Login successful',
            'user' => [
                'id' => $user['id'],
                'name' => $user['name'],
                'email' => $user['email'],
                'role' => $user['role']
            ]
        ];
    } catch (PDOException $e) {
        return [
            'success' => false,
            'message' => 'Login failed: ' . $e->getMessage()
        ];
    }
}

// Logout user
function logoutUser() {
    // Unset all session variables
    $_SESSION = [];
    
    // Destroy the session
    session_destroy();
    
    return [
        'success' => true,
        'message' => 'Logout successful'
    ];
}

// Get current user
function getCurrentUser() {
    global $pdo;
    
    if (!isLoggedIn()) {
        return null;
    }
    
    try {
        $stmt = $pdo->prepare("SELECT id, name, email, phone, address, role FROM users WHERE id = ?");
        $stmt->execute([$_SESSION['user_id']]);
        
        return $stmt->fetch();
    } catch (PDOException $e) {
        return null;
    }
}

// Update user profile
function updateUserProfile($id, $name, $email, $phone, $address) {
    global $pdo;
    
    try {
        $stmt = $pdo->prepare("UPDATE users SET name = ?, email = ?, phone = ?, address = ? WHERE id = ?");
        $stmt->execute([$name, $email, $phone, $address, $id]);
        
        // Update session variables
        $_SESSION['user_name'] = $name;
        $_SESSION['user_email'] = $email;
        
        return [
            'success' => true,
            'message' => 'Profile updated successfully'
        ];
    } catch (PDOException $e) {
        return [
            'success' => false,
            'message' => 'Profile update failed: ' . $e->getMessage()
        ];
    }
}

// Change password
function changePassword($id, $currentPassword, $newPassword) {
    global $pdo;
    
    try {
        // Get current password
        $stmt = $pdo->prepare("SELECT password FROM users WHERE id = ?");
        $stmt->execute([$id]);
        $user = $stmt->fetch();
        
        // Verify current password
        if (!password_verify($currentPassword, $user['password'])) {
            return [
                'success' => false,
                'message' => 'Current password is incorrect'
            ];
        }
        
        // Hash new password
        $hashedPassword = password_hash($newPassword, PASSWORD_DEFAULT);
        
        // Update password
        $stmt = $pdo->prepare("UPDATE users SET password = ? WHERE id = ?");
        $stmt->execute([$hashedPassword, $id]);
        
        return [
            'success' => true,
            'message' => 'Password changed successfully'
        ];
    } catch (PDOException $e) {
        return [
            'success' => false,
            'message' => 'Password change failed: ' . $e->getMessage()
        ];
    }
}