<?php
require_once '../includes/functions.php';
require_once '../includes/auth.php';
require_once '../config/database.php';

// Check if user is logged in and is admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../index.php');
}

// Get dashboard statistics
try {
    $stmt = $pdo->query("SELECT COUNT(*) as total FROM products");
    $totalProducts = $stmt->fetch()['total'];
    
    $stmt = $pdo->query("SELECT COUNT(*) as total FROM categories");
    $totalCategories = $stmt->fetch()['total'];
    
    $stmt = $pdo->query("SELECT COUNT(*) as total FROM users");
    $totalUsers = $stmt->fetch()['total'];
    
    $stmt = $pdo->query("SELECT COUNT(*) as total FROM orders");
    $totalOrders = $stmt->fetch()['total'];
    
    $stmt = $pdo->query("SELECT o.id, o.total_price, o.status, o.created_at, u.name as user_name 
                         FROM orders o 
                         JOIN users u ON o.user_id = u.id 
                         ORDER BY o.created_at DESC 
                         LIMIT 5");
    $recentOrders = $stmt->fetchAll();
    // sản phẩm sắp hết hàng
    $stmt = $pdo->query("SELECT id, name, stock FROM products WHERE stock < 10 ORDER BY stock ASC LIMIT 5");
    $lowStockProducts = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy dữ liệu bảng điều khiển: ' . $e->getMessage());
}

// Page title
$pageTitle = 'Bảng Điều Khiển Admin';

// Include header
include 'includes/header.php';
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $pageTitle; ?></title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f5f7fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .sidebar {
            min-height: 100vh;
            background-color: #1e3a8a;
        }
        .card {
            transition: transform 0.3s, box-shadow 0.3s;
            border: none;
            border-radius: 12px;
            overflow: hidden;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
        }
        .card-header {
            background: linear-gradient(45deg, #1e3a8a, #3b82f6);
            color: white;
            border-radius: 12px 12px 0 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #ffffff, #e5e7eb);
        }
        .table th, .table td {
            vertical-align: middle;
        }
        .table-hover tbody tr:hover {
            background-color: #f1f5f9;
        }
        .badge {
            padding: 8px 12px;
            font-size: 0.9em;
        }
        .btn-sm {
            padding: 6px 12px;
            border-radius: 8px;
        }
        .main-content {
            padding: 2rem;
        }
        @media (max-width: 768px) {
            .stat-card {
                margin-bottom: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <?php include 'includes/sidebar.php'; ?>
            
            <!-- Main content -->
            <main class="col-md-9 ms-sm-auto col-lg-10 main-content">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1 class="h3 fw-bold text-dark">Bảng Điều Khiển</h1>
                </div>
                
                <!-- Statistics cards -->
                <div class="row g-4">
                    <div class="col-xl-3 col-md-6">
                        <div class="card stat-card shadow-sm">
                            <div class="card-body d-flex align-items-center">
                                <div>
                                    <h6 class="text-muted text-uppercase mb-1">Sản Phẩm</h6>
                                    <h3 class="fw-bold text-dark"><?php echo $totalProducts; ?></h3>
                                </div>
                                <i class="fas fa-box fa-2x text-primary ms-auto opacity-75"></i>
                            </div>
                        </div>
                    </div>
                    <div class="col-xl-3 col-md-6">
                        <div class="card stat-card shadow-sm">
                            <div class="card-body d-flex align-items-center">
                                <div>
                                    <h6 class="text-muted text-uppercase mb-1">Danh Mục</h6>
                                    <h3 class="fw-bold text-dark"><?php echo $totalCategories; ?></h3>
                                </div>
                                <i class="fas fa-folder fa-2x text-success ms-auto opacity-75"></i>
                            </div>
                        </div>
                    </div>
                    <div class="col-xl-3 col-md-6">
                        <div class="card stat-card shadow-sm">
                            <div class="card-body d-flex align-items-center">
                                <div>
                                    <h6 class="text-muted text-uppercase mb-1">Người Dùng</h6>
                                    <h3 class="fw-bold text-dark"><?php echo $totalUsers; ?></h3>
                                </div>
                                <i class="fas fa-users fa-2x text-info ms-auto opacity-75"></i>
                            </div>
                        </div>
                    </div>
                    <div class="col-xl-3 col-md-6">
                        <div class="card stat-card shadow-sm">
                            <div class="card-body d-flex align-items-center">
                                <div>
                                    <h6 class="text-muted text-uppercase mb-1">Đơn Hàng</h6>
                                    <h3 class="fw-bold text-dark"><?php echo $totalOrders; ?></h3>
                                </div>
                                <i class="fas fa-shopping-cart fa-2x text-warning ms-auto opacity-75"></i>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Recent Orders -->
                <div class="card shadow-sm mt-4">
                    <div class="card-header">
                        <h5 class="m-0 fw-bold">Đơn Hàng Gần Đây</h5>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover table-bordered mb-0">
                                <thead class="bg-light">
                                    <tr>
                                        <th>Mã</th>
                                        <th>Khách Hàng</th>
                                        <th>Tổng Tiền</th>
                                        <th>Trạng Thái</th>
                                        <th>Ngày</th>
                                        <th>Thao Tác</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($recentOrders as $order): ?>
                                    <tr>
                                        <td><?php echo $order['id']; ?></td>
                                        <td><?php echo htmlspecialchars($order['user_name']); ?></td>
                                        <td><?php echo number_format($order['total_price'], 0) . " VNĐ"; ?></td>
                                        <td>
                                            <span class="badge bg-<?php 
                                                echo $order['status'] === 'delivered' ? 'success' : 
                                                    ($order['status'] === 'cancelled' ? 'danger' : 
                                                    ($order['status'] === 'processing' ? 'primary' : 
                                                    ($order['status'] === 'shipped' ? 'info' : 'warning'))); 
                                            ?>">
                                                <?php 
                                                $status = [
                                                    'pending' => 'Chờ xử lý',
                                                    'processing' => 'Đang xử lý',
                                                    'shipped' => 'Đã gửi hàng',
                                                    'delivered' => 'Đã giao hàng',
                                                    'cancelled' => 'Đã hủy'
                                                ];
                                                echo $status[$order['status']] ?? ucfirst($order['status']); 
                                                ?>
                                            </span>
                                        </td>
                                        <td><?php echo date('d/m/Y', strtotime($order['created_at'])); ?></td>
                                        <td>
                                            <a href="orders/view.php?id=<?php echo $order['id']; ?>" class="btn btn-sm btn-outline-info">
                                                <i class="fas fa-eye"></i> Xem
                                            </a>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                    <?php if (empty($recentOrders)): ?>
                                    <tr>
                                        <td colspan="6" class="text-center text-muted">Không tìm thấy đơn hàng nào</td>
                                    </tr>
                                    <?php endif; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Low Stock Products -->
                <div class="card shadow-sm mt-4">
                    <div class="card-header">
                        <h5 class="m-0 fw-bold">Sản Phẩm Sắp Hết Hàng</h5>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover table-bordered mb-0">
                                <thead class="bg-light">
                                    <tr>
                                        <th>Mã</th>
                                        <th>Tên Sản Phẩm</th>
                                        <th>Tồn Kho</th>
                                        <th>Thao Tác</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($lowStockProducts as $product): ?>
                                    <tr>
                                        <td><?php echo $product['id']; ?></td>
                                        <td><?php echo htmlspecialchars($product['name']); ?></td>
                                        <td>
                                            <span class="badge bg-<?php echo $product['stock'] <= 5 ? 'danger' : 'warning'; ?>">
                                                <?php echo $product['stock']; ?>
                                            </span>
                                        </td>
                                        <td>
                                            <a href="products/edit.php?id=<?php echo $product['id']; ?>" class="btn btn-sm btn-outline-primary">
                                                <i class="fas fa-edit"></i> Cập Nhật
                                            </a>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                    <?php if (empty($lowStockProducts)): ?>
                                    <tr>
                                        <td colspan="4" class="text-center text-muted">Không có sản phẩm sắp hết hàng</td>
                                    </tr>
                                    <?php endif; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <?php include 'includes/footer.php'; ?>
</body>
</html>