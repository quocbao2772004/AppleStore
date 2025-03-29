<?php
session_start();
include '../config/fetch_product.php';

if (!isset($_SESSION['user_id']) || !isset($_SESSION['user_email'])) {
    header("Location: login.php");
    exit();
}

$user_id = $_SESSION['user_id'];
$user_email = $_SESSION['user_email'];

$query = "
    SELECT c.product_id, c.quantity, p.name, p.price, p.image
    FROM cart_items c
    JOIN products p ON c.product_id = p.id
    WHERE c.user_id = :user_id
";
$stmt = $pdo->prepare($query);
$stmt->bindParam(':user_id', $user_id, PDO::PARAM_INT);
$stmt->execute();
$cart_items_db = $stmt->fetchAll(PDO::FETCH_ASSOC);

$cart_items = [];
$total = 0;

if ($cart_items_db) {
    foreach ($cart_items_db as $item) {
        $price = (int) str_replace(['VND', '.'], '', $item['price']);
        $subtotal = $price * $item['quantity'];
        $total += $subtotal;

        $cart_items[] = [
            'id' => $item['product_id'],
            'name' => $item['name'],
            'price' => $price,
            'quantity' => $item['quantity'],
            'image' => $item['image']
        ];
    }
}

header('Content-Type: application/json');
echo json_encode([
    'user_id' => $user_id,
    'user_email' => $user_email,
    'cart_items' => $cart_items,
    'total' => $total
]);
exit();
?>