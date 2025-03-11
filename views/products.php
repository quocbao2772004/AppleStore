<?php
include '../config/fetch_product.php'
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sản phẩm - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
</head>
<body>
    <header>
        <div class="logo">Apple Store</div>
        <?php include '../includes/navbar.php'; ?>
    </header>

    <section class="product-page">
        <div class="product-header">
            <h1>Tất cả sản phẩm</h1>
            <div class="filter">
                <select name="category" id="category-filter">
                    <option value="">Danh mục</option>
                    <option value="iphone" <?php echo $category === 'iphone' ? 'selected' : ''; ?>>iPhone</option>
                    <option value="macbook" <?php echo $category === 'macbook' ? 'selected' : ''; ?>>MacBook</option>
                    <option value="ipad" <?php echo $category === 'ipad' ? 'selected' : ''; ?>>iPad</option>
                    <option value="macmini" <?php echo $category === 'macmini' ? 'selected' : ''; ?>>Mac Mini</option>
                    <option value="macstudio" <?php echo $category === 'macstudio' ? 'selected' : ''; ?>>Mac Studio</option>
                </select>
                <select name="sort" id="sort-filter">
                    <option value="">Sắp xếp</option>
                    <option value="price-asc" <?php echo $sort === 'price-asc' ? 'selected' : ''; ?>>Giá tăng dần</option>
                    <option value="price-desc" <?php echo $sort === 'price-desc' ? 'selected' : ''; ?>>Giá giảm dần</option>
                    <option value="name-asc" <?php echo $sort === 'name-asc' ? 'selected' : ''; ?>>Tên A-Z</option>
                </select>
            </div>
        </div>

        <div class="product-list" id="product-list">
            <?php
            if (!empty($products)) {
                foreach ($products as $product) {
                    echo '<div class="product-card">';
                    echo '<div class="product-image"><img src="' . htmlspecialchars($product['image']) . '" alt="' . htmlspecialchars($product['name']) . '"></div>';
                    echo '<div class="product-details">';
                    echo '<h3>' . htmlspecialchars($product['name']) . '</h3>';
                    echo '<p class="price">' . htmlspecialchars($product['price']) . '</p>';
                    echo '<div class="actions">';
                    echo '<a href="details.php?id=' . htmlspecialchars($product['id']) . '" class="buy-btn">Mua ngay</a>';
                    echo 'id = '. $product['id'];
                    echo '<a href="#" class="cart-btn">Thêm vào giỏ</a>';
                    echo '</div>';
                    echo '</div>';
                    echo '</div>';
                }
            } else {
                echo '<p>Không có sản phẩm nào.</p>';
            }
            ?>
        </div>

        <div class="pagination">
            <?php
            if ($total_pages > 1) {
                // Nút "Trước"
                $prev_page = $page > 1 ? $page - 1 : 1;
                echo '<a href="?page=' . $prev_page . '&category=' . urlencode($category) . '&sort=' . urlencode($sort) . '" class="page-link">« Trước</a>';

                // Các số trang
                for ($i = 1; $i <= $total_pages; $i++) {
                    $active = $i === $page ? 'active' : '';
                    echo '<a href="?page=' . $i . '&category=' . urlencode($category) . '&sort=' . urlencode($sort) . '" class="page-link ' . $active . '">' . $i . '</a>';
                }

                // Nút "Sau"
                $next_page = $page < $total_pages ? $page + 1 : $total_pages;
                echo '<a href="?page=' . $next_page . '&category=' . urlencode($category) . '&sort=' . urlencode($sort) . '" class="page-link">Sau »</a>';
            }
            ?>
        </div>
    </section>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

    <script>
        // JavaScript để lọc và sắp xếp
        document.getElementById('category-filter').addEventListener('change', filterProducts);
        document.getElementById('sort-filter').addEventListener('change', filterProducts);

        function filterProducts() {
            const category = document.getElementById('category-filter').value;
            const sort = document.getElementById('sort-filter').value;
            const page = 1; // Quay lại trang 1 khi lọc/sắp xếp
            const url = `?page=${page}&category=${encodeURIComponent(category)}&sort=${encodeURIComponent(sort)}`;

            // Gửi yêu cầu AJAX
            fetch(url)
                .then(response => response.text())
                .then(data => {
                    document.open();
                    document.write(data);
                    document.close();
                })
                .catch(error => console.error('Lỗi:', error));
        }
    </script>
</body>
</html>