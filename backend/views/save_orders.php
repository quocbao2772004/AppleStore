<?php
session_start();
include '../config/fetch_product.php';

header('Content-Type: application/json');

if (!isset($pdo)) {
    $host = 'localhost';
    $dbname = 'apple_store';
    $username = 'root';
    $password = 'root';
    try {
        $pdo = new PDO("mysql:host=$host;dbname=$dbname", $username, $password);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Kết nối thất bại: ' . $e->getMessage()]);
        exit;
    }
}

if (!isset($_SESSION['user_id']) || !isset($_SESSION['user_email'])) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => 'Vui lòng đăng nhập để xử lý đơn hàng.']);
    exit;
}

$user_id = $_SESSION['user_id'];
$user_email = $_SESSION['user_email'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = $_POST['user_email'] ?? $user_email;
    $total = floatval($_POST['total']);
    $cart_items = json_decode($_POST['cart_items'], true);

    if (!$email || !$total || empty($cart_items)) {
        http_response_code(400);
        echo json_encode(['success' => false, 'message' => 'Dữ liệu không hợp lệ.']);
        exit;
    }

    try {
        // Lưu vào bảng orders
        $query = "INSERT INTO orders (user_id, email, total, status) VALUES (:user_id, :email, :total, 'completed')";
        $stmt = $pdo->prepare($query);
        $stmt->execute([
            'user_id' => $user_id,
            'email' => $email,
            'total' => $total
        ]);

        echo json_encode(['success' => true]);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Lỗi khi lưu đơn hàng: ' . $e->getMessage()]);
    }
    exit;
}

http_response_code(405);
echo json_encode(['success' => false, 'message' => 'Phương thức không được hỗ trợ.']);
exit;
?>