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
    <link rel="stylesheet" type = "text/css" href="../assets/css/admin.css">
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

                    <label for="product-price">Giá (VNĐ)</label>
                    <input type="number" id="product-price" name="price" required>

                    <label for="product-image">URL hình ảnh</label>
                    <input type="text" id="product-image" name="image" required>

                    <label for="product-category">Loại sản phẩm</label>
                    <input type="text" id="product-category" name="category" required>

                    <label for="product-quantity">Số lượng</label>
                    <input type="text" id="product-quantity" name="quantity" required>
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

    <script>
        // Điều hướng giữa các section
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const sectionId = this.getAttribute('href').substring(1);

                // Ẩn tất cả section
                document.querySelectorAll('.section').forEach(section => {
                    section.classList.remove('active');
                });

                // Hiển thị section được chọn
                document.getElementById(sectionId).classList.add('active');

                // Cập nhật trạng thái active cho nav-link
                document.querySelectorAll('.nav-link').forEach(nav => {
                    nav.classList.remove('active');
                });
                this.classList.add('active');

                // Tải dữ liệu tương ứng
                if (sectionId === 'products') {
                    fetchProducts();
                } else if (sectionId === 'orders') {
                    fetchOrders();
                } else if (sectionId === 'users') {
                    fetchUsers();
                }
            });
        });

        // Tải danh sách sản phẩm
        function fetchProducts() {
            fetch('../../backend/admin/fetch_products_admin.php')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const tbody = document.querySelector('#product-table tbody');
                    tbody.innerHTML = '';

                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="empty-message">Không có sản phẩm nào trong database.</td></tr>';
                        return;
                    }

                    data.forEach(product => {
                        const row = `
                            <tr>
                                <td>${product.id}</td>
                                <td><img src="${product.image}" alt="${product.name}"></td>
                                <td>${product.name}</td>
                                <td>${product.price}</td>
                                <td>${product.category}</td>
                                <td>${product.quantity}</td>
                                <td>
                                    <button class="action-btn edit" onclick="editProduct(${product.id})">Sửa</button>
                                    <button class="action-btn delete" onclick="deleteProduct(${product.id})">Xóa</button>
                                </td>
                            </tr>
                        `;
                        tbody.innerHTML += row;
                    });
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    const tbody = document.querySelector('#product-table tbody');
                    tbody.innerHTML = `<tr><td colspan="5" class="error-message">Lỗi khi tải sản phẩm: ${error.message}</td></tr>`;
                });
        }

        // Tải danh sách đơn hàng (giữ nguyên)
        function fetchOrders() {
    fetch('../../backend/admin/fetch_order_admin.php')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const tbody = document.querySelector('#order-table tbody');
            tbody.innerHTML = '';

            // Kiểm tra xem data có phải là mảng không
            if (!Array.isArray(data)) {
                tbody.innerHTML = `<tr><td colspan="5" class="error-message">Dữ liệu không hợp lệ: ${JSON.stringify(data)}</td></tr>`;
                return;
            }

            // Kiểm tra lỗi từ backend
            if (data.length > 0 && data[0].error) {
                tbody.innerHTML = `<tr><td colspan="5" class="error-message">${data[0].message}</td></tr>`;
                return;
            }

            // Nếu không có đơn hàng
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-message">Không có đơn hàng nào.</td></tr>';
                return;
            }

            // Hiển thị danh sách đơn hàng
            data.forEach(order => {
                const row = `
                    <tr>
                        <td>${order.id}</td>
                        <td>${order.user_email}</td>
                        <td>${order.total}</td>
                        <td>${order.status}</td>
                        <td>${order.created_at}</td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        })
        .catch(error => {
            console.error('Lỗi fetchOrders:', error);
            const tbody = document.querySelector('#order-table tbody');
            tbody.innerHTML = `<tr><td colspan="5" class="error-message">Lỗi khi tải đơn hàng: ${error.message}</td></tr>`;
        });
}

        // Tải danh sách người dùng (giữ nguyên)
        function fetchUsers() {
            fetch('../../backend/admin/fetch_user_admin.php')
                .then(response => response.json())
                .then(data => {
                    const tbody = document.querySelector('#user-table tbody');
                    tbody.innerHTML = '';
                    if (data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="3" class="empty-message">Không có người dùng nào.</td></tr>';
                        return;
                    }
                    data.forEach(user => {
                        const row = `
                            <tr>
                                <td>${user.id}</td>
                                <td>${user.email}</td>
                                <td>${user.created_at}</td>
                            </tr>
                        `;
                        tbody.innerHTML += row;
                    });
                })
                .catch(error => {
                    const tbody = document.querySelector('#user-table tbody');
                    tbody.innerHTML = `<tr><td colspan="3" class="error-message">Lỗi khi tải người dùng: ${error.message}</td></tr>`;
                });
        }

        // Thêm sản phẩm
        document.getElementById('add-product-form').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);

            fetch('add_product.php', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Thêm sản phẩm thành công!');
                    fetchProducts();
                    this.reset();
                } else {
                    alert('Lỗi: ' + data.message);
                }
            })
            .catch(error => {
                alert('Lỗi khi thêm sản phẩm: ' + error.message);
            });
        });

        // Sửa sản phẩm
        function editProduct(id) {
            fetch(`../../backend/admin/fetch_product_admin.php?id=${id}`)
                .then(response => response.json())
                .then(data => {
                    const name = prompt('Nhập tên sản phẩm mới:', data.name);
                    const price = prompt('Nhập giá mới:', data.price);
                    const image = prompt('Nhập URL hình ảnh mới:', data.image);

                    if (name && price && image) {
                        const formData = new FormData();
                        formData.append('id', id);
                        formData.append('name', name);
                        formData.append('price', price);
                        formData.append('image', image);

                        fetch('update_product.php', {
                            method: 'POST',
                            body: formData
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                alert('Cập nhật sản phẩm thành công!');
                                fetchProducts();
                            } else {
                                alert('Lỗi: ' + data.message);
                            }
                        });
                    }
                });
        }

        // Xóa sản phẩm
        function deleteProduct(id) {
            if (confirm('Bạn có chắc muốn xóa sản phẩm này?')) {
                fetch(`delete_product.php?id=${id}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Xóa sản phẩm thành công!');
                        fetchProducts();
                    } else {
                        alert('Lỗi: ' + data.message);
                    }
                });
            }
        }

        // Tải dữ liệu ban đầu
        fetchProducts();
    </script>
</body>
</html>