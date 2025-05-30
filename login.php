<?php
require_once 'includes/functions.php';
require_once 'includes/auth.php';
require_once 'config/database.php';

// Chuyển hướng nếu đã đăng nhập
if (isLoggedIn()) {
    redirect('index.php');
}

// Lấy URL chuyển hướng nếu có
$redirect = isset($_GET['redirect']) ? $_GET['redirect'] : 'index.php';

// Xử lý gửi form
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = clean($_POST['email']);
    $password = $_POST['password'];
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if (empty($email)) {
        $errors[] = 'Email là bắt buộc';
    }
    
    if (empty($password)) {
        $errors[] = 'Mật khẩu là bắt buộc';
    }
    
    // Nếu không có lỗi, thử đăng nhập
    if (empty($errors)) {
        $result = loginUser($email, $password);
        
        if ($result['success']) {
            setFlashMessage('success', 'Đăng nhập thành công. Chào mừng bạn trở lại, ' . $_SESSION['user_name'] . '!');
            redirect($redirect);
        } else {
            setFlashMessage('error', $result['message']);
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Tiêu đề trang
$pageTitle = 'Đăng Nhập';

// Thêm header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card shadow">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Đăng Nhập</h4>
                </div>
                <div class="card-body">
                    <form action="" method="POST">
                        <input type="hidden" name="redirect" value="<?php echo htmlspecialchars($redirect); ?>">
                        
                        <div class="mb-3">
                            <label for="email" class="form-label">Địa Chỉ Email</label>
                            <input type="email" class="form-control" id="email" name="email" required value="<?php echo isset($_POST['email']) ? htmlspecialchars($_POST['email']) : ''; ?>">
                        </div>
                        
                        <div class="mb-3">
                            <label for="password" class="form-label">Mật Khẩu</label>
                            <input type="password" class="form-control" id="password" name="password" required>
                        </div>
                        
                        <div class="mb-3 form-check">
                            <input type="checkbox" class="form-check-input" id="remember" name="remember">
                            <label class="form-check-label" for="remember">Ghi nhớ đăng nhập</label>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Đăng Nhập</button>
                        </div>
                    </form>
                </div>
                <div class="card-footer text-center">
                    <p class="mb-0">Chưa có tài khoản? <a href="register.php<?php echo !empty($redirect) ? '?redirect=' . urlencode($redirect) : ''; ?>">Đăng Ký</a></p>
                </div>
            </div>
        </div>
    </div>
</div>

<?php include 'includes/footer.php'; ?>