<?php
// config.php
$host = 'localhost';
$dbname = 'apple_store';
$username = 'root'; // Thay bằng username MySQL của bạn
$password = 'root';     // Thay bằng password MySQL của bạn
// $dbname = 'toanphat_apple_store';
// $username = 'toanphat'; // Thay bằng username MySQL của bạn
// $password = 'qCYc7aFq#P!659'; 

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    // echo "Successfully";
} catch (PDOException $e) {
    die("Kết nối thất bại: " . $e->getMessage());
}
?>

