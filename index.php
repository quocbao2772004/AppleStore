<?php
// Khởi tạo PHP (có thể thêm logic backend sau)
session_start();
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apple Store - Mua sắm sản phẩm chính hãng</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel = "stylesheet" type = "text/css" href = "assets/css/applestyle.css" />
</head>
<body>
    <header>
        <div class="logo">Apple Store</div>
        <nav>
            <a href="index.php">Trang chủ</a>
            <a href="views/products.php">Sản phẩm</a>
            <a href="views/contact.php">Liên hệ</a>
            <a href="views/cart.php">Giỏ hàng</a>
            <a href="views/register.php">Đăng ký</a>
            <a href="views/login.php">Đăng nhập</a>
            <a href="views/chatbot.php" class="chatbot-btn">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-robot" viewBox="0 0 16 16">
                <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.6 26.6 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.93.93 0 0 1-.765.935c-.845.147-2.34.346-4.235.346s-3.39-.2-4.235-.346A.93.93 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a25 25 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25 25 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135"/>
                <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5"/>
            </svg>
                Trợ lý ảo
            </a>
        </nav>
    </header>

    <section class="banner">
        <h1>Khám phá thế giới Apple</h1>
        <p>Các sản phẩm iPhone, iPad, MacBook chính hãng với thiết kế đỉnh cao.</p>
        <a href="#san-pham" class="btn">Mua ngay</a>
    </section>

    <section class="products" id="san-pham">
        <?php
        // Dữ liệu sản phẩm mẫu (có thể thay bằng truy vấn CSDL)
        $products = [
            ['name' => 'iPhone', 'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/iphone-15-pro-finish-select-202309-6-1inch-blacktitanium'],
            ['name' => 'MacBook Pro', 'image' => 'assets/images/mac/0022672_macbook-pro-16-inch-m3-pro-2023-36gb-ram-18-core-gpu-512gb-ssd_240.jpeg'],
            ['name' => 'Mac Mini', 'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mac-mini-hero-202301?wid=904&hei=840&fmt=jpeg&qlt=90&.v=1670036721985'],
            ['name' => 'Mac Studio', 'image' => 'https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/mac-studio-select-202306?wid=904&hei=840&fmt=jpeg&qlt=90&.v=1683748525359']
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

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>
</body>
</html>