<?php
session_start();
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giỏ hàng - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
    <link rel="stylesheet" type="text/css" href="../assets/css/cart.css" />
</head>
<body>
    <?php include '../includes/header.php'; ?>

    <section class="cart-page">
        <div class="cart-header">
            <h1>Giỏ hàng của bạn</h1>
            <p id="cart-count"></p>
        </div>

        <div class="cart-content" id="cart-content" style="display: none;">
            <div class="cart-items" id="cart-items"></div>
            <div class="cart-summary">
                <h3>Tóm tắt đơn hàng</h3>
                <div class="summary-details">
                    <p>Tổng tiền hàng: <span id="subtotal"></span></p>
                    <p>Phí vận chuyển: <span>Miễn phí</span></p>
                    <p class="total">Tổng cộng: <span id="total"></span></p>
                </div>
                <button id="checkout-btn" class="checkout-btn">Thanh toán</button>
            </div>
        </div>

        <div class="empty-cart" id="empty-cart" style="display: none;">
            <p>Chưa có sản phẩm nào trong giỏ hàng.</p>
            <a href="products.php" class="continue-shopping">Tiếp tục mua sắm</a>
        </div>
    </section>

    <div id="qrModal" class="modal">
        <div class="modal-content">
            <span class="close">×</span>
            <h2>Thanh Toán Đơn Hàng</h2>
            <div id="modal-qr-code"></div>
            <div class="modal-footer">
                <p>Quét mã QR bằng ứng dụng MB Bank để thanh toán</p>
            </div>
            <div class="modal-actions">
                <button class="confirm-btn" id="confirm-btn">Xác nhận</button>
                <button class="cancel-btn" id="cancel-btn">Hủy</button>
            </div>
        </div>
    </div>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

    <script src="../assets/js/cart.js"></script>
</body>
</html>