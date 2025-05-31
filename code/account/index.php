<?php
require_once '../includes/functions.php';
require_once '../includes/auth.php';
require_once '../config/database.php';

// Kiểm tra người dùng đã đăng nhập
if (!isLoggedIn()) {
    setFlashMessage('error', 'Vui lòng đăng nhập để truy cập tài khoản của bạn');
    redirect('../login.php');
}

// Lấy thông tin người dùng
$user_id = $_SESSION['user_id'];
try {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE id = ?");
    $stmt->execute([$user_id]);
    $user = $stmt->fetch();
    
    if (!$user) {
        setFlashMessage('error', 'Không tìm thấy người dùng');
        redirect('../index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin người dùng: ' . $e->getMessage());
    redirect('../index.php');
}

// Lấy thống kê đơn hàng của người dùng
try {
    // Tổng số đơn hàng
    $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM orders WHERE user_id = ?");
    $stmt->execute([$user_id]);
    $total_orders = $stmt->fetch()['count'];
    
    // Đơn hàng theo trạng thái
    $stmt = $pdo->prepare("
        SELECT status, COUNT(*) as count 
        FROM orders 
        WHERE user_id = ? 
        GROUP BY status
    ");
    $stmt->execute([$user_id]);
    $orders_by_status = [];
    while ($row = $stmt->fetch()) {
        $orders_by_status[$row['status']] = $row['count'];
    }
    
    // Đơn hàng gần đây
    $stmt = $pdo->prepare("
        SELECT o.id, o.created_at, o.total_amount, o.status, COUNT(oi.id) as item_count
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT 5
    ");
    $stmt->execute([$user_id]);
    $recent_orders = $stmt->fetchAll();
    
    // Tổng chi tiêu
    $stmt = $pdo->prepare("
        SELECT SUM(total_amount) as total 
        FROM orders 
        WHERE user_id = ? AND status != 'cancelled'
    ");
    $stmt->execute([$user_id]);
    $total_spent = $stmt->fetch()['total'] ?? 0;
} catch (PDOException $e) {
    $total_orders = 0;
    $orders_by_status = [];
    $recent_orders = [];
    $total_spent = 0;
}

// Lấy đánh giá gần đây của người dùng
try {
    $stmt = $pdo->prepare("
        SELECT r.*, p.name as product_name, p.image as product_image
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
        LIMIT 3
    ");
    $stmt->execute([$user_id]);
    $recent_reviews = $stmt->fetchAll();
} catch (PDOException $e) {
    $recent_reviews = [];
}

// Tiêu đề trang
$pageTitle = 'Tài Khoản Của Tôi';

// Include header
include '../includes/header2.php';
?>

<div class="container py-5">
    <div class="row">
        <!-- Thanh bên -->
        <div class="col-lg-3">
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Tài Khoản Của Tôi</h5>
                </div>
                <div class="list-group list-group-flush">
                    <a href="index.php" class="list-group-item list-group-item-action active">
                        <i class="fas fa-tachometer-alt me-2"></i> Bảng Điều Khiển
                    </a>
                    <a href="profile.php" class="list-group-item list-group-item-action">
                        <i class="fas fa-user me-2"></i> Hồ Sơ Của Tôi
                    </a>
                    
                    <a href="reviews.php" class="list-group-item list-group-item-action">
                        <i class="fas fa-star me-2"></i> Đánh Giá Của Tôi
                    </a>
                    <a href="../logout.php" class="list-group-item list-group-item-action text-danger">
                        <i class="fas fa-sign-out-alt me-2"></i> Đăng Xuất
                    </a>
                </div>
            </div>
        </div>
        
        <!-- Nội dung chính -->
        <div class="col-lg-9">
            <!-- Banner chào mừng -->
            <div class="card mb-4">
                <div class="card-body bg-light">
                    <div class="d-flex align-items-center">
                        <div class="flex-shrink-0">
                            <i class="fas fa-user-circle fa-4x text-primary"></i>
                        </div>
                        <div class="flex-grow-1 ms-3">
                            <h4>Chào mừng trở lại, <?php echo htmlspecialchars($user['name']); ?>!</h4>
                            <p class="mb-0">Từ bảng điều khiển tài khoản của bạn, bạn có thể xem các đơn hàng gần đây, quản lý địa chỉ giao hàng và chỉnh sửa mật khẩu cùng thông tin tài khoản.</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Thống kê đơn hàng -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card text-center h-100">
                        <div class="card-body">
                            <i class="fas fa-shopping-bag fa-3x text-primary mb-3"></i>
                            <h5>Tổng Đơn Hàng</h5>
                            <h3><?php echo $total_orders; ?></h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center h-100">
                        <div class="card-body">
                            <i class="fas fa-truck fa-3x text-info mb-3"></i>
                            <h5>Đang Xử Lý</h5>
                            <h3><?php echo ($orders_by_status['processing'] ?? 0) + ($orders_by_status['shipped'] ?? 0); ?></h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center h-100">
                        <div class="card-body">
                            <i class="fas fa-check-circle fa-3x text-success mb-3"></i>
                            <h5>Đã Giao</h5>
                            <h3><?php echo $orders_by_status['delivered'] ?? 0; ?></h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center h-100">
                        <div class="card-body">
                            <i class="fas fa-dollar-sign fa-3x text-warning mb-3"></i>
                            <h5>Tổng Chi Tiêu</h5>
                            <h3>$<?php echo formatPrice($total_spent); ?></h3>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Đơn hàng gần đây -->
            <div class="card mb-4">
                <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">Đơn Hàng Gần Đây</h5>
                    <a href="orders.php" class="btn btn-sm btn-light">Xem Tất Cả</a>
                </div>
                <div class="card-body">
                    <?php if (!empty($recent_orders)): ?>
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Đơn Hàng #</th>
                                        <th>Ngày</th>
                                        <th>Số Lượng</th>
                                        <th>Tổng Tiền</th>
                                        <th>Trạng Thái</th>
                                        <th>Thao Tác</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($recent_orders as $order): ?>
                                        <tr>
                                            <td><?php echo $order['id']; ?></td>
                                            <td><?php echo date('d/m/Y', strtotime($order['created_at'])); ?></td>
                                            <td><?php echo $order['item_count']; ?></td>
                                            <td>$<?php echo formatPrice($order['total_amount']); ?></td>
                                            <td>
                                                <span class="badge bg-<?php 
                                                    echo $order['status'] === 'delivered' ? 'success' : 
                                                        ($order['status'] === 'cancelled' ? 'danger' : 
                                                        ($order['status'] === 'processing' ? 'primary' : 
                                                        ($order['status'] === 'shipped' ? 'info' : 'warning'))); 
                                                ?>">
                                                    <?php 
                                                    echo $order['status'] === 'delivered' ? 'Đã Giao' :
                                                        ($order['status'] === 'cancelled' ? 'Đã Hủy' :
                                                        ($order['status'] === 'processing' ? 'Đang Xử Lý' :
                                                        ($order['status'] === 'shipped' ? 'Đang Giao' : 'Chờ Xử Lý'))); 
                                                    ?>
                                                </span>
                                            </td>
                                            <td>
                                                <a href="order-details.php?id=<?php echo $order['id']; ?>" class="btn btn-sm btn-info">
                                                    <i class="fas fa-eye"></i>
                                                </a>
                                            </td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    <?php else: ?>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i> Bạn chưa có đơn hàng nào.
                        </div>
                        <div class="text-center">
                            <a href="../products.php" class="btn btn-primary">
                                <i class="fas fa-shopping-bag me-2"></i> Bắt Đầu Mua Sắm
                            </a>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
            
            <!-- Đánh giá gần đây -->
            <div class="card">
                <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">Đánh Giá Gần Đây</h5>
                    <a href="reviews.php" class="btn btn-sm btn-light">Xem Tất Cả</a>
                </div>
                <div class="card-body">
                    <?php if (!empty($recent_reviews)): ?>
                        <div class="row">
                            <?php foreach ($recent_reviews as $review): ?>
                                <div class="col-md-4 mb-3">
                                    <div class="card h-100">
                                        <div class="card-body">
                                            <div class="d-flex align-items-center mb-3">
                                                <img src="../uploads/products/<?php echo !empty($review['product_image']) ? $review['product_image'] : 'default.jpg'; ?>" 
                                                     alt="<?php echo htmlspecialchars($review['product_name']); ?>" 
                                                     class="img-thumbnail me-3" style="width: 60px; height: 60px; object-fit: cover;">
                                                <div>
                                                    <h6 class="mb-1">
                                                        <a href="../product.php?id=<?php echo $review['product_id']; ?>" class="text-decoration-none">
                                                            <?php echo htmlspecialchars($review['product_name']); ?>
                                                        </a>
                                                    </h6>
                                                    <div>
                                                        <?php for ($i = 1; $i <= 5; $i++): ?>
                                                            <?php if ($i <= $review['rating']): ?>
                                                                <i class="fas fa-star text-warning"></i>
                                                            <?php else: ?>
                                                                <i class="far fa-star text-warning"></i>
                                                            <?php endif; ?>
                                                        <?php endfor; ?>
                                                    </div>
                                                </div>
                                            </div>
                                            <p class="card-text">
                                                <?php 
                                                $comment = htmlspecialchars($review['comment']);
                                                echo strlen($comment) > 100 ? substr($comment, 0, 100) . '...' : $comment;
                                                ?>
                                            </p>
                                            <div class="d-flex justify-content-between align-items-center">
                                                <small class="text-muted"><?php echo date('d/m/Y', strtotime($review['created_at'])); ?></small>
                                                <span class="badge bg-<?php 
                                                    echo $review['status'] === 'approved' ? 'success' : 
                                                        ($review['status'] === 'rejected' ? 'danger' : 'warning'); 
                                                ?>">
                                                    <?php 
                                                    echo $review['status'] === 'approved' ? 'Đã Duyệt' :
                                                        ($review['status'] === 'rejected' ? 'Đã Từ Chối' : 'Chờ Duyệt');
                                                    ?>
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    <?php else: ?>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i> Bạn chưa có đánh giá nào.
                        </div>
                        <div class="text-center">
                            <a href="../products.php" class="btn btn-primary">
                                <i class="fas fa-star me-2"></i> Xem Sản Phẩm Để Đánh Giá
                            </a>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </div>
</div>

<?php include '../includes/footer.php'; ?>