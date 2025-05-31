<?php
require_once 'includes/functions.php';
require_once 'includes/auth.php';
require_once 'config/database.php';

// Ensure session is started
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// Check if user is logged in
if (!isLoggedIn()) {
    setFlashMessage('error', 'Vui lòng đăng nhập để xem xác nhận đơn hàng');
    redirect('login.php?redirect=order-confirmation.php');
}

$user_id = $_SESSION['user_id'];
$order_group_id = isset($_GET['order_group_id']) ? (int)$_GET['order_group_id'] : 0;

if ($order_group_id <= 0) {
    setFlashMessage('error', 'Đơn hàng không hợp lệ');
    redirect('index.php');
}

// Fetch order details
try {
    $stmt = $pdo->prepare("
        SELECT o.*, p.name AS product_name, p.image
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ? AND o.order_group_id = ?
    ");
    $stmt->execute([$user_id, $order_group_id]);
    $orders = $stmt->fetchAll(PDO::FETCH_ASSOC);
    
    if (empty($orders)) {
        setFlashMessage('error', 'Không tìm thấy đơn hàng');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin đơn hàng: ' . $e->getMessage());
    redirect('index.php');
}

// Set transaction number
$transaction_number = $order_group_id; // Default for COD
if ($orders[0]['payment_method'] === 'qr_code') {
    if (!isset($_SESSION['qr_info']) || $_SESSION['qr_info']['order_group_id'] != $order_group_id) {
        setFlashMessage('error', 'Không tìm thấy thông tin thanh toán. Vui lòng kiểm tra lại đơn hàng.');
        error_log("Session QR Info missing or mismatch in order-confirmation: " . print_r($_SESSION['qr_info'] ?? [], true));
        redirect('orders.php');
    }
    $transaction_number = preg_replace('/Ma hoa don /', '', $_SESSION['qr_info']['description']);
}

// Clear QR info from session
if (isset($_SESSION['qr_info']) && $_SESSION['qr_info']['order_group_id'] == $order_group_id) {
    unset($_SESSION['qr_info']);
}

// Page title
$pageTitle = 'Xác nhận đơn hàng #' . htmlspecialchars($transaction_number);

// Include header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <div class="col-lg-8">
            <div class="card mb-4">
                <div class="card-header bg-success text-white">
                    <h4 class="mb-0">Xác nhận đơn hàng #<?php echo htmlspecialchars($transaction_number); ?></h4>
                </div>
                <div class="card-body">
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        Đơn hàng của bạn đã được đặt thành công! Chúng tôi đã gửi email xác nhận đến địa chỉ email của bạn.
                    </div>
                    
                    <h5 class="mb-3">Thông tin đơn hàng</h5>
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <p class="mb-1"><strong>Người nhận:</strong></p>
                            <p class="mb-1"><?php echo htmlspecialchars($orders[0]['shipping_name']); ?></p>
                            <p class="mb-1"><?php echo htmlspecialchars($orders[0]['shipping_phone']); ?></p>
                            <p class="mb-1"><?php echo nl2br(htmlspecialchars($orders[0]['shipping_address'])); ?></p>
                        </div>
                        <div class="col-md-6">
                            <p class="mb-1"><strong>Phương thức thanh toán:</strong></p>
                            <p class="mb-1">
                                <?php echo $orders[0]['payment_method'] === 'qr_code' ? 'Thanh toán qua QR' : 'Thanh toán khi nhận hàng'; ?>
                            </p>
                            <p class="mb-1"><strong>Ngày đặt hàng:</strong></p>
                            <p class="mb-1"><?php echo date('d/m/Y H:i', strtotime($orders[0]['created_at'])); ?></p>
                        </div>
                    </div>
                    
                    <?php if (!empty($orders[0]['notes'])): ?>
                        <div class="mb-3">
                            <p class="mb-1"><strong>Ghi chú:</strong></p>
                            <p class="mb-0"><?php echo nl2br(htmlspecialchars($orders[0]['notes'])); ?></p>
                        </div>
                    <?php endif; ?>
                    
                    <div class="table-responsive">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Sản phẩm</th>
                                    <th class="text-end">Đơn giá</th>
                                    <th class="text-center">Số lượng</th>
                                    <th class="text-end">Thành tiền</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php
                                $total_amount = 0;
                                foreach ($orders as $order):
                                    $total_amount += $order['total_price'];
                                ?>
                                    <tr>
                                        <td>
                                            <div class="d-flex align-items-center">
                                                <img src="uploads/products/<?php echo !empty($order['image']) ? $order['image'] : 'default.jpg'; ?>" 
                                                     alt="<?php echo htmlspecialchars($order['product_name']); ?>" 
                                                     class="me-3" style="width: 50px; height: 50px; object-fit: cover;">
                                                <div><?php echo htmlspecialchars($order['product_name']); ?></div>
                                            </div>
                                        </td>
                                        <td class="text-end"><?php echo number_format($order['total_price'] / $order['quantity'], 0, '.', ',') . '₫'; ?></td>
                                        <td class="text-center"><?php echo $order['quantity']; ?></td>
                                        <td class="text-end"><?php echo number_format($order['total_price'], 0, '.', ',') . '₫'; ?></td>
                                    </tr>
                                <?php endforeach; ?>
                            </tbody>
                            <tfoot>
                                <tr>
                                    <td colspan="3" class="text-end"><strong>Tổng cộng:</strong></td>
                                    <td class="text-end"><strong><?php echo number_format($total_amount, 0, '.', ',') . '₫'; ?></strong></td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-lg-4">
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h5 class="mb-0">Trạng thái đơn hàng</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <p class="mb-1"><strong>Mã đơn hàng:</strong></p>
                        <p class="mb-3"><?php echo htmlspecialchars($transaction_number); ?></p>
                        
                        <p class="mb-1"><strong>Trạng thái:</strong></p>
                        <p class="mb-3">
                            <span class="badge bg-success">Đã đặt hàng</span>
                        </p>
                    </div>
                    
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        Bạn sẽ nhận được thông báo khi đơn hàng được xác nhận và giao hàng.
                    </div>
                    
                    <div class="d-grid gap-2">
                        <a href="orders.php" class="btn btn-dark">
                            <i class="fas fa-list me-2"></i> Xem đơn hàng của tôi
                        </a>
                        <a href="index.php" class="btn btn-outline-dark">
                            <i class="fas fa-home me-2"></i> Tiếp tục mua sắm
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<?php include 'includes/footer.php'; ?>