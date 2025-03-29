<?php
include '../config/fetch_product.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $user_id = $_POST['user_id'] ?? 0;
    $total = $_POST['total'] ?? 0;
    $status = $_POST['status'] ?? 'Pending';

    if ($user_id && $total) {
        try {
            $query = "INSERT INTO orders (user_id, total, status) VALUES (:user_id, :total, :status)";
            $stmt = $pdo->prepare($query);
            $stmt->execute([
                'user_id' => $user_id,
                'total' => $total,
                'status' => $status
            ]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => $e->getMessage()]);
        }
    } else {
        echo json_encode(['success' => false, 'message' => 'Thiếu thông tin đơn hàng']);
    }
}
?>