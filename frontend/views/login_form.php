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
    <?php
    session_start();
    $error = $_SESSION['login_error'] ?? '';
    $email = $_SESSION['login_email'] ?? '';                                                                                                                                                    
    unset($_SESSION['login_error']);
    unset($_SESSION['login_email']);
    ?>
    <div class="login-container">
        <div class="logo">Apple Store</div>
        <h2>Đăng nhập</h2>

        <?php if ($error): ?>
            <div class="error"><?php echo htmlspecialchars($error); ?></div>
        <?php endif; ?>

        <form method="POST" action="../../backend/views/login.php">
            <input type="text" name="email" placeholder="Email hoặc số điện thoại" value="<?php echo htmlspecialchars($email); ?>" required>
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