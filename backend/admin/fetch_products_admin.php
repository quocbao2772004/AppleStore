<?php
include '../config/fetch_product.php';

header('Content-Type: application/json');

try {
    $query = "SELECT * FROM products";
    $stmt = $pdo->prepare($query);
    $stmt->execute();
    $products = $stmt->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($products);
} catch (PDOException $e) {
    echo json_encode(['success' => false, 'message' => $e->getMessage()]);
}
?>