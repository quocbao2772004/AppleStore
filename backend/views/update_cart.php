<?php
session_start();
include '../config/fetch_product.php';

if (!isset($_SESSION['user_id'])) {
    echo json_encode(['success' => false, 'message' => 'Chưa đăng nhập']);
    exit();
}

$user_id = $_SESSION['user_id'];
$product_id = (int) $_POST['product_id'];
$quantity = (int) $_POST['quantity'];

$query = "UPDATE cart_items SET quantity = :quantity WHERE user_id = :user_id AND product_id = :product_id";
$stmt = $pdo->prepare($query);
$stmt->execute(['quantity' => $quantity, 'user_id' => $user_id, 'product_id' => $product_id]);

echo json_encode(['success' => true]);
?>