<?php
include '../config/fetch_product.php';
header('Content-Type: application/json');

// Lấy dữ liệu từ request
$user_email = $_POST['user_email'];
$total = $_POST['total'];
$cart_items = json_decode($_POST['cart_items'], true);

// Lấy user_id từ email
$sql = "SELECT id FROM users WHERE email = ?";
$stmt = $conn->prepare($sql);
$stmt->bind_param("s", $user_email);
$stmt->execute();
$result = $stmt->get_result();

if ($result->num_rows === 0) {
    echo json_encode(['success' => false, 'message' => 'Không tìm thấy người dùng với email này']);
    exit;
}

$user = $result->fetch_assoc();
$user_id = $user['id'];

// Lưu đơn hàng vào bảng orders
$sql = "INSERT INTO orders (user_id, email, total, order_date, status) VALUES (?, ?, ?, NOW(), 'completed')";
$stmt = $conn->prepare($sql);
$stmt->bind_param("iss", $user_id, $user_email, $total);

if ($stmt->execute()) {
    $order_id = $stmt->insert_id;

    // Cập nhật số lượng sản phẩm trong bảng products
    foreach ($cart_items as $item) {
        $product_id = $item['id'];
        $quantity = $item['quantity'];

        $update_sql = "UPDATE products SET quantity = quantity - ? WHERE id = ?";
        $update_stmt = $conn->prepare($update_sql);
        $update_stmt->bind_param("ii", $quantity, $product_id);
        $update_stmt->execute();
    }

    echo json_encode(['success' => true, 'order_id' => $order_id]);
} else {
    echo json_encode(['success' => false, 'message' => 'Lưu đơn hàng thất bại: ' . $stmt->error]);
}

$stmt->close();
$conn->close();
?>