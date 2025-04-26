<?php
session_start();
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="product-title">Sản phẩm - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css?v=1" />
    <link rel="stylesheet" type="text/css" href="../assets/css/product_detail.css?v=1" />
</head>
<body>
    <?php include '../includes/header.php'; ?>

    <section class="product-detail-page">
        <div class="container">
            <div class="product-gallery">
                <div class="main-image">
                    <img id="product-image" src="" alt="">
                </div>
            </div>
            <div class="product-info">
                <h1 id="product-name"></h1>
                <div class="rating">
                    ★★★★★ <span>(Đánh giá | 100)</span>
                </div>
                <div class="price">
                    <span class="current-price" id="product-price"></span>
                </div>
                <div class="options">
                    <div class="option">
                        <label>Dung lượng:</label>
                        <select name="capacity" id="capacity">
                            <option value="128GB">128GB</option>
                            <option value="256GB">256GB</option>
                            <option value="512GB">512GB</option>
                        </select>
                    </div>
                    <div class="option">
                        <label>Màu sắc:</label>
                        <div class="color-options">
                            <span class="color black"></span>
                            <span class="color silver"></span>
                        </div>
                    </div>
                </div>
                <div class="shipping-info">
                    <p><strong>Ưu đãi:</strong> (Ưu đãi đến ngày 25/03/2025)</p>
                    <ul>
                        <li><span class="check">✔</span> Giảm ngay 400.000đ khi thanh toán qua ZaloPay/SL co hạn</li>
                        <li><span class="check">✔</span> Tặng ngay Sony mua kèm giảm 15% (đến 1.000.000đ)</li>
                        <li><span class="check">✔</span> Mua combo với Non Apple giảm 200.000đ</li>
                        <li><span class="error">✖</span> Ưu đãi không áp dụng cho đơn hàng đã hoàn thành</li>
                    </ul>
                </div>
                <div class="actions">
                    <form id="buy-form" method="POST">
                        <input type="hidden" name="product_id" id="product-id">
                        <input type="number" name="quantity" id="quantity" value="1" min="1" style="width: 60px; padding: 5px; margin-right: 10px;">
                        <button type="submit" name="buy_now" class="buy-btn">MUA NGAY</button>
                        <button type="submit" name="add_to_cart" class="cart-btn">Thêm vào giỏ</button>
                    </form>
                </div>
                <div class="payment-options">
                    <p>Trả góp 0% qua thẻ Visa, Mastercard, JCB, Amex</p>
                    <p>Thử đổi mới</p>
                </div>
                <div class="additional-info">
                    <p><strong>Bảo hành:</strong> 12 tháng, 1 đổi 1 trong 30 ngày nếu lỗi do NSX</p>
                </div>
            </div>
        </div>

        <div class="product-promo-image">
            <img src="https://shopdunk.com/images/uploaded/gi%C3%A1%20iphone%2016/iPhone_16e_Non-AI_Feb25_Product_Page_L__VN-VI.jpg" alt="iPhone 16e Non-AI Promo">
        </div>
    </section>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

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

    <script src="../assets/js/product_detail.js"></script>
</body>
</html>