<?php
session_start();
include '../../backend/config/fetch_product.php';

if (!isset($pdo)) {
    $host = 'localhost';
    $dbname = 'apple_store';
    $username = 'root';
    $password = '';
    try {
        $pdo = new PDO("mysql:host=$host;dbname=$dbname", $username, $password);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Kết nối thất bại: ' . $e->getMessage()]);
        exit;
    }
}

if (!isset($_SESSION['user_id']) || !isset($_SESSION['user_email'])) {
    http_response_code(401);
    echo json_encode(['error' => 'Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng.']);
    exit;
}

$user_id = $_SESSION['user_id'];
$user_email = $_SESSION['user_email'];
$product_id = isset($_GET['id']) ? (int)$_GET['id'] : 0;

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_to_cart'])) {
    $quantity = isset($_POST['quantity']) ? (int)$_POST['quantity'] : 1;

    try {
        $query = "SELECT * FROM products WHERE id = :id";
        $stmt = $pdo->prepare($query);
        $stmt->bindParam(':id', $product_id, PDO::PARAM_INT);
        $stmt->execute();
        $product = $stmt->fetch(PDO::FETCH_ASSOC);

        if ($product) {
            $check_query = "SELECT id, quantity FROM cart_items WHERE user_id = :user_id AND product_id = :product_id";
            $check_stmt = $pdo->prepare($check_query);
            $check_stmt->execute(['user_id' => $user_id, 'product_id' => $product_id]);
            $cart_item = $check_stmt->fetch(PDO::FETCH_ASSOC);

            if ($cart_item) {
                $new_quantity = $cart_item['quantity'] + $quantity;
                $update_query = "UPDATE cart_items SET quantity = :quantity WHERE id = :id";
                $update_stmt = $pdo->prepare($update_query);
                $update_stmt->execute(['quantity' => $new_quantity, 'id' => $cart_item['id']]);
            } else {
                $insert_query = "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (:user_id, :product_id, :quantity)";
                $insert_stmt = $pdo->prepare($insert_query);
                $insert_stmt->execute(['user_id' => $user_id, 'product_id' => $product_id, 'quantity' => $quantity]);
            }
            echo json_encode(['success' => true, 'redirect' => '../../frontend/views/cart.php']);
        } else {
            echo json_encode(['error' => 'Sản phẩm không tồn tại.']);
        }
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Lỗi: ' . $e->getMessage()]);
    }
    exit;
}

try {
    $query = "SELECT * FROM products WHERE id = :id";
    $stmt = $pdo->prepare($query);
    $stmt->bindParam(':id', $product_id, PDO::PARAM_INT);
    $stmt->execute();
    $product = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($product) {
        header('Content-Type: application/json');
        echo json_encode([
            'success' => true,
            'product' => $product,
            'user_email' => $user_email
        ]);
    } else {
        http_response_code(404);
        echo json_encode(['error' => 'Sản phẩm không tồn tại.']);
    }
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Lỗi: ' . $e->getMessage()]);
}
exit;
?>