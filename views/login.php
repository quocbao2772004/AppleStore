<?php
// Khởi tạo session
session_start();

// Kết nối cơ sở dữ liệu
require_once '../config/config.php';

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = trim($_POST['email'] ?? '');
    $password = trim($_POST['password'] ?? '');

    // Kiểm tra dữ liệu đầu vào
    if ($email && $password) {
        // Kiểm tra thông tin đăng nhập
        $stmt = $pdo->prepare("SELECT * FROM users WHERE email = ?");
        $stmt->execute([$email]);
        $user = $stmt->fetch(PDO::FETCH_ASSOC);

        if ($user && password_verify($password, $user['password'])) {
            // Lưu user_id vào session thay vì email
            $_SESSION['user_id'] = $user['id'];
            // Tùy chọn: Lưu thêm thông tin khác nếu cần
            $_SESSION['user_email'] = $user['email']; // Nếu bạn vẫn muốn giữ email
            header('Location: ../index.php');
            exit();
        } else {
            $error = "Email hoặc mật khẩu không đúng!";
        }
    } else {
        $error = "Vui lòng nhập đầy đủ thông tin!";
    }
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đăng nhập - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/login.css" />
</head>
<body>
    <div class="login-container">
        <div class="logo">Apple Store</div>
        <h2>Đăng nhập</h2>

        <?php if ($error): ?>
            <div class="error"><?php echo htmlspecialchars($error); ?></div>
        <?php endif; ?>

        <form method="POST" action="">
            <input type="text" name="email" placeholder="Email hoặc số điện thoại" value="<?php echo isset($email) ? htmlspecialchars($email) : ''; ?>" required>
            <input type="password" name="password" placeholder="Mật khẩu" required>
            <button type="submit">Đăng nhập</button>
        </form>

        <div class="forgot-password">
            <a href="#quen-mat-khau">Quên mật khẩu?</a>
        </div>

        <div class="register-link">
            Bạn chưa có tài khoản? <a href="register.php">Đăng ký ngay</a>
        </div>
    </div>
</body>
</html>