<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Phân trang
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$perPage = 10;
$offset = ($page - 1) * $perPage;

// Bộ lọc
$status = isset($_GET['status']) ? clean($_GET['status']) : '';
$search = isset($_GET['search']) ? clean($_GET['search']) : '';

// Xây dựng điều kiện truy vấn
$conditions = [];
$params = [];

if (!empty($status)) {
    $conditions[] = "o.status = ?";
    $params[] = $status;
}

if (!empty($search)) {
    $conditions[] = "(u.name LIKE ? OR u.email LIKE ? OR o.id LIKE ?)";
    $params[] = "%$search%";
    $params[] = "%$search%";
    $params[] = "%$search%";
}

$whereClause = !empty($conditions) ? "WHERE " . implode(" AND ", $conditions) : "";

// Lấy tổng số đơn hàng
try {
    $query = "SELECT COUNT(*) as total 
              FROM orders o 
              JOIN users u ON o.user_id = u.id 
              $whereClause";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $totalOrders = $stmt->fetch()['total'];
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy đơn hàng: ' . $e->getMessage());
    $totalOrders = 0;
}

// Lấy danh sách đơn hàng có phân trang
try {
    $query = "SELECT o.*, u.name as user_name, u.email as user_email, p.name as product_name 
              FROM orders o 
              JOIN users u ON o.user_id = u.id 
              JOIN products p ON o.product_id = p.id 
              $whereClause 
              ORDER BY o.created_at DESC 
              LIMIT $perPage OFFSET $offset";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $orders = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy đơn hàng: ' . $e->getMessage());
    $orders = [];
}

// Tiêu đề trang
$pageTitle = 'Đơn Hàng';

// Thêm header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Đơn Hàng</h1>
            </div>
            
            <!-- Bộ lọc -->
            <div class="row mb-3">
                <div class="col-md-8">
                    <form action="" method="GET" class="d-flex">
                        <input type="text" name="search" class="form-control me-2" placeholder="Tìm theo mã đơn hàng, tên khách hàng hoặc email..." value="<?php echo htmlspecialchars($search); ?>">
                        <select name="status" class="form-select me-2" style="width: 150px;">
                            <option value="">Tất Cả Trạng Thái</option>
                            <option value="pending" <?php echo $status === 'pending' ? 'selected' : ''; ?>>Chờ Xử Lý</option>
                            <option value="processing" <?php echo $status === 'processing' ? 'selected' : ''; ?>>Đang Xử Lý</option>
                            <option value="shipped" <?php echo $status === 'shipped' ? 'selected' : ''; ?>>Đã Gửi</option>
                            <option value="delivered" <?php echo $status === 'delivered' ? 'selected' : ''; ?>>Đã Giao</option>
                            <option value="cancelled" <?php echo $status === 'cancelled' ? 'selected' : ''; ?>>Đã Hủy</option>
                        </select>
                        <button type="submit" class="btn btn-outline-primary">Lọc</button>
                        <?php if (!empty($search) || !empty($status)): ?>
                            <a href="index.php" class="btn btn-outline-secondary ms-2">Xóa Lọc</a>
                        <?php endif; ?>
                    </form>
                </div>
                
            </div>
            
            <!-- Bảng đơn hàng -->
            <div class="table-responsive">
                <table class="table table-striped table-sm">
                    <thead>
                        <tr>
                            <th>Mã</th>
                            <th>Khách Hàng</th>
                            <th>Sản Phẩm</th>
                            <th>Số Lượng</th>
                            <th>Tổng Tiền</th>
                            <th>Trạng Thái</th>
                            <th>Thanh Toán</th>
                            <th>Ngày</th>
                            <th>Thao Tác</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($orders as $order): ?>
                        <tr>
                            <td><?php echo $order['id']; ?></td>
                            <td>
                                <div><?php echo htmlspecialchars($order['user_name']); ?></div>
                                <small class="text-muted"><?php echo htmlspecialchars($order['user_email']); ?></small>
                            </td>
                            <td><?php echo htmlspecialchars($order['product_name']); ?></td>
                            <td><?php echo $order['quantity']; ?></td>
                            <td><?php echo number_format($order['total_price'], 0) . " VNĐ"; ?></td>
                            <td>
                                <span class="badge bg-<?php 
                                    echo $order['status'] === 'delivered' ? 'success' : 
                                        ($order['status'] === 'cancelled' ? 'danger' : 
                                        ($order['status'] === 'processing' ? 'primary' : 
                                        ($order['status'] === 'shipped' ? 'info' : 'warning'))); 
                                ?>">
                                    <?php 
                                    $statusMap = [
                                        'pending' => 'Chờ Xử Lý',
                                        'processing' => 'Đang Xử Lý',
                                        'shipped' => 'Đã Gửi',
                                        'delivered' => 'Đã Giao',
                                        'cancelled' => 'Đã Hủy'
                                    ];
                                    echo $statusMap[$order['status']] ?? ucfirst($order['status']); 
                                    ?>
                                </span>
                            </td>
                            <td><?php echo htmlspecialchars($order['payment_method'] ?? 'N/A'); ?></td>
                            <td><?php echo date('d/m/Y', strtotime($order['created_at'])); ?></td>
                            <td>
                                <a href="view.php?id=<?php echo $order['id']; ?>" class="btn btn-sm btn-info">
                                    <i class="fas fa-eye"></i>
                                </a>
                                <a href="edit.php?id=<?php echo $order['id']; ?>" class="btn btn-sm btn-primary">
                                    <i class="fas fa-edit"></i>
                                </a>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                        <?php if (empty($orders)): ?>
                        <tr>
                            <td colspan="9" class="text-center">Không tìm thấy đơn hàng nào</td>
                        </tr>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>
            
            <!-- Phân trang -->
            <div class="d-flex justify-content-center">
                <?php
                $totalPages = ceil($totalOrders / $perPage);
                $url = 'index.php';
                $queryParams = [];
                
                if (!empty($status)) {
                    $queryParams[] = "status=" . urlencode($status);
                }
                
                if (!empty($search)) {
                    $queryParams[] = "search=" . urlencode($search);
                }
                
                if (!empty($queryParams)) {
                    $url .= '?' . implode('&', $queryParams) . '&';
                } else {
                    $url .= '?';
                }
                
                echo paginate($totalOrders, $perPage, $page, $url);
                ?>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>