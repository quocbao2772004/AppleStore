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

// Lấy ID sản phẩm từ query parameter
$id = isset($_GET['id']) ? intval($_GET['id']) : 0;
if ($id <= 0) {
    echo json_encode(['success' => false, 'message' => 'ID sản phẩm không hợp lệ!']);
    exit();
}

// Truy vấn sản phẩm
$stmt = $conn->prepare("SELECT id, name, price, image, category, quantity FROM products WHERE id = ?");
if (!$stmt) {
    echo json_encode(['success' => false, 'message' => 'Lỗi chuẩn bị câu lệnh SQL: ' . $conn->error]);
    exit();
}

$stmt->bind_param("i", $id);
$stmt->execute();
$result = $stmt->get_result();

if ($result->num_rows > 0) {
    $product = $result->fetch_assoc();
    // Đảm bảo price là chuỗi
    $product['price'] = (string)$product['price'];
    echo json_encode($product);
} else {
    echo json_encode(['success' => false, 'message' => 'Không tìm thấy sản phẩm!']);
}

$stmt->close();
$conn->close();
?>