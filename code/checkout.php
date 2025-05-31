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
    redirect('login.php?redirect=checkout.php');
}

// Get user information
$user_id = $_SESSION['user_id'];
try {
    $stmt = $pdo->prepare("SELECT id, name, phone FROM users WHERE id = ?");
    $stmt->execute([$user_id]);
    $user = $stmt->fetch();
    if (!$user) {
        setFlashMessage('error', 'Không tìm thấy thông tin người dùng');
        redirect('logout.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin người dùng: ' . $e->getMessage());
    redirect('cart.php');
}

// Get cart items from database
try {
    $stmt = $pdo->prepare("
        SELECT c.id AS cart_id, c.product_id, c.quantity, p.name, p.price, p.stock, p.image, p.slug
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ");
    $stmt->execute([$user_id]);
    $cart_items = $stmt->fetchAll(PDO::FETCH_ASSOC);
    
    if (empty($cart_items)) {
        setFlashMessage('error', 'Giỏ hàng của bạn đang trống');
        redirect('cart.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin giỏ hàng: ' . $e->getMessage());
    redirect('cart.php');
}

// Calculate cart totals
$total_price = 0;
$total_items = 0;

foreach ($cart_items as $item) {
    if ($item['stock'] < $item['quantity']) {
        setFlashMessage('error', 'Không đủ hàng cho "' . htmlspecialchars($item['name']) . '". Chỉ còn ' . $item['stock'] . ' sản phẩm.');
        redirect('cart.php');
    }
    
    $subtotal = $item['price'] * $item['quantity'];
    $total_price += $subtotal;
    $total_items += $item['quantity'];
}

// Process checkout form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $shipping_name = clean($_POST['full_name']);
    $shipping_phone = clean($_POST['phone']);
    $shipping_address = clean($_POST['address']);
    $payment_method = clean($_POST['payment_method']);
    $notes = !empty($_POST['notes']) ? clean($_POST['notes']) : null;
    
    // Validate input
    $errors = [];
    
    if (empty($shipping_name)) {
        $errors[] = 'Vui lòng nhập họ tên';
    }
    
    if (empty($shipping_phone)) {
        $errors[] = 'Vui lòng nhập số điện thoại';
    }
    
    if (empty($shipping_address)) {
        $errors[] = 'Vui lòng nhập địa chỉ giao hàng';
    }
    
    if (empty($payment_method)) {
        $errors[] = 'Vui lòng chọn phương thức thanh toán';
    }
    
    // If no errors, process the order
    if (empty($errors)) {
        try {
            // Begin transaction
            $pdo->beginTransaction();
            
            // Generate a unique order group ID
            $order_group_id = time();
            
            // Create orders (one per cart item)
            foreach ($cart_items as $item) {
                $stmt = $pdo->prepare("
                    INSERT INTO orders (
                        user_id, total_price, status, payment_method, shipping_phone,
                        shipping_name, shipping_address, notes, product_id, quantity, order_group_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
                ");
                $stmt->execute([
                    $user_id,
                    $item['price'] * $item['quantity'],
                    'pending',
                    $payment_method,
                    $shipping_phone,
                    $shipping_name,
                    $shipping_address,
                    $notes,
                    $item['product_id'],
                    $item['quantity'],
                    $order_group_id
                ]);
            }
            
            // Handle payment method
            if ($payment_method === 'qr_code') {
                // Prepare items for QR code API
                $items_for_qr = array_map(function($item) {
                    return [
                        'product_id' => (int)$item['product_id'],
                        'quantity' => (int)$item['quantity']
                    ];
                }, $cart_items);
                
                // Call QR code generation API
                $api_url = 'http://localhost:4070/generate-qr';
                $qr_data = [
                    'items' => json_encode($items_for_qr),
                    'amount' => $total_price
                ];
                
                $ch = curl_init($api_url);
                curl_setopt($ch, CURLOPT_POST, 1);
                curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($qr_data));
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/x-www-form-urlencoded']);
                
                $response = curl_exec($ch);
                $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                
                if (curl_errno($ch)) {
                    throw new Exception('Lỗi khi gọi API QR: ' . curl_error($ch));
                }
                
                curl_close($ch);
                
                if ($http_code === 200) {
                    $qr_result = json_decode($response, true);
                    error_log("QR API Response: " . print_r($qr_result, true));
                    
                    if ($qr_result && isset($qr_result['success']) && $qr_result['success']) {
                        // Store QR info in session
                        $_SESSION['qr_info'] = [
                            'order_id' => $qr_result['order_id'],
                            'description' => $qr_result['description'],
                            'qr_code' => $qr_result['qr_code'],
                            'amount' => $total_price,
                            'order_group_id' => $order_group_id
                        ];
                        
                        // Clear cart
                        $stmt = $pdo->prepare("DELETE FROM cart WHERE user_id = ?");
                        $stmt->execute([$user_id]);
                        
                        // Commit transaction
                        $pdo->commit();
                        
                        // Redirect to payment page
                        redirect('payment.php?order_group_id=' . $order_group_id);
                    } else {
                        throw new Exception('Lỗi từ API QR: ' . ($qr_result['message'] ?? 'Không xác định'));
                    }
                } else {
                    throw new Exception('Lỗi khi gọi API QR: HTTP ' . $http_code);
                }
            } else {
                // For cash on delivery
                $stmt = $pdo->prepare("DELETE FROM cart WHERE user_id = ?");
                $stmt->execute([$user_id]);
                
                // Commit transaction
                $pdo->commit();
                
                setFlashMessage('success', 'Đơn hàng đã được đặt thành công');
                redirect('order-confirmation.php?order_group_id=' . $order_group_id);
            }
        } catch (Exception $e) {
            // Rollback transaction on error
            $pdo->rollBack();
            setFlashMessage('error', 'Lỗi khi xử lý đơn hàng: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Page title
$pageTitle = 'Thanh toán';

// Include header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <div class="col-lg-8">
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h4 class="mb-0">Thanh toán</h4>
                </div>
                <div class="card-body">
                    <form action="" method="POST" id="checkout-form">
                        <h5 class="mb-3">Thông tin giao hàng</h5>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="full_name" class="form-label">Họ tên <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="full_name" name="full_name" 
                                       value="<?php echo htmlspecialchars($user['name']); ?>" required>
                            </div>
                            <div class="col-md-6">
                                <label for="phone" class="form-label">Số điện thoại <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="phone" name="phone" 
                                       value="<?php echo htmlspecialchars($user['phone']); ?>" required>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="address" class="form-label">Địa chỉ giao hàng <span class="text-danger">*</span></label>
                            <textarea class="form-control" id="address" name="address" rows="3" 
                                      placeholder="Nhập địa chỉ giao hàng" required></textarea>
                        </div>
                        
                        <hr class="my-4">
                        
                        <h5 class="mb-3">Phương thức thanh toán</h5>
                        
                        <div class="mb-3">
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="radio" name="payment_method" 
                                       id="payment_qr" value="qr_code" checked>
                                <label class="form-check-label" for="payment_qr">
                                    <i class="fas fa-qrcode me-2"></i> Thanh toán qua mã QR
                                </label>
                            </div>
                            <div class="form-check mb-2">
                                <input class="form-check-input" type="radio" name="payment_method" 
                                       id="payment_cod" value="cash_on_delivery">
                                <label class="form-check-label" for="payment_cod">
                                    <i class="fas fa-money-bill-wave me-2"></i> Thanh toán khi nhận hàng
                                </label>
                            </div>
                        </div>
                        
                        <hr class="my-4">
                        
                        <div class="mb-3">
                            <label for="notes" class="form-label">Ghi chú đơn hàng (Không bắt buộc)</label>
                            <textarea class="form-control" id="notes" name="notes" rows="3" 
                                      placeholder="Hướng dẫn giao hàng hoặc ghi chú khác"></textarea>
                        </div>
                        
                        <div class="d-grid gap-2 mt-4">
                            <button type="submit" class="btn btn-dark btn-lg" id="submit-button">
                                <i class="fas fa-qrcode me-2"></i> Tạo mã QR thanh toán
                            </button>
                            <a href="cart.php" class="btn btn-outline-secondary">
                                <i class="fas fa-arrow-left me-2"></i> Quay lại giỏ hàng
                            </a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-lg-4">
            <!-- Order Summary -->
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h5 class="mb-0">Tổng đơn hàng</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <h6>Sản phẩm (<?php echo $total_items; ?>)</h6>
                        <div class="list-group">
                            <?php foreach ($cart_items as $item): ?>
                                <div class="list-group-item d-flex justify-content-between lh-sm py-3">
                                    <div>
                                        <h6 class="my-0"><?php echo htmlspecialchars($item['name']); ?></h6>
                                        <small class="text-muted">
                                            Số lượng: <?php echo $item['quantity']; ?> x 
                                            <?php echo number_format($item['price'], 0, '.', ',') . '₫'; ?>
                                        </small>
                                    </div>
                                    <span class="text-muted">
                                        <?php echo number_format($item['price'] * $item['quantity'], 0, '.', ',') . '₫'; ?>
                                    </span>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    </div>
                    
                    <hr>
                    
                    <div class="d-flex justify-content-between mb-2">
                        <span>Tạm tính:</span>
                        <span><?php echo number_format($total_price, 0, '.', ',') . '₫'; ?></span>
                    </div>
                    <div class="d-flex justify-content-between mb-2">
                        <span>Phí vận chuyển:</span>
                        <span>Tính khi thanh toán</span>
                    </div>
                    <div class="d-flex justify-content-between mb-2">
                        <span>Thuế:</span>
                        <span>Tính khi thanh toán</span>
                    </div>
                    <hr>
                    <div class="d-flex justify-content-between mb-2">
                        <strong>Tổng cộng:</strong>
                        <strong class="text-dark"><?php echo number_format($total_price, 0, '.', ',') . '₫'; ?></strong>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Auto-fill phone if available
    const phoneField = document.getElementById('phone');
    if (!phoneField.value && '<?php echo htmlspecialchars($user['phone'] ?? ''); ?>' !== '') {
        phoneField.value = '<?php echo htmlspecialchars($user['phone'] ?? ''); ?>';
    }
    
    // Handle payment method change
    const paymentMethods = document.querySelectorAll('input[name="payment_method"]');
    const submitButton = document.getElementById('submit-button');
    
    paymentMethods.forEach(method => {
        method.addEventListener('change', function() {
            if (this.value === 'qr_code') {
                submitButton.innerHTML = '<i class="fas fa-qrcode me-2"></i> Tạo mã QR thanh toán';
            } else {
                submitButton.innerHTML = '<i class="fas fa-check-circle me-2"></i> Đặt hàng';
            }
        });
    });
});
</script>

<?php include 'includes/footer.php'; ?>