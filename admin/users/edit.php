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

// Xử lý gửi form
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name = clean($_POST['name']);
    $email = clean($_POST['email']);
    $role = clean($_POST['role']);
    $phone = !empty($_POST['phone']) ? clean($_POST['phone']) : null;
    $address = !empty($_POST['address']) ? clean($_POST['address']) : null;
    $change_password = isset($_POST['change_password']) && $_POST['change_password'] === '1';
    $password = $change_password ? $_POST['password'] : '';
    $confirm_password = $change_password ? $_POST['confirm_password'] : '';
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if (empty($name)) {
        $errors[] = 'Họ tên là bắt buộc';
    }
    
    if (empty($email)) {
        $errors[] = 'Email là bắt buộc';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $errors[] = 'Email không hợp lệ';
    }
    
    if (empty($role)) {
        $errors[] = 'Vai trò là bắt buộc';
    }
    
    // Kiểm tra email đã tồn tại chưa (trừ người dùng hiện tại)
    if ($email !== $user['email']) {
        try {
            $stmt = $pdo->prepare("SELECT id FROM users WHERE email = ? AND id != ?");
            $stmt->execute([$email, $user_id]);
            if ($stmt->rowCount() > 0) {
                $errors[] = 'Email đã tồn tại';
            }
        } catch (PDOException $e) {
            $errors[] = 'Lỗi khi kiểm tra email: ' . $e->getMessage();
        }
    }
    
    // Kiểm tra mật khẩu nếu thay đổi
    if ($change_password) {
        if (empty($password)) {
            $errors[] = 'Mật khẩu là bắt buộc';
        } elseif (strlen($password) < 6) {
            $errors[] = 'Mật khẩu phải có ít nhất 6 ký tự';
        }
        
        if ($password !== $confirm_password) {
            $errors[] = 'Mật khẩu không khớp';
        }
    }
    
    // Nếu không có lỗi, cập nhật người dùng
    if (empty($errors)) {
        try {
            if ($change_password) {
                // Mã hóa mật khẩu mới
                $hashed_password = password_hash($password, PASSWORD_DEFAULT);
                
                $stmt = $pdo->prepare("
                    UPDATE users 
                    SET name = ?, email = ?, password = ?, role = ?, phone = ?, address = ?, updated_at = NOW() 
                    WHERE id = ?
                ");
                $stmt->execute([$name, $email, $hashed_password, $role, $phone, $address, $user_id]);
            } else {
                $stmt = $pdo->prepare("
                    UPDATE users 
                    SET name = ?, email = ?, role = ?, phone = ?, address = ?, updated_at = NOW() 
                    WHERE id = ?
                ");
                $stmt->execute([$name, $email, $role, $phone, $address, $user_id]);
            }
            
            setFlashMessage('success', 'Cập nhật người dùng thành công');
            redirect('index.php');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật người dùng: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Tiêu đề trang
$pageTitle = 'Chỉnh sửa người dùng';

// Include header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Chỉnh sửa người dùng</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="view.php?id=<?php echo $user_id; ?>" class="btn btn-sm btn-info me-2">
                        <i class="fas fa-eye"></i> Xem người dùng
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay lại danh sách
                    </a>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-body">
                            <form action="" method="POST">
                                <div class="mb-3">
                                    <label for="name" class="form-label">Họ tên <span class="text-danger">*</span></label>
                                    <input type="text" class="form-control" id="name" name="name" value="<?php echo htmlspecialchars($user['name']); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email" class="form-label">Địa chỉ email <span class="text-danger">*</span></label>
                                    <input type="email" class="form-control" id="email" name="email" value="<?php echo htmlspecialchars($user['email']); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role" class="form-label">Vai trò <span class="text-danger">*</span></label>
                                    <select class="form-select" id="role" name="role" required>
                                        <option value="admin" <?php echo $user['role'] === 'admin' ? 'selected' : ''; ?>>Quản trị viên</option>
                                        <option value="customer" <?php echo $user['role'] === 'customer' ? 'selected' : ''; ?>>Khách hàng</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="phone" class="form-label">Số điện thoại</label>
                                    <input type="tel" class="form-control" id="phone" name="phone" value="<?php echo htmlspecialchars($user['phone'] ?? ''); ?>">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="address" class="form-label">Địa chỉ</label>
                                    <textarea class="form-control" id="address" name="address" rows="3"><?php echo htmlspecialchars($user['address'] ?? ''); ?></textarea>
                                </div>
                                
                                <div class="mb-3 form-check">
                                    <input type="checkbox" class="form-check-input" id="change_password" name="change_password" value="1">
                                    <label class="form-check-label" for="change_password">Đổi mật khẩu</label>
                                </div>
                                
                                <div id="password_fields" style="display: none;">
                                    <div class="row mb-3">
                                        <div class="col-md-6">
                                            <label for="password" class="form-label">Mật khẩu mới</label>
                                            <input type="password" class="form-control" id="password" name="password">
                                            <small class="text-muted">Mật khẩu phải có ít nhất 6 ký tự</small>
                                        </div>
                                        <div class="col-md-6">
                                            <label for="confirm_password" class="form-label">Xác nhận mật khẩu mới</label>
                                            <input type="password" class="form-control" id="confirm_password" name="confirm_password">
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="d-grid gap-2">
                                    <button type="submit" class="btn btn-primary">Cập nhật người dùng</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông tin người dùng</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>ID:</strong> <?php echo $user['id']; ?></p>
                            <p><strong>Ngày đăng ký:</strong> <?php echo date('d/m/Y', strtotime($user['created_at'])); ?></p>
                            <p><strong>Cập nhật lần cuối:</strong> <?php echo date('d/m/Y', strtotime($user['updated_at'])); ?></p>
                            
                            <?php
                            // Lấy số lượng đơn hàng
                            try {
                                $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM orders WHERE user_id = ?");
                                $stmt->execute([$user_id]);
                                $orderCount = $stmt->fetch()['count'];
                            } catch (PDOException $e) {
                                $orderCount = 0;
                            }
                            
                            // Lấy số lượng đánh giá
                            try {
                                $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM reviews WHERE user_id = ?");
                                $stmt->execute([$user_id]);
                                $reviewCount = $stmt->fetch()['count'];
                            } catch (PDOException $e) {
                                $reviewCount = 0;
                            }
                            ?>
                            
                            <p>
                                <strong>Đơn hàng:</strong> 
                                <?php if ($orderCount > 0): ?>
                                    <a href="../orders/index.php?user_id=<?php echo $user_id; ?>" class="badge bg-primary">
                                        <?php echo $orderCount; ?> đơn hàng
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 đơn hàng</span>
                                <?php endif; ?>
                            </p>
                            
                            <p>
                                <strong>Đánh giá:</strong> 
                                <?php if ($reviewCount > 0): ?>
                                    <a href="../reviews/index.php?user_id=<?php echo $user_id; ?>" class="badge bg-primary">
                                        <?php echo $reviewCount; ?> đánh giá
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 đánh giá</span>
                                <?php endif; ?>
                            </p>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Lưu ý</h5>
                        </div>
                        <div class="card-body">
                            <ul class="list-unstyled">
                                <li><i class="fas fa-info-circle text-primary me-2"></i> Quản trị viên có toàn quyền truy cập vào trang quản trị.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Khách hàng chỉ có thể truy cập vào trang chủ.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Chỉ thay đổi mật khẩu khi cần thiết.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Đảm bảo sử dụng mật khẩu mạnh cho tài khoản quản trị.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<script>
// Hiển thị/ẩn trường mật khẩu
document.getElementById('change_password').addEventListener('change', function() {
    const passwordFields = document.getElementById('password_fields');
    passwordFields.style.display = this.checked ? 'block' : 'none';
    
    // Bật/tắt thuộc tính required cho các trường mật khẩu
    const passwordInputs = passwordFields.querySelectorAll('input');
    passwordInputs.forEach(input => {
        input.required = this.checked;
    });
});
</script>

<?php include '../includes/footer.php'; ?>