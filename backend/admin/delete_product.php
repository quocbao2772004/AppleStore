<?php
session_start();

// Bật error reporting để debug
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

// Đảm bảo trả về JSON
header('Content-Type: application/json');

// Kiểm tra quyền admin
if (!isset($_SESSION['user_id'])) {
    echo json_encode(['success' => false, 'message' => 'Bạn cần đăng nhập với tài khoản admin!']);
    exit();
}

// Kết nối database
$host = 'localhost';
$user = 'root';
$password = 'root'; // Thay bằng mật khẩu MySQL của mày
$database = 'apple_store';

$conn = new mysqli($host, $user, $password, $database);
if ($conn->connect_error) {
    echo json_encode(['success' => false, 'message' => 'Lỗi kết nối database: ' . $conn->connect_error]);
    exit();
}

// Xử lý request POST
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Lấy ID sản phẩm từ query parameter hoặc body
    $id = isset($_GET['id']) ? intval($_GET['id']) : (isset($_POST['id']) ? intval($_POST['id']) : 0);

    // Kiểm tra ID
    if ($id <= 0) {
        echo json_encode(['success' => false, 'message' => 'ID sản phẩm không hợp lệ!']);
        exit();
    }

    // Chuẩn bị câu lệnh SQL để xóa
    $stmt = $conn->prepare("DELETE FROM products WHERE id = ?");
    if (!$stmt) {
        echo json_encode(['success' => false, 'message' => 'Lỗi chuẩn bị câu lệnh SQL: ' . $conn->error]);
        exit();
    }

    // Gán tham số
    $stmt->bind_param("i", $id);

    // Thực thi câu lệnh
    if ($stmt->execute()) {
        if ($stmt->affected_rows > 0) {
            echo json_encode(['success' => true, 'message' => 'Xóa sản phẩm thành công!']);
        } else {
            echo json_encode(['success' => false, 'message' => 'Không tìm thấy sản phẩm với ID này!']);
        }
    } else {
        echo json_encode(['success' => false, 'message' => 'Lỗi khi xóa: ' . $stmt->error]);
    }

    // Đóng statement và kết nối
    $stmt->close();
    $conn->close();
} else {
    echo json_encode(['success' => false, 'message' => 'Phương thức không hợp lệ!']);
}
?>