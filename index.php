<?php
session_start();
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apple Store - Mua sắm sản phẩm chính hãng</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="frontend/assets/css/applestyle.css" />
    <link rel="stylesheet" type="text/css" href="frontend/assets/css/index_file.css" />
</head>
<body>
    <?php include 'frontend/includes/header_index.php'; ?>

    <section class="banner">
        <h1>Khám phá thế giới Apple</h1>
        <p>Các sản phẩm iPhone, iPad, MacBook chính hãng với thiết kế đỉnh cao.</p>
        <a href="#san-pham" class="btn">Mua ngay</a>
    </section>

    <section class="products" id="san-pham">
        <?php
        $products = [
            ['name' => 'iPhone', 'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-15-pro-finish-select-202309-6-1inch-blacktitanium'],
            ['name' => 'MacBook Pro', 'image' => 'frontend/assets/images/mac/0022672_macbook-pro-16-inch-m3-pro-2023-36gb-ram-18-core-gpu-512gb-ssd_240.jpeg'],
            ['name' => 'Mac Mini', 'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mac-mini-hero-202301?wid=904&hei=840&fmt=jpeg&qlt=90&.v=1670036721985'],
            ['name' => 'Mac Studio', 'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mac-studio-select-202306?wid=904&hei=840&fmt=jpeg&qlt=90&.v=1683748525359'],
            ['name' => 'AirPods', 'image' => 'frontend/assets/images/airpods.png'],
            ['name' => 'Apple Watch', 'image' => 'frontend/assets/images/applewatch.png'],
            
        ];

        foreach ($products as $product) {
            echo '<div class="product-item">';
            echo '<img src="' . $product['image'] . '" alt="' . $product['name'] . '">';
            echo '<h3>' . $product['name'] . '</h3>';
            echo '<p>Sản phẩm chính hãng Apple</p>';
            echo '</div>';
        }
        ?>
    </section>

    <section class="promo-section">
        <div class="promo-item">
            <img src="frontend/assets/images/home/airpods.png" alt="AirPods Pro">
        </div>
        <div class="promo-item">
            <img src="frontend/assets/images/home/applecard.png" alt="Apple Card">
        </div>
        <div class="promo-item">
            <img src="frontend/assets/images/home/applewatch.png" alt="Apple Watch Series 10">
        </div>
        <div class="promo-item">
            <img src="frontend/assets/images/home/Ipad.png" alt="IPad">
        </div>
        <div class="promo-item">
            <img src="frontend/assets/images/home/iphonefamily.png" alt="IPhone family">
        </div>
        <div class="promo-item">
            <img src="frontend/assets/images/home/iphonetradein.png" alt="IPhone tradein">
        </div>
    </section>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>
</body>
</html>