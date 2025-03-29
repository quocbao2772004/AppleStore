<?php
session_start();
include '../../backend/config/fetch_product.php';

if (!isset($_SESSION['user_id'])) 
{
    $login_message = "Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng.";
}


if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_to_cart'])) 
{
    if (!isset($_SESSION['user_id'])) 
    {
        header("Location: login_form.php");
        exit();
    }

    $user_id = $_SESSION['user_id'];
    $product_id = (int)$_POST['product_id'];
    $quantity = 1; 

    try {
        $check_query = "SELECT id, quantity FROM cart_items WHERE user_id = :user_id AND product_id = :product_id";
        $check_stmt = $pdo->prepare($check_query);
        $check_stmt->execute(['user_id' => $user_id, 'product_id' => $product_id]);
        $cart_item = $check_stmt->fetch(PDO::FETCH_ASSOC);

        if ($cart_item) 
        {
            $new_quantity = $cart_item['quantity'] + $quantity;
            $update_query = "UPDATE cart_items SET quantity = :quantity WHERE id = :id";
            $update_stmt = $pdo->prepare($update_query);
            $update_stmt->execute(['quantity' => $new_quantity, 'id' => $cart_item['id']]);
        } else {
            $insert_query = "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (:user_id, :product_id, :quantity)";
            $insert_stmt = $pdo->prepare($insert_query);
            $insert_stmt->execute(['user_id' => $user_id, 'product_id' => $product_id, 'quantity' => $quantity]);
        }

        header("Location: cart.php"); 
        exit();
    } catch (PDOException $e) {
        echo "Lỗi: " . $e->getMessage();
    }
}

$category = isset($_GET['category']) ? $_GET['category'] : '';
$sort = isset($_GET['sort']) ? $_GET['sort'] : '';
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$items_per_page = 10; 

$sql = "SELECT * FROM products WHERE 1=1";
$params = [];

if ($category) 
{
    $sql .= " AND category = :category";
    $params[':category'] = $category;
}

if ($sort) 
{
    switch ($sort) 
    {
        case 'price-asc':
            $sql .= " ORDER BY CAST(REPLACE(REPLACE(price, '.', ''), ' VND', '') AS DECIMAL) ASC";
            break;
        case 'price-desc':
            $sql .= " ORDER BY CAST(REPLACE(REPLACE(price, '.', ''), ' VND', '') AS DECIMAL) DESC";
            break;
        case 'name-asc':
            $sql .= " ORDER BY name ASC";
            break;
    }
}

$total_items_query = "SELECT COUNT(*) FROM products WHERE 1=1" . ($category ? " AND category = :category" : "");
$total_stmt = $pdo->prepare($total_items_query);
if ($category) {
    $total_stmt->bindParam(':category', $category);
}
$total_stmt->execute();
$total_items = $total_stmt->fetchColumn();
$total_pages = ceil($total_items / $items_per_page);

$offset = ($page - 1) * $items_per_page;
$sql .= " LIMIT :offset, :limit";
$stmt = $pdo->prepare($sql);
if ($category) {
    $stmt->bindParam(':category', $category);
}
$stmt->bindParam(':offset', $offset, PDO::PARAM_INT);
$stmt->bindParam(':limit', $items_per_page, PDO::PARAM_INT);
$stmt->execute();
$products = $stmt->fetchAll(PDO::FETCH_ASSOC);
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
    <?php include '../includes/header.php'; ?>
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
                    <option value = "watch" <?php echo $category === 'watch' ? 'selected' : ''; ?>>Apple Watch</option>
                    <option value = "case" <?php echo $category === 'case' ? 'selected' : ''; ?>>Case</option>
                    <option value = "airpod" <?php echo $category === 'airpod' ? 'selected' : ''; ?>>AirPods</option>
                </select>
                <select name="sort" id="sort-filter">
                    <option value="">Sắp xếp</option>
                    <option value="price-asc" <?php echo $sort === 'price-asc' ? 'selected' : ''; ?>>Giá tăng dần</option>
                    <option value="price-desc" <?php echo $sort === 'price-desc' ? 'selected' : ''; ?>>Giá giảm dần</option>
                    <option value="name-asc" <?php echo $sort === 'name-asc' ? 'selected' : ''; ?>>Tên A-Z</option>
                </select>
            </div>
        </div>

        <?php if (isset($login_message)): ?>
            <p style="color: red;"><?php echo $login_message; ?></p>
        <?php endif; ?>

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
                    echo '<form method="POST" action="">';
                    echo '<input type="hidden" name="product_id" value="' . htmlspecialchars($product['id']) . '">';
                    echo '<input type="hidden" name="add_to_cart" value="1">';
                    echo '<button type="submit" class="cart-btn">Thêm vào giỏ</button>';
                    echo '</form>';
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
                $prev_page = $page > 1 ? $page - 1 : 1;
                echo '<a href="?page=' . $prev_page . '&category=' . urlencode($category) . '&sort=' . urlencode($sort) . '" class="page-link">« Trước</a>';

                for ($i = 1; $i <= $total_pages; $i++) {
                    $active = $i === $page ? 'active' : '';
                    echo '<a href="?page=' . $i . '&category=' . urlencode($category) . '&sort=' . urlencode($sort) . '" class="page-link ' . $active . '">' . $i . '</a>';
                }

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
        document.getElementById('category-filter').addEventListener('change', filterProducts);
        document.getElementById('sort-filter').addEventListener('change', filterProducts);

        function filterProducts() {
            const category = document.getElementById('category-filter').value;
            const sort = document.getElementById('sort-filter').value;
            const page = 1;
            const url = `?page=${page}&category=${encodeURIComponent(category)}&sort=${encodeURIComponent(sort)}`;

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