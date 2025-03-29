<?php
include '../config/fetch_product.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name = $_POST['name'] ?? '';
    $price = $_POST['price'] ?? '';
    $image = $_POST['image'] ?? '';

    if ($name && $price && $image) {
        try {
            $query = "INSERT INTO products (name, price, image) VALUES (:name, :price, :image)";
            $stmt = $pdo->prepare($query);
            $stmt->execute([
                'name' => $name,
                'price' => $price,
                'image' => $image
            ]);
            echo json_encode(['success' => true]);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => $e->getMessage()]);
        }
    } else {
        echo json_encode(['success' => false, 'message' => 'Vui lòng nhập đầy đủ thông tin']);
    }
}
?>