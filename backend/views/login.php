<?php
session_start();
require_once '../../backend/config/config.php';

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') 
{
    $email = trim($_POST['email'] ?? '');
    $password = trim($_POST['password'] ?? '');

    if ($email && $password) 
    {
        $stmt = $pdo->prepare("SELECT * FROM users WHERE email = ?");
        $stmt->execute([$email]);
        $user = $stmt->fetch(PDO::FETCH_ASSOC);

        if ($user && password_verify($password, $user['password'])) 
        {
            if($user['email'] == "k100iltqbao@gmail.com")
            {
                $_SESSION['user_id'] = $user['id'];
                $_SESSION['user_email'] = $user['email']; 
                header("Location: ../../frontend/views/admin.php");
                exit();
            }
            else 
            {
                $_SESSION['user_id'] = $user['id'];
                $_SESSION['user_email'] = $user['email']; 
                header('Location: ../../index.php');
                exit();
            }
        } 
        else 
        {
            $error = "Email hoặc mật khẩu không đúng!";
        }
    } 
    else 
    {
        $error = "Vui lòng nhập đầy đủ thông tin!";
    }
}


if ($error) {
    $_SESSION['login_error'] = $error;
    $_SESSION['login_email'] = $email ?? '';
}
header('Location: ../../frontend/views/login_form.php');
exit();
?>