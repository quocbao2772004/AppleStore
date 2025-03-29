<?php

session_start();

require_once '../../backend/config/config.php';

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') 
{
    $fullname = trim($_POST['fullname'] ?? '');
    $email = trim($_POST['email'] ?? '');
    $phone = trim($_POST['phone'] ?? '');
    $password = trim($_POST['password'] ?? '');
    $confirm_password = trim($_POST['confirm_password'] ?? '');

    if ($fullname && $email && $phone && $password && $confirm_password) 
    {
        if ($password === $confirm_password) 
        {
            $stmt = $pdo->prepare("SELECT COUNT(*) FROM users WHERE email = ?");
            $stmt->execute([$email]);
            if ($stmt->fetchColumn() > 0) 
            {
                $error = "Email đã được sử dụng!";
            } 
            else 
            {
                $hashed_password = password_hash($password, PASSWORD_DEFAULT);
                $stmt = $pdo->prepare("INSERT INTO users (fullname, email, phone, password) VALUES (?, ?, ?, ?)");
                $stmt->execute([$fullname, $email, $phone, $hashed_password]);
                $_SESSION['user'] = $email;
                header("Location: login.php");
                exit();
            }
        } 
        else 
        {
            $error = "Mật khẩu xác nhận không khớp!";
        }
    } 
    else 
    {
        $error = "Vui lòng nhập đầy đủ thông tin!";
    }
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đăng ký - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/login.css" />
</head>
<body>
    <div class="register-container">
        <div class="logo">Apple Store</div>
        <h2>Đăng ký</h2>

        <?php if ($error): ?>
            <div class="error"><?php echo htmlspecialchars($error); ?></div>
        <?php endif; ?>

        <form method="POST" action="">
            <input type="text" name="fullname" placeholder="Họ và tên" value="<?php echo htmlspecialchars($fullname); ?>" required>
            <input type="email" name="email" placeholder="Email" value="<?php echo htmlspecialchars($email); ?>" required>
            <input type="tel" name="phone" placeholder="Số điện thoại" value="<?php echo htmlspecialchars($phone); ?>" required>
            <input type="password" name="password" placeholder="Mật khẩu" required>
            <input type="password" name="confirm_password" placeholder="Xác nhận mật khẩu" required>
            <button type="submit">Đăng ký</button>
        </form>

        <div class="login-link">
            Đã có tài khoản? <a href="login_form.php">Đăng nhập ngay</a>
        </div>
    </div>
</body>
</html>