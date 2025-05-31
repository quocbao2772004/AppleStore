<?php
require_once '../includes/functions.php';
require_once '../includes/auth.php';
require_once '../config/database.php';

// Kiểm tra người dùng đã đăng nhập
if (!isLoggedIn()) {
    setFlashMessage('error', 'Vui lòng đăng nhập để truy cập hồ sơ của bạn');
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

// Xử lý cập nhật hồ sơ
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_profile'])) {
    $name = clean($_POST['name']);
    $email = clean($_POST['email']);
    $phone = !empty($_POST['phone']) ? clean($_POST['phone']) : null;
    $address = !empty($_POST['address']) ? clean($_POST['address']) : null;
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if (empty($name)) {
        $errors[] = 'Họ tên là bắt buộc';
    }
    
    if (empty($email)) {
        $errors[] = 'Email là bắt buộc';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $errors[] = 'Định dạng email không hợp lệ';
    }
    
    // Kiểm tra email đã tồn tại chưa (cho người dùng khác)
    if ($email !== $user['email']) {
        try {
            $stmt = $pdo->prepare("SELECT id FROM users WHERE email = ? AND id != ?");
            $stmt->execute([$email, $user_id]);
            if ($stmt->rowCount() > 0) {
                $errors[] = 'Email đã được sử dụng bởi tài khoản khác';
            }
        } catch (PDOException $e) {
            $errors[] = 'Lỗi khi kiểm tra email: ' . $e->getMessage();
        }
    }
    
    // Nếu không có lỗi, cập nhật hồ sơ
    if (empty($errors)) {
        try {
            $stmt = $pdo->prepare("
                UPDATE users 
                SET name = ?, email = ?, phone = ?, address = ?, created_at = NOW()
                WHERE id = ?
            ");
            $stmt->execute([$name, $email, $phone, $address, $user_id]);
            
            setFlashMessage('success', 'Cập nhật hồ sơ thành công');
            
            // Cập nhật dữ liệu phiên
            $_SESSION['user_name'] = $name;
            
            // Làm mới dữ liệu người dùng
            $stmt = $pdo->prepare("SELECT * FROM users WHERE id = ?");
            $stmt->execute([$user_id]);
            $user = $stmt->fetch();
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật hồ sơ: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Xử lý đổi mật khẩu
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['change_password'])) {
    $current_password = $_POST['current_password'];
    $new_password = $_POST['new_password'];
    $confirm_password = $_POST['confirm_password'];
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if (empty($current_password)) {
        $errors[] = 'Mật khẩu hiện tại là bắt buộc';
    }
    
    if (empty($new_password)) {
        $errors[] = 'Mật khẩu mới là bắt buộc';
    } elseif (strlen($new_password) < 6) {
        $errors[] = 'Mật khẩu mới phải có ít nhất 6 ký tự';
    }
    
    if ($new_password !== $confirm_password) {
        $errors[] = 'Mật khẩu mới không khớp';
    }
    
    // Xác minh mật khẩu hiện tại
    if (!password_verify($current_password, $user['password'])) {
        $errors[] = 'Mật khẩu hiện tại không đúng';
    }
    
    // Nếu không có lỗi, cập nhật mật khẩu
    if (empty($errors)) {
        try {
            $hashed_password = password_hash($new_password, PASSWORD_DEFAULT);
            
            $stmt = $pdo->prepare("
                UPDATE users 
                SET password = ?, created_at = NOW()
                WHERE id = ?
            ");
            $stmt->execute([$hashed_password, $user_id]);
            
            setFlashMessage('success', 'Đổi mật khẩu thành công');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi đổi mật khẩu: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Lấy đơn hàng gần đây
try {
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
} catch (PDOException $e) {
    $recent_orders = [];
}

// Tiêu đề trang
$pageTitle = 'Hồ Sơ Của Tôi';

// Fix đường dẫn tương đối cho header
$_SERVER['DOCUMENT_ROOT'] = dirname(dirname(__FILE__));
chdir($_SERVER['DOCUMENT_ROOT']);

// Include header
include 'includes/header2.php';

// Quay lại thư mục account
chdir('account');
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
                    <a href="index.php" class="list-group-item list-group-item-action">
                        <i class="fas fa-tachometer-alt me-2"></i> Bảng Điều Khiển
                    </a>
                    <a href="profile.php" class="list-group-item list-group-item-action active">
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
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Hồ Sơ Của Tôi</h5>
                </div>
                <div class="card-body">
                    <form action="" method="POST">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="name" class="form-label">Họ Tên <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="name" name="name" value="<?php echo htmlspecialchars($user['name']); ?>" required>
                            </div>
                            <div class="col-md-6">
                                <label for="email" class="form-label">Địa Chỉ Email <span class="text-danger">*</span></label>
                                <input type="email" class="form-control" id="email" name="email" value="<?php echo htmlspecialchars($user['email']); ?>" required>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="phone" class="form-label">Số Điện Thoại</label>
                                <input type="tel" class="form-control" id="phone" name="phone" value="<?php echo htmlspecialchars($user['phone'] ?? ''); ?>">
                            </div>
                            <div class="col-md-6">
                                <label for="role" class="form-label">Loại Tài Khoản</label>
                                <input type="text" class="form-control" id="role" value="<?php echo ucfirst($user['role']); ?>" readonly>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="address" class="form-label">Địa Chỉ</label>
                            <textarea class="form-control" id="address" name="address" rows="3"><?php echo htmlspecialchars($user['address'] ?? ''); ?></textarea>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="created_at" class="form-label">Thành Viên Từ</label>
                                <input type="text" class="form-control" id="created_at" value="<?php echo date('d/m/Y', strtotime($user['created_at'])); ?>" readonly>
                            </div>
                            <div class="col-md-6">
                                <label for="last_login" class="form-label">Đăng Nhập Lần Cuối</label>
                                <input type="text" class="form-control" id="last_login" value="<?php echo !empty($user['last_login']) ? date('d/m/Y H:i', strtotime($user['last_login'])) : 'N/A'; ?>" readonly>
                            </div>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" name="update_profile" class="btn btn-primary">
                                <i class="fas fa-save me-2"></i> Cập Nhật Hồ Sơ
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- Đổi Mật Khẩu -->
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Đổi Mật Khẩu</h5>
                </div>
                <div class="card-body">
                    <form action="" method="POST">
                        <div class="mb-3">
                            <label for="current_password" class="form-label">Mật Khẩu Hiện Tại <span class="text-danger">*</span></label>
                            <input type="password" class="form-control" id="current_password" name="current_password" required>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="new_password" class="form-label">Mật Khẩu Mới <span class="text-danger">*</span></label>
                                <input type="password" class="form-control" id="new_password" name="new_password" required>
                                <div class="form-text">Mật khẩu phải có ít nhất 6 ký tự.</div>
                            </div>
                            <div class="col-md-6">
                                <label for="confirm_password" class="form-label">Xác Nhận Mật Khẩu Mới <span class="text-danger">*</span></label>
                                <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                            </div>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" name="change_password" class="btn btn-primary">
                                <i class="fas fa-key me-2"></i> Đổi Mật Khẩu
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- Đơn Hàng Gần Đây -->
            <div class="card">
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
                                        <th>Mã Đơn</th>
                                        <th>Ngày Đặt</th>
                                        <th>Số SP</th>
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
                                            <td><?php echo formatPrice($order['total_amount']); ?>đ</td>
                                            <td>
                                                <span class="badge bg-<?php 
                                                    echo $order['status'] === 'delivered' ? 'success' : 
                                                        ($order['status'] === 'cancelled' ? 'danger' : 
                                                        ($order['status'] === 'processing' ? 'primary' : 
                                                        ($order['status'] === 'shipped' ? 'info' : 'warning'))); 
                                                ?>">
                                                    <?php 
                                                    $status_text = [
                                                        'pending' => 'Chờ xử lý',
                                                        'processing' => 'Đang xử lý',
                                                        'shipped' => 'Đang giao',
                                                        'delivered' => 'Đã giao',
                                                        'cancelled' => 'Đã hủy'
                                                    ];
                                                    echo $status_text[$order['status']] ?? ucfirst($order['status']); 
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
        </div>
    </div>
</div>

<?php include '../includes/footer.php'; ?>