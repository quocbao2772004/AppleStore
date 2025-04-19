<?php
session_start();

if (!isset($_SESSION['user_id'])) {
    header("Location: login.php");
    exit();
}

$user_email = $_SESSION['user_email'];
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css" integrity="sha512-Kc323vGBEqzTmouAECnVceyQqyqdsSiqLQISBL29aUW4U/M7pSPA/gEUZQqv1cwx4OnYxTxve5UMg5GT6L4JJg==" crossorigin="anonymous" referrerpolicy="no-referrer" />
    <link rel="stylesheet" type="text/css" href="../assets/css/admin.css">
</head>
<body>
    <!-- Sidebar -->
    <div class="sidebar">
        <h2>Admin Panel</h2>
        <ul>
            <li><a href="#products" class="nav-link active">Sản phẩm</a></li>
            <li><a href="#orders" class="nav-link">Đơn hàng</a></li>
            <li><a href="#users" class="nav-link">Người dùng</a></li>
            <li><a href="logout.php">Đăng xuất</a></li>
        </ul>
    </div>

    <!-- Header -->
    <div class="header">
        <h1>Quản lý</h1>
        <div class="admin-info">
            Admin: <?php echo htmlspecialchars($user_email); ?>
        </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
        <!-- Quản lý sản phẩm -->
        <div id="products" class="section active">
            <h2>Quản lý sản phẩm</h2>
            <div class="form-container">
                <h3>Thêm sản phẩm mới</h3>
                <form id="add-product-form">
                    <label for="product-name">Tên sản phẩm</label>
                    <input type="text" id="product-name" name="name" required>

                    <label for="product-price">Giá (VD: 30.990.000 VND)</label>
                    <input type="text" id="product-price" name="price" required pattern="\d{1,3}(\.\d{3})*(\sVND)?$" title="Giá phải có định dạng như 30.990.000 hoặc 30.990.000 VND">

                    <label for="product-image">URL hình ảnh</label>
                    <input type="text" id="product-image" name="image" required>

                    <label for="product-category">Loại sản phẩm</label>
                    <input type="text" id="product-category" name="category" required>

                    <label for="product-quantity">Số lượng</label>
                    <input type="number" id="product-quantity" name="quantity" required min="0">
                    <button type="submit">Thêm sản phẩm</button>
                </form>
            </div>

            <table id="product-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Hình ảnh</th>
                        <th>Tên</th>
                        <th>Giá</th>
                        <th>Phân loại</th>
                        <th>Số lượng</th>
                        <th>Hành động</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Dữ liệu sẽ được thêm bằng JavaScript -->
                </tbody>
            </table>
        </div>

        <!-- Quản lý đơn hàng -->
        <div id="orders" class="section">
            <h2>Quản lý đơn hàng</h2>
            <table id="order-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Người dùng</th>
                        <th>Tổng tiền</th>
                        <th>Trạng thái</th>
                        <th>Ngày đặt</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Dữ liệu sẽ được thêm bằng JavaScript -->
                </tbody>
            </table>
        </div>

        <!-- Quản lý người dùng -->
        <div id="users" class="section">
            <h2>Quản lý người dùng</h2>
            <table id="user-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Email</th>
                        <th>Ngày đăng ký</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Dữ liệu sẽ được thêm bằng JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <!-- Modal chỉnh sửa sản phẩm -->
    <div id="edit-product-modal" class="modal">
        <div class="modal-content">
            <span class="close-btn">×</span>
            <h2>Chỉnh sửa sản phẩm</h2>
            <form id="edit-product-form">
                <input type="hidden" id="edit-product-id" name="id">
                <div class="form-group">
                    <label for="edit-product-name">Tên sản phẩm</label>
                    <input type="text" id="edit-product-name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="edit-product-price">Giá (VD: 30.990.000 VND)</label>
                    <input type="text" id="edit-product-price" name="price" required pattern="\d{1,3}(\.\d{3})*(\sVND)?$" title="Giá phải có định dạng như 30.990.000 hoặc 30.990.000 VND">
                </div>
                <div class="form-group">
                    <label for="edit-product-image">URL hình ảnh</label>
                    <input type="text" id="edit-product-image" name="image" required>
                </div>
                <div class="form-group">
                    <label for="edit-product-category">Loại sản phẩm</label>
                    <input type="text" id="edit-product-category" name="category" required>
                </div>
                <div class="form-group">
                    <label for="edit-product-quantity">Số lượng</label>
                    <input type="number" id="edit-product-quantity" name="quantity" required min="0">
                </div>
                <div class="modal-actions">
                    <button type="submit" class="save-btn">Lưu</button>
                    <button type="button" class="cancel-btn">Hủy</button>
                </div>
            </form>
        </div>
    </div>

    <script src="../assets/js/navigation.js"></script>
    <script src="../assets/js/fetch_products.js"></script>
    <script src="../assets/js/fetch_orders.js"></script>
    <script src="../assets/js/fetch_users.js"></script>
    <script src="../assets/js/product_actions.js"></script>
    <script src="../assets/js/main.js"></script>
</body>
</html>