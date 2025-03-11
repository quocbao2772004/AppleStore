<?php
include '../config/fetch_product.php';

// Lấy ID sản phẩm từ URL
$product_id = isset($_GET['id']) ? (int)$_GET['id'] : 0;

try {
    $query = "SELECT * FROM products WHERE id = :id";
    $stmt = $pdo->prepare($query);
    $stmt->bindParam(':id', $product_id, PDO::PARAM_INT);
    $stmt->execute();
    $product = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$product) {
        die("Sản phẩm không tồn tại.");
    }
} catch (PDOException $e) {
    echo '<p>Lỗi: ' . $e->getMessage() . '</p>';
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($product['name']); ?> - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
</head>
<body>
    <header>
        <div class="logo">Apple Store</div>
        <?php include '../includes/navbar.php'; ?>
    </header>

    <section class="product-detail-page">
        <div class="container">
            <div class="product-gallery">
                <div class="main-image">
                    <img src="<?php echo htmlspecialchars($product['image']); ?>" alt="<?php echo htmlspecialchars($product['name']); ?>">
                </div>
                <div class="thumbnail-gallery">
                    <img src="<?php echo htmlspecialchars($product['image']); ?>" alt="Thumbnail 1">
                    <img src="<?php echo htmlspecialchars($product['image']); ?>" alt="Thumbnail 2">
                    <img src="<?php echo htmlspecialchars($product['image']); ?>" alt="Thumbnail 3">
                    <img src="<?php echo htmlspecialchars($product['image']); ?>" alt="Thumbnail 4">
                </div>
            </div>
            <div class="product-info">
                <h1><?php echo htmlspecialchars($product['name']); ?></h1>
                <div class="rating">
                    ★★★★★ <span>(Đánh giá | 100)</span>
                </div>
                <div class="price">
                    <span class="current-price"><?php echo htmlspecialchars($product['price']); ?></span>
                    <span class="original-price">(16.690.000đ)</span>
                </div>
                <div class="options">
                    <div class="option">
                        <label>Dung lượng:</label>
                        <select>
                            <option>128GB</option>
                            <option>256GB</option>
                            <option>512GB</option>
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
                    <a href="#" class="buy-now-btn">MUA NGAY</a>
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
</body>
</html>