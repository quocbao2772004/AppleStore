<?php
session_start();
include '../config/fetch_product.php';

if (!isset($_SESSION['user_id'])) {
    header("Location: login.php");
    exit();
}

$user_id = $_SESSION['user_id'];
$product_id = (int) $_GET['id'];

$query = "DELETE FROM cart_items WHERE user_id = :user_id AND product_id = :product_id";
$stmt = $pdo->prepare($query);
$stmt->execute(['user_id' => $user_id, 'product_id' => $product_id]);

header("Location: ../../frontend/views/cart.php");
exit();
?>