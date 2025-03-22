<?php
session_start();

// Xóa tất cả dữ liệu session
unset($_SESSION['user_id']);
unset($_SESSION['user_email']); // Nếu có lưu email
session_destroy();

// Chuyển hướng về trang chủ hoặc trang đăng nhập
header("Location: login.php");
exit();
?>