<?php
session_start();

unset($_SESSION['user_id']);
unset($_SESSION['user_email']); 
session_destroy();
header("Location: login_form.php");
exit();
?>