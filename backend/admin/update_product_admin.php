<?php
include '../config/fetch_product.php';

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = $_POST['id'] ?? 0;
    $name = $_POST['name'] ?? '';
    $price = $_POST['price'] ?? '';
    $image = $_POST['image'] ?? '';

    if ($id && $name && $price && $image) {
        try {
            $query = "UPDATE products SET name = :name, price = :price, image = :image WHERE id = :id";
            $stmt = $pdo->prepare($query);
            $stmt->execute([
                'id' => $id,
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