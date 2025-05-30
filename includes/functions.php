<?php
// Start session if not already started
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// Clean input data
function clean($data) {
    $data = trim($data);
    $data = stripslashes($data);
    $data = htmlspecialchars($data);
    return $data;
}

// Generate slug from string
function generateSlug($string) {
    $string = strtolower($string);
    $string = preg_replace('/[^a-z0-9\-]/', '-', $string);
    $string = preg_replace('/-+/', '-', $string);
    $string = trim($string, '-');
    return $string;
}

// Flash messages
function setFlashMessage($type, $message) {
    $_SESSION['flash'] = [
        'type' => $type,
        'message' => $message
    ];
}

function getFlashMessage() {
    if (isset($_SESSION['flash'])) {
        $flash = $_SESSION['flash'];
        unset($_SESSION['flash']);
        return $flash;
    }
    return null;
}

// Check if user is logged in
function isLoggedIn() {
    return isset($_SESSION['user_id']);
}

// Check if user is admin
function isAdmin() {
    return isset($_SESSION['user_role']) && $_SESSION['user_role'] === 'admin';
}

// Redirect to a URL
function redirect($url) {
    header("Location: $url");
    exit;
}

// Pagination function
function paginate($total, $per_page, $current_page, $url) {
    $total_pages = ceil($total / $per_page);
    
    if ($total_pages <= 1) {
        return '';
    }
    
    $pagination = '<ul class="pagination">';
    
    // Previous button
    if ($current_page > 1) {
        $pagination .= '<li><a href="' . $url . '?page=' . ($current_page - 1) . '">&laquo;</a></li>';
    } else {
        $pagination .= '<li class="disabled"><span>&laquo;</span></li>';
    }
    
    // Page numbers
    for ($i = 1; $i <= $total_pages; $i++) {
        if ($i == $current_page) {
            $pagination .= '<li class="active"><span>' . $i . '</span></li>';
        } else {
            $pagination .= '<li><a href="' . $url . '?page=' . $i . '">' . $i . '</a></li>';
        }
    }
    
    // Next button
    if ($current_page < $total_pages) {
        $pagination .= '<li><a href="' . $url . '?page=' . ($current_page + 1) . '">&raquo;</a></li>';
    } else {
        $pagination .= '<li class="disabled"><span>&raquo;</span></li>';
    }
    
    $pagination .= '</ul>';
    
    return $pagination;
}

// Format price
function formatPrice($price) {
    return number_format($price, 2, '.', ',');
}

// Upload image
function uploadImage($file, $destination) {
    $fileName = time() . '_' . basename($file['name']);
    $targetPath = $destination . $fileName;
    
    // Check if image file is a actual image or fake image
    $check = getimagesize($file['tmp_name']);
    if ($check === false) {
        return false;
    }
    
    // Check file size (limit to 5MB)
    if ($file['size'] > 5000000) {
        return false;
    }
    
    // Allow certain file formats
    $allowedExtensions = ['jpg', 'jpeg', 'png', 'gif'];
    $fileExtension = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    if (!in_array($fileExtension, $allowedExtensions)) {
        return false;
    }
    
    // Upload file
    if (move_uploaded_file($file['tmp_name'], $targetPath)) {
        return $fileName;
    } else {
        return false;
    }
}