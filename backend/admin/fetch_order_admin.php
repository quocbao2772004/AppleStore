<?php
include '../config/config.php';

header('Content-Type: application/json');

try {
    $query = "SELECT o.id, u.email AS user_email, o.total, o.status, o.order_date AS created_at 
              FROM orders o 
              JOIN users u ON o.user_id = u.id";
    $stmt = $pdo->prepare($query);
    $stmt->execute();
    $orders = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($orders); 
} catch (PDOException $e) {
    echo json_encode([
        'error' => true,
        'message' => 'Lỗi truy vấn database: ' . $e->getMessage()
    ]);
}
?>