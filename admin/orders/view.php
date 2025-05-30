<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Kiểm tra ID đã được cung cấp
if (!isset($_GET['id']) || empty($_GET['id'])) {
    setFlashMessage('error', 'ID đơn hàng là bắt buộc');
    redirect('index.php');
}

$order_id = (int)$_GET['id'];

// Lấy dữ liệu đơn hàng
try {
    $stmt = $pdo->prepare("
        SELECT o.*, u.name as user_name, u.email as user_email, u.phone as user_phone, 
               p.name as product_name, p.id as product_id, p.price as product_price, p.image as product_image
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN products p ON o.product_id = p.id
        WHERE o.id = ?
    ");
    $stmt->execute([$order_id]);
    $order = $stmt->fetch();
    
    if (!$order) {
        setFlashMessage('error', 'Không tìm thấy đơn hàng');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy đơn hàng: ' . $e->getMessage());
    redirect('index.php');
}

// Tiêu đề trang
$pageTitle = 'Xem Đơn Hàng';

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
                <h1 class="h2">Đơn Hàng #<?php echo $order_id; ?></h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="edit.php?id=<?php echo $order_id; ?>" class="btn btn-sm btn-primary me-2">
                        <i class="fas fa-edit"></i> Cập Nhật Đơn Hàng
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại
                    </a>
                </div>
            </div>
            
            <!-- Trạng thái đơn hàng -->
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h5 class="card-title">Trạng Thái Đơn Hàng</h5>
                                    <p class="mb-0">
                                        <span class="badge bg-<?php 
                                            echo $order['status'] === 'delivered' ? 'success' : 
                                                ($order['status'] === 'cancelled' ? 'danger' : 
                                                ($order['status'] === 'processing' ? 'primary' : 
                                                ($order['status'] === 'shipped' ? 'info' : 'warning'))); 
                                        ?> fs-6">
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
                                    </p>
                                </div>
                                <div>
                                    <p class="mb-0"><strong>Ngày Đặt:</strong> <?php echo date('d/m/Y', strtotime($order['created_at'])); ?></p>
                                    <p class="mb-0"><strong>Cập Nhật Lần Cuối:</strong> <?php echo date('d/m/Y', strtotime($order['updated_at'])); ?></p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <!-- Thông tin khách hàng -->
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Khách Hàng</h5>
                        </div>
                        <div class="card-body">
                            <table class="table">
                                <tr>
                                    <th style="width: 150px;">Tên:</th>
                                    <td>
                                        <a href="../users/view.php?id=<?php echo $order['user_id']; ?>">
                                            <?php echo htmlspecialchars($order['user_name']); ?>
                                        </a>
                                    </td>
                                </tr>
                                <tr>
                                    <th>Email:</th>
                                    <td><?php echo htmlspecialchars($order['user_email']); ?></td>
                                </tr>
                                <tr>
                                    <th>Điện Thoại:</th>
                                    <td><?php echo !empty($order['user_phone']) ? htmlspecialchars($order['user_phone']) : '<em>Chưa cung cấp</em>'; ?></td>
                                </tr>
                                <tr>
                                    <th>Địa Chỉ Giao Hàng:</th>
                                    <td><?php echo !empty($order['shipping_address']) ? nl2br(htmlspecialchars($order['shipping_address'])) : '<em>Chưa cung cấp</em>'; ?></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Thông tin thanh toán -->
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Thanh Toán</h5>
                        </div>
                        <div class="card-body">
                            <table class="table">
                                <tr>
                                    <th style="width: 150px;">Phương Thức:</th>
                                    <td><?php echo !empty($order['payment_method']) ? htmlspecialchars($order['payment_method']) : '<em>Chưa xác định</em>'; ?></td>
                                </tr>
                                <tr>
                                    <th>Trạng Thái:</th>
                                    <td>
                                        <span class="badge bg-<?php echo $order['payment_status'] === 'paid' ? 'success' : 'warning'; ?>">
                                            <?php echo $order['payment_status'] === 'paid' ? 'Đã Thanh Toán' : 'Chưa Thanh Toán'; ?>
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <th>Mã Giao Dịch:</th>
                                    <td><?php echo !empty($order['transaction_id']) ? htmlspecialchars($order['transaction_id']) : '<em>Không có</em>'; ?></td>
                                </tr>
                                <tr>
                                    <th>Ngày Thanh Toán:</th>
                                    <td><?php echo !empty($order['payment_date']) ? date('d/m/Y', strtotime($order['payment_date'])) : '<em>Chưa có</em>'; ?></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Chi tiết đơn hàng -->
                <div class="col-md-12 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Chi Tiết Đơn Hàng</h5>
                        </div>
                        <div class="card-body">
                            <div class="row mb-4">
                                <div class="col-md-3">
                                    <div class="text-center">
                                        <img src="../../uploads/products/<?php echo !empty($order['product_image']) ? $order['product_image'] : 'default.jpg'; ?>" 
                                             alt="<?php echo htmlspecialchars($order['product_name']); ?>" 
                                             class="img-fluid rounded" style="max-height: 150px;">
                                    </div>
                                </div>
                                <div class="col-md-9">
                                    <h5>
                                        <a href="../products/view.php?id=<?php echo $order['product_id']; ?>">
                                            <?php echo htmlspecialchars($order['product_name']); ?>
                                        </a>
                                    </h5>
                                    <table class="table table-bordered mt-3">
                                        <thead class="table-light">
                                            <tr>
                                                <th>Đơn Giá</th>
                                                <th>Số Lượng</th>
                                                <th>Tạm Tính</th>
                                                <th>Giảm Giá</th>
                                                <th>Thuế</th>
                                                <th>Phí Ship</th>
                                                <th>Tổng Cộng</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td><?php echo number_format($order['product_price'], 0) . " VNĐ"; ?></td>
                                                <td><?php echo $order['quantity']; ?></td>
                                                <td><?php echo number_format($order['product_price'] * $order['quantity'], 0) . " VNĐ"; ?></td>
                                                <td><?php echo number_format($order['discount'] ?? 0, 0) . " VNĐ"; ?></td>
                                                <td><?php echo number_format($order['tax'] ?? 0, 0) . " VNĐ"; ?></td>
                                                <td><?php echo number_format($order['shipping_fee'] ?? 0, 0) . " VNĐ"; ?></td>
                                                <td class="fw-bold"><?php echo number_format($order['total_price'], 0) . " VNĐ"; ?></td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            
                            <?php if (!empty($order['notes'])): ?>
                            <div class="mt-3">
                                <h6>Ghi Chú Đơn Hàng:</h6>
                                <div class="p-3 bg-light rounded">
                                    <?php echo nl2br(htmlspecialchars($order['notes'])); ?>
                                </div>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
                
                <!-- Lịch sử đơn hàng -->
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Lịch Sử Đơn Hàng</h5>
                        </div>
                        <div class="card-body">
                            <ul class="list-group">
                                <li class="list-group-item">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <i class="fas fa-shopping-cart text-primary me-2"></i>
                                            <strong>Đã Đặt Hàng</strong>
                                        </div>
                                        <div><?php echo date('d/m/Y H:i', strtotime($order['created_at'])); ?></div>
                                    </div>
                                </li>
                                
                                <?php if ($order['status'] !== 'pending'): ?>
                                <li class="list-group-item">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <i class="fas fa-cog text-primary me-2"></i>
                                            <strong>Đang Xử Lý</strong>
                                        </div>
                                        <div><?php echo date('d/m/Y H:i', strtotime($order['updated_at'])); ?></div>
                                    </div>
                                </li>
                                <?php endif; ?>
                                
                                <?php if ($order['status'] === 'shipped' || $order['status'] === 'delivered'): ?>
                                <li class="list-group-item">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <i class="fas fa-truck text-primary me-2"></i>
                                            <strong>Đã Gửi Hàng</strong>
                                        </div>
                                        <div><?php echo date('d/m/Y H:i', strtotime($order['updated_at'])); ?></div>
                                    </div>
                                </li>
                                <?php endif; ?>
                                
                                <?php if ($order['status'] === 'delivered'): ?>
                                <li class="list-group-item">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <i class="fas fa-check-circle text-success me-2"></i>
                                            <strong>Đã Giao Hàng</strong>
                                        </div>
                                        <div><?php echo date('d/m/Y H:i', strtotime($order['updated_at'])); ?></div>
                                    </div>
                                </li>
                                <?php endif; ?>
                                
                                <?php if ($order['status'] === 'cancelled'): ?>
                                <li class="list-group-item">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <i class="fas fa-times-circle text-danger me-2"></i>
                                            <strong>Đã Hủy Đơn</strong>
                                        </div>
                                        <div><?php echo date('d/m/Y H:i', strtotime($order['updated_at'])); ?></div>
                                    </div>
                                </li>
                                <?php endif; ?>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>