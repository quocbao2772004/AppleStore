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
        SELECT o.*, u.name as user_name, u.email as user_email, 
               p.name as product_name, p.id as product_id
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

// Xử lý gửi form
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $status = clean($_POST['status']);
    $payment_status = clean($_POST['payment_status']);
    $transaction_id = !empty($_POST['transaction_id']) ? clean($_POST['transaction_id']) : null;
    $shipping_address = !empty($_POST['shipping_address']) ? clean($_POST['shipping_address']) : null;
    $notes = !empty($_POST['notes']) ? clean($_POST['notes']) : null;
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if (empty($status)) {
        $errors[] = 'Trạng thái đơn hàng là bắt buộc';
    }
    
    if (empty($payment_status)) {
        $errors[] = 'Trạng thái thanh toán là bắt buộc';
    }
    
    // Nếu không có lỗi, cập nhật đơn hàng
    if (empty($errors)) {
        try {
            $stmt = $pdo->prepare("
                UPDATE orders 
                SET status = ?, notes = ?, created_at = NOW()
                WHERE id = ?
            ");
            $stmt->execute([$status, $notes, $order_id]);
            
            setFlashMessage('success', 'Cập nhật đơn hàng thành công');
            redirect('view.php?id=' . $order_id);
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật đơn hàng: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Tiêu đề trang
$pageTitle = 'Sửa Đơn Hàng';

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
                <h1 class="h2">Sửa Đơn Hàng #<?php echo $order_id; ?></h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="view.php?id=<?php echo $order_id; ?>" class="btn btn-sm btn-info me-2">
                        <i class="fas fa-eye"></i> Xem Đơn Hàng
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại
                    </a>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-body">
                            <form action="" method="POST">
                                <div class="row mb-3">
                                    <div class="col-md-6">
                                        <label for="status" class="form-label">Trạng Thái Đơn Hàng <span class="text-danger">*</span></label>
                                        <select class="form-select" id="status" name="status" required>
                                            <option value="pending" <?php echo $order['status'] === 'pending' ? 'selected' : ''; ?>>Chờ xử lý</option>
                                            <option value="processing" <?php echo $order['status'] === 'processing' ? 'selected' : ''; ?>>Đang xử lý</option>
                                            <option value="shipped" <?php echo $order['status'] === 'shipped' ? 'selected' : ''; ?>>Đã gửi hàng</option>
                                            <option value="delivered" <?php echo $order['status'] === 'delivered' ? 'selected' : ''; ?>>Đã giao hàng</option>
                                            <option value="cancelled" <?php echo $order['status'] === 'cancelled' ? 'selected' : ''; ?>>Đã hủy</option>
                                        </select>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="payment_status" class="form-label">Trạng Thái Thanh Toán <span class="text-danger">*</span></label>
                                        <select class="form-select" id="payment_status" name="payment_status" required>
                                            <option value="pending" <?php echo $order['payment_status'] === 'pending' ? 'selected' : ''; ?>>Chờ thanh toán</option>
                                            <option value="paid" <?php echo $order['payment_status'] === 'paid' ? 'selected' : ''; ?>>Đã thanh toán</option>
                                            <option value="refunded" <?php echo $order['payment_status'] === 'refunded' ? 'selected' : ''; ?>>Đã hoàn tiền</option>
                                            <option value="failed" <?php echo $order['payment_status'] === 'failed' ? 'selected' : ''; ?>>Thanh toán thất bại</option>
                                        </select>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="transaction_id" class="form-label">Mã Giao Dịch</label>
                                    <input type="text" class="form-control" id="transaction_id" name="transaction_id" value="<?php echo htmlspecialchars($order['transaction_id'] ?? ''); ?>">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="shipping_address" class="form-label">Địa Chỉ Giao Hàng</label>
                                    <textarea class="form-control" id="shipping_address" name="shipping_address" rows="3"><?php echo htmlspecialchars($order['shipping_address'] ?? ''); ?></textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="notes" class="form-label">Ghi Chú</label>
                                    <textarea class="form-control" id="notes" name="notes" rows="3"><?php echo htmlspecialchars($order['notes'] ?? ''); ?></textarea>
                                </div>
                                
                                <div class="d-grid gap-2">
                                    <button type="submit" class="btn btn-primary">Cập Nhật Đơn Hàng</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Đơn Hàng</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Mã đơn hàng:</strong> <?php echo $order['id']; ?></p>
                            <p><strong>Ngày đặt:</strong> <?php echo date('d/m/Y', strtotime($order['created_at'])); ?></p>
                            <p><strong>Khách hàng:</strong> <?php echo htmlspecialchars($order['user_name']); ?></p>
                            <p><strong>Email:</strong> <?php echo htmlspecialchars($order['user_email']); ?></p>
                            <p><strong>Sản phẩm:</strong> <?php echo htmlspecialchars($order['product_name']); ?></p>
                            <p><strong>Số lượng:</strong> <?php echo $order['quantity']; ?></p>
                            <p><strong>Tổng tiền:</strong> <?php echo formatPrice($order['total_price']); ?>đ</p>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Lưu Ý</h5>
                        </div>
                        <div class="card-body">
                            <ul class="list-unstyled">
                                <li><i class="fas fa-info-circle text-primary me-2"></i> Thay đổi trạng thái đơn hàng sẽ cập nhật lịch sử đơn hàng của khách hàng.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Nếu bạn đánh dấu đơn hàng là "Đã giao hàng", hãy đảm bảo rằng nó đã thực sự được giao cho khách hàng.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Thêm ghi chú để theo dõi thông tin quan trọng về đơn hàng này.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>