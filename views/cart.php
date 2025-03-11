<?php
session_start();

// Dữ liệu giỏ hàng mẫu (có thể thay bằng dữ liệu từ session hoặc CSDL)
$cart_items = [
    [
        'name' => 'iPhone 15 Pro',
        'price' => 29990000,
        'quantity' => 1,
        'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-15-pro-finish-select-202309-6-1inch-blacktitanium?wid=2560&hei=1440&fmt=jpeg&qlt=95&.v=1692846361359'
    ],
    [
        'name' => 'Apple Watch Ultra 2',
        'price' => 18990000,
        'quantity' => 2,
        'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/MT5F3ref_VW_34FR+watch-49-titanium-ultra2_VW_34FR+watch-face-49-trail-ultra2_VW_34FR?wid=820&hei=498&fmt=jpeg&qlt=95&.v=1694507276769'
    ]
];
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giỏ hàng - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
    <style>
            footer 
            {
            position: fixed
            
            }
    </style>
</head>
<body>
    <header>
        <div class="logo">Apple Store</div>
        <?php include '../includes/navbar.php'; ?>
    </header>

    <section class="cart-page">
        <div class="cart-header">
            <h1>Giỏ hàng của bạn</h1>
            <p>
                <?php echo count($cart_items) > 0 ? "Bạn có " . count($cart_items) . " sản phẩm trong giỏ." : "Giỏ hàng của bạn đang trống."; ?>
            </p>
        </div>

        <?php if (count($cart_items) > 0): ?>
            <div class="cart-content">
                <div class="cart-items">
                    <?php
                    $total = 0;
                    foreach ($cart_items as $item) {
                        $subtotal = $item['price'] * $item['quantity'];
                        $total += $subtotal;
                        echo '<div class="cart-item">';
                        echo '<img src="' . $item['image'] . '" alt="' . $item['name'] . '">';
                        echo '<div class="item-details">';
                        echo '<h3>' . $item['name'] . '</h3>';
                        echo '<p class="price">' . number_format($item['price'], 0, ',', '.') . ' VNĐ</p>';
                        echo '<div class="quantity">';
                        echo '<button class="qty-btn minus">-</button>';
                        echo '<input type="number" value="' . $item['quantity'] . '" min="1">';
                        echo '<button class="qty-btn plus">+</button>';
                        echo '</div>';
                        echo '</div>';
                        echo '<div class="item-subtotal">' . number_format($subtotal, 0, ',', '.') . ' VNĐ</div>';
                        echo '<a href="#" class="remove-btn">Xóa</a>';
                        echo '</div>';
                    }
                    ?>
                </div>

                <div class="cart-summary">
                    <h3>Tóm tắt đơn hàng</h3>
                    <div class="summary-details">
                        <p>Tổng tiền hàng: <span><?php echo number_format($total, 0, ',', '.') . ' VNĐ'; ?></span></p>
                        <p>Phí vận chuyển: <span>Miễn phí</span></p>
                        <p class="total">Tổng cộng: <span><?php echo number_format($total, 0, ',', '.') . ' VNĐ'; ?></span></p>
                    </div>
                    <a href="#" class="checkout-btn">Thanh toán</a>
                </div>
            </div>
        <?php else: ?>
            <div class="empty-cart">
                <p>Chưa có sản phẩm nào trong giỏ hàng.</p>
                <a href="products.php" class="continue-shopping">Tiếp tục mua sắm</a>
            </div>
        <?php endif; ?>
    </section>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>
</body>
</html>