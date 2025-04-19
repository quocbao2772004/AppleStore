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

if (!isset($_SESSION['user_id'])) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => 'Vui lòng đăng nhập để xóa giỏ hàng.']);
    exit;
}

$user_id = $_SESSION['user_id'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        $query = "DELETE FROM cart_items WHERE user_id = :user_id";
        $stmt = $pdo->prepare($query);
        $stmt->execute(['user_id' => $user_id]);

        echo json_encode(['success' => true]);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['success' => false, 'message' => 'Lỗi khi xóa giỏ hàng: ' . $e->getMessage()]);
    }
    exit;
}

http_response_code(405);
echo json_encode(['success' => false, 'message' => 'Phương thức không được hỗ trợ.']);
exit;
?>