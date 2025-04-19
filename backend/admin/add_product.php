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
    // Lấy dữ liệu từ form
    $name = isset($_POST['name']) ? trim($_POST['name']) : '';
    $price = isset($_POST['price']) ? trim($_POST['price']) : '';
    $image = isset($_POST['image']) ? trim($_POST['image']) : '';
    $category = isset($_POST['category']) ? trim($_POST['category']) : '';
    $quantity = isset($_POST['quantity']) ? intval($_POST['quantity']) : 0;

    // Kiểm tra dữ liệu đầu vào
    if (empty($name)) {
        echo json_encode(['success' => false, 'message' => 'Tên sản phẩm không được để trống!']);
        exit();
    }
    if (empty($price)) {
        echo json_encode(['success' => false, 'message' => 'Giá không được để trống!']);
        exit();
    }
    // Validate price format (ví dụ: 30.990.000 hoặc 30.990.000 VND)
    if (!preg_match('/^\d{1,3}(\.\d{3})*(\sVND)?$/', $price)) {
        echo json_encode(['success' => false, 'message' => 'Giá phải có định dạng như 30.990.000 hoặc 30.990.000 VND!']);
        exit();
    }
    if (empty($image)) {
        echo json_encode(['success' => false, 'message' => 'URL hình ảnh không được để trống!']);
        exit();
    }
    if (empty($category)) {
        echo json_encode(['success' => false, 'message' => 'Loại sản phẩm không được để trống!']);
        exit();
    }
    if ($quantity < 0) {
        echo json_encode(['success' => false, 'message' => 'Số lượng không được âm!']);
        exit();
    }

    // Chuẩn bị câu lệnh SQL để chèn
    $stmt = $conn->prepare("INSERT INTO products (name, price, image, category, quantity) VALUES (?, ?, ?, ?, ?)");
    if (!$stmt) {
        echo json_encode(['success' => false, 'message' => 'Lỗi chuẩn bị câu lệnh SQL: ' . $conn->error]);
        exit();
    }

    // Gán tham số (price là string)
    $stmt->bind_param("ssssi", $name, $price, $image, $category, $quantity);

    // Thực thi câu lệnh
    if ($stmt->execute()) {
        echo json_encode(['success' => true, 'message' => 'Thêm sản phẩm thành công!']);
    } else {
        echo json_encode(['success' => false, 'message' => 'Lỗi khi thêm sản phẩm: ' . $stmt->error]);
    }

    // Đóng statement và kết nối
    $stmt->close();
    $conn->close();
} else {
    echo json_encode(['success' => false, 'message' => 'Phương thức không hợp lệ!']);
}
?>