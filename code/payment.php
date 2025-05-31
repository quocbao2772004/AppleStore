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
    setFlashMessage('error', 'Vui lòng đăng nhập để thanh toán');
    redirect('login.php?redirect=payment.php');
}

$user_id = $_SESSION['user_id'];
$order_group_id = isset($_GET['order_group_id']) ? (int)$_GET['order_group_id'] : 0;

if ($order_group_id <= 0) {
    setFlashMessage('error', 'Đơn hàng không hợp lệ');
    redirect('cart.php');
}

// Fetch order details
try {
    $stmt = $pdo->prepare("
        SELECT o.*, p.name AS product_name, p.image, p.price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ? AND o.order_group_id = ?
    ");
    $stmt->execute([$user_id, $order_group_id]);
    $orders = $stmt->fetchAll(PDO::FETCH_ASSOC);
    
    if (empty($orders)) {
        setFlashMessage('error', 'Không tìm thấy đơn hàng');
        redirect('cart.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin đơn hàng: ' . $e->getMessage());
    redirect('cart.php');
}

// Check QR info in session for QR code payment
$qr_image = null;
$transaction_id = null;
$amount = null;
$transaction_number = $order_group_id; // Default for COD

if ($orders[0]['payment_method'] === 'qr_code') {
    if (!isset($_SESSION['qr_info']) || $_SESSION['qr_info']['order_group_id'] != $order_group_id) {
        setFlashMessage('error', 'Không tìm thấy thông tin thanh toán. Vui lòng thử lại.');
        error_log("Session QR Info missing or mismatch: " . print_r($_SESSION['qr_info'] ?? [], true));
        redirect('cart.php');
    }
    
    $qr_info = $_SESSION['qr_info'];
    $qr_image = $qr_info['qr_code'];
    $transaction_id = $qr_info['order_id'];
    $amount = $qr_info['amount'];
    $transaction_number = preg_replace('/Ma hoa don /', '', $qr_info['description']);
}

// Prepare items for email
$items = array_map(function($order) {
    return [
        'name' => $order['product_name'],
        'quantity' => $order['quantity'],
        'price' => $order['total_price'] / $order['quantity']
    ];
}, $orders);

// Page title
$pageTitle = 'Thanh toán đơn hàng #' . htmlspecialchars($transaction_number);

// Include header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <div class="col-lg-8">
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h4 class="mb-0">Thanh toán đơn hàng #<?php echo htmlspecialchars($transaction_number); ?></h4>
                </div>
                <div class="card-body">
                    <?php if ($orders[0]['payment_method'] === 'qr_code'): ?>
                        <div class="text-center mb-4">
                            <?php if ($qr_image): ?>
                                <img src="<?php echo htmlspecialchars($qr_image); ?>" 
                                     alt="QR Code" class="img-fluid mb-3" style="max-width: 300px;">
                                <p class="mb-0">Quét mã QR để thanh toán</p>
                                <p class="text-muted mt-2">
                                    Số tài khoản: MB-6866820048888
                                </p>
                            <?php else: ?>
                                <div class="alert alert-danger">
                                    Không thể hiển thị mã QR. Vui lòng liên hệ hỗ trợ.
                                </div>
                            <?php endif; ?>
                        </div>
                        
                        <div class="alert alert-info">
                            <h5 class="alert-heading">Hướng dẫn thanh toán:</h5>
                            <ol class="mb-0">
                                <li>Mở ứng dụng ngân hàng của bạn</li>
                                <li>Quét mã QR trên màn hình</li>
                                <li>Kiểm tra thông tin thanh toán</li>
                                <li>Xác nhận thanh toán</li>
                            </ol>
                        </div>
                    <?php endif; ?>
                    
                    <hr>
                    
                    <h5 class="mb-3">Thông tin đơn hàng</h5>
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <p class="mb-1"><strong>Người nhận:</strong></p>
                            <p class="mb-1"><?php echo htmlspecialchars($orders[0]['shipping_name']); ?></p>
                            <p class="mb-1"><?php echo htmlspecialchars($orders[0]['shipping_phone']); ?></p>
                            <p class="mb-1"><?php echo nl2br(htmlspecialchars($orders[0]['shipping_address'])); ?></p>
                        </div>
                        <div class="col-md-6">
                            <p class="mb-1"><strong>Số tiền thanh toán:</strong></p>
                            <p class="mb-1 text-danger fw-bold"><?php echo number_format($amount ?: array_sum(array_column($orders, 'total_price')), 0, '.', ',') . '₫'; ?></p>
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
                                <?php foreach ($orders as $order): ?>
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
                                    <td class="text-end"><strong><?php echo number_format($amount ?: array_sum(array_column($orders, 'total_price')), 0, '.', ',') . '₫'; ?></strong></td>
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
                    <h5 class="mb-0">Trạng thái thanh toán</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <p class="mb-1"><strong>Mã đơn hàng:</strong></p>
                        <p class="mb-3"><?php echo htmlspecialchars($transaction_number); ?></p>
                        
                        <p class="mb-1"><strong>Trạng thái:</strong></p>
                        <p class="mb-3">
                            <span class="badge bg-warning">Chờ thanh toán</span>
                        </p>
                        
                        <p class="mb-1"><strong>Ngày đặt hàng:</strong></p>
                        <p class="mb-0"><?php echo date('d/m/Y H:i', strtotime($orders[0]['created_at'])); ?></p>
                    </div>
                    
                    <div class="alert alert-warning">
                        <i class="fas fa-info-circle me-2"></i>
                        Sau khi thanh toán thành công, đơn hàng của bạn sẽ được xử lý trong vòng 24 giờ.
                    </div>
                    
                    <?php if ($orders[0]['payment_method'] === 'qr_code'): ?>
                        <div class="d-grid gap-2">
                            <button type="button" class="btn btn-success" id="check-payment">
                                <i class="fas fa-check-circle me-2"></i> Kiểm tra thanh toán
                            </button>
                            <a href="orders.php" class="btn btn-outline-dark">
                                <i class="fas fa-list me-2"></i> Xem đơn hàng của tôi
                            </a>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    <?php if ($orders[0]['payment_method'] === 'qr_code'): ?>
        const checkPaymentButton = document.getElementById('check-payment');
        const transactionId = '<?php echo htmlspecialchars($transaction_id); ?>';
        const userId = '<?php echo htmlspecialchars($user_id); ?>';
        const items = <?php echo json_encode($items); ?>;
        let checkCount = 0;
        let checkInterval;
        let isChecking = false;
        
        // Function to check payment status
        async function checkPaymentStatus() {
            if (isChecking) return; // Prevent multiple simultaneous checks
            
            isChecking = true;
            checkCount++;
            
            try {
                // Update button text to show checking status
                if (checkPaymentButton) {
                    checkPaymentButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Đang kiểm tra...';
                    checkPaymentButton.disabled = true;
                }
                
                const response = await fetch('http://localhost:4070/check-transaction', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        order_id: '<?php echo htmlspecialchars($transaction_id); ?>',
                        description: '<?php echo htmlspecialchars($qr_info['description']); ?>',
                        amount: <?php echo $amount; ?>,
                        user_id: userId,
                        items: items
                    })
                });
                const result = await response.json();
                
                if (result.success) {
                    // Payment successful
                    clearInterval(checkInterval); // Stop checking
                    alert('Thanh toán thành công! Email xác nhận đã được gửi.');
                    window.location.href = 'order-confirmation.php?order_group_id=<?php echo $order_group_id; ?>';
                } else {
                    // Payment not found or failed
                    if (checkPaymentButton) {
                        checkPaymentButton.innerHTML = '<i class="fas fa-check-circle me-2"></i> Kiểm tra thanh toán';
                        checkPaymentButton.disabled = false;
                    }
                    
                    // Only show alert every 12 checks (approximately 1 minute) to avoid spam
                    if (checkCount % 12 === 0) {
                        console.log('Đã kiểm tra ' + checkCount + ' lần. Chưa nhận được thanh toán.');
                        // Uncomment if you want to show notification
                        // alert('Chưa nhận được thanh toán. Hệ thống sẽ tiếp tục kiểm tra tự động.');
                    }
                }
            } catch (error) {
                console.error('Error checking payment:', error);
                if (checkPaymentButton) {
                    checkPaymentButton.innerHTML = '<i class="fas fa-check-circle me-2"></i> Kiểm tra thanh toán';
                    checkPaymentButton.disabled = false;
                }
            } finally {
                isChecking = false;
            }
        }
        
        // Start automatic checking every 5 seconds
        checkInterval = setInterval(checkPaymentStatus, 5000);
        
        // Also check immediately on page load
        checkPaymentStatus();
        
        // Keep manual check button functionality
        if (checkPaymentButton) {
            checkPaymentButton.addEventListener('click', checkPaymentStatus);
        }
    <?php endif; ?>
});
</script>

<?php include 'includes/footer.php'; ?>