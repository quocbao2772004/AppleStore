<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Kiểm tra ID có được cung cấp không
if (!isset($_GET['id']) || empty($_GET['id'])) {
    setFlashMessage('error', 'ID người dùng là bắt buộc');
    redirect('index.php');
}

$user_id = (int)$_GET['id'];

// Lấy thông tin người dùng
try {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE id = ?");
    $stmt->execute([$user_id]);
    $user = $stmt->fetch();
    
    if (!$user) {
        setFlashMessage('error', 'Không tìm thấy người dùng');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin người dùng: ' . $e->getMessage());
    redirect('index.php');
}

// Lấy đơn hàng gần đây của người dùng
try {
    $stmt = $pdo->prepare("
        SELECT o.*, p.name as product_name 
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ?
        ORDER BY o.created_at DESC
        LIMIT 5
    ");
    $stmt->execute([$user_id]);
    $orders = $stmt->fetchAll();
    
    // Lấy tổng số đơn hàng
    $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM orders WHERE user_id = ?");
    $stmt->execute([$user_id]);
    $orderCount = $stmt->fetch()['count'];
} catch (PDOException $e) {
    $orders = [];
    $orderCount = 0;
}

// Lấy đánh giá gần đây của người dùng
try {
    $stmt = $pdo->prepare("
        SELECT r.*, p.name as product_name 
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
        LIMIT 5
    ");
    $stmt->execute([$user_id]);
    $reviews = $stmt->fetchAll();
    
    // Lấy tổng số đánh giá
    $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM reviews WHERE user_id = ?");
    $stmt->execute([$user_id]);
    $reviewCount = $stmt->fetch()['count'];
} catch (PDOException $e) {
    $reviews = [];
    $reviewCount = 0;
}

// Tiêu đề trang
$pageTitle = 'Xem Người Dùng';

// Bao gồm header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Thông Tin Người Dùng</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="edit.php?id=<?php echo $user_id; ?>" class="btn btn-sm btn-primary me-2">
                        <i class="fas fa-edit"></i> Sửa Thông Tin
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại
                    </a>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Chi Tiết</h5>
                        </div>
                        <div class="card-body">
                            <table class="table">
                                <tr>
                                    <th style="width: 150px;">ID:</th>
                                    <td><?php echo $user['id']; ?></td>
                                </tr>
                                <tr>
                                    <th>Họ tên:</th>
                                    <td><?php echo htmlspecialchars($user['name']); ?></td>
                                </tr>
                                <tr>
                                    <th>Email:</th>
                                    <td><?php echo htmlspecialchars($user['email']); ?></td>
                                </tr>
                                <tr>
                                    <th>Vai trò:</th>
                                    <td>
                                        <span class="badge bg-<?php echo $user['role'] === 'admin' ? 'danger' : 'primary'; ?>">
                                            <?php echo $user['role'] === 'admin' ? 'Quản trị viên' : 'Người dùng'; ?>
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <th>Điện thoại:</th>
                                    <td><?php echo !empty($user['phone']) ? htmlspecialchars($user['phone']) : '<em>Chưa cung cấp</em>'; ?></td>
                                </tr>
                                <tr>
                                    <th>Địa chỉ:</th>
                                    <td><?php echo !empty($user['address']) ? nl2br(htmlspecialchars($user['address'])) : '<em>Chưa cung cấp</em>'; ?></td>
                                </tr>
                                <tr>
                                    <th>Ngày đăng ký:</th>
                                    <td><?php echo date('d/m/Y', strtotime($user['created_at'])); ?></td>
                                </tr>
                                <tr>
                                    <th>Cập nhật lần cuối:</th>
                                    <td><?php echo date('d/m/Y', strtotime($user['updated_at'])); ?></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Đơn Hàng Gần Đây</h5>
                            <?php if ($orderCount > 0): ?>
                            <a href="../orders/index.php?user_id=<?php echo $user_id; ?>" class="btn btn-sm btn-light">
                                Xem Tất Cả
                            </a>
                            <?php endif; ?>
                        </div>
                        <div class="card-body">
                            <?php if (!empty($orders)): ?>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Sản phẩm</th>
                                                <th>Tổng tiền</th>
                                                <th>Trạng thái</th>
                                                <th>Ngày đặt</th>
                                                <th></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach ($orders as $order): ?>
                                            <tr>
                                                <td><?php echo $order['id']; ?></td>
                                                <td><?php echo htmlspecialchars($order['product_name']); ?></td>
                                                <td><?php echo number_format($order['total_price'], 0) . ' VNĐ'; ?></td>
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
                                                            'shipped' => 'Đang giao',
                                                            'delivered' => 'Đã giao',
                                                            'cancelled' => 'Đã hủy'
                                                        ];
                                                        echo $status[$order['status']] ?? ucfirst($order['status']); 
                                                        ?>
                                                    </span>
                                                </td>
                                                <td><?php echo date('d/m/Y', strtotime($order['created_at'])); ?></td>
                                                <td>
                                                    <a href="../orders/view.php?id=<?php echo $order['id']; ?>" class="btn btn-sm btn-info">
                                                        <i class="fas fa-eye"></i>
                                                    </a>
                                                </td>
                                            </tr>
                                            <?php endforeach; ?>
                                        </tbody>
                                    </table>
                                </div>
                                
                                <?php if ($orderCount > count($orders)): ?>
                                <div class="text-center mt-3">
                                    <a href="../orders/index.php?user_id=<?php echo $user_id; ?>" class="btn btn-primary">
                                        Xem Tất Cả <?php echo $orderCount; ?> Đơn Hàng
                                    </a>
                                </div>
                                <?php endif; ?>
                                
                            <?php else: ?>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i> Người dùng này chưa có đơn hàng nào.
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Đánh Giá Gần Đây</h5>
                            <?php if ($reviewCount > 0): ?>
                            <a href="../reviews/index.php?user_id=<?php echo $user_id; ?>" class="btn btn-sm btn-light">
                                Xem Tất Cả
                            </a>
                            <?php endif; ?>
                        </div>
                        <div class="card-body">
                            <?php if (!empty($reviews)): ?>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Sản phẩm</th>
                                                <th>Đánh giá</th>
                                                <th>Nhận xét</th>
                                                <th>Trạng thái</th>
                                                <th>Ngày đánh giá</th>
                                                <th></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach ($reviews as $review): ?>
                                            <tr>
                                                <td><?php echo $review['id']; ?></td>
                                                <td><?php echo htmlspecialchars($review['product_name']); ?></td>
                                                <td>
                                                    <?php for ($i = 1; $i <= 5; $i++): ?>
                                                        <?php if ($i <= $review['rating']): ?>
                                                            <i class="fas fa-star text-warning"></i>
                                                        <?php else: ?>
                                                            <i class="far fa-star text-warning"></i>
                                                        <?php endif; ?>
                                                    <?php endfor; ?>
                                                </td>
                                                <td>
                                                    <?php 
                                                    $comment = htmlspecialchars($review['comment']);
                                                    echo strlen($comment) > 50 ? substr($comment, 0, 50) . '...' : $comment;
                                                    ?>
                                                </td>
                                                <td>
                                                    <span class="badge bg-<?php 
                                                        echo $review['status'] === 'approved' ? 'success' : 
                                                            ($review['status'] === 'rejected' ? 'danger' : 'warning'); 
                                                    ?>">
                                                        <?php 
                                                        $status = [
                                                            'pending' => 'Chờ duyệt',
                                                            'approved' => 'Đã duyệt',
                                                            'rejected' => 'Từ chối'
                                                        ];
                                                        echo $status[$review['status']] ?? ucfirst($review['status']); 
                                                        ?>
                                                    </span>
                                                </td>
                                                <td><?php echo date('d/m/Y', strtotime($review['created_at'])); ?></td>
                                                <td>
                                                    <a href="../reviews/view.php?id=<?php echo $review['id']; ?>" class="btn btn-sm btn-info">
                                                        <i class="fas fa-eye"></i>
                                                    </a>
                                                </td>
                                            </tr>
                                            <?php endforeach; ?>
                                        </tbody>
                                    </table>
                                </div>
                                
                                <?php if ($reviewCount > count($reviews)): ?>
                                <div class="text-center mt-3">
                                    <a href="../reviews/index.php?user_id=<?php echo $user_id; ?>" class="btn btn-primary">
                                        Xem Tất Cả <?php echo $reviewCount; ?> Đánh Giá
                                    </a>
                                </div>
                                <?php endif; ?>
                                
                            <?php else: ?>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i> Người dùng này chưa có đánh giá nào.
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>