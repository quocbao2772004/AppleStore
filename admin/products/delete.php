<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Kiểm tra ID được cung cấp qua POST hoặc GET
if ((!isset($_POST['id']) || empty($_POST['id'])) && (!isset($_GET['id']) || empty($_GET['id']))) {
    setFlashMessage('error', 'ID sản phẩm là bắt buộc');
    redirect('index.php');
}

// Lấy ID sản phẩm từ POST hoặc GET
$product_id = (int)(isset($_POST['id']) ? $_POST['id'] : $_GET['id']);

// Lấy thông tin sản phẩm để kiểm tra tồn tại và lấy tên file ảnh
try {
    $stmt = $pdo->prepare("SELECT id, name, image FROM products WHERE id = ?");
    $stmt->execute([$product_id]);
    $product = $stmt->fetch();
    
    if (!$product) {
        setFlashMessage('error', 'Không tìm thấy sản phẩm');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin sản phẩm: ' . $e->getMessage());
    redirect('index.php');
}

// Xóa sản phẩm
try {
    // Bắt đầu giao dịch
    $pdo->beginTransaction();
    
    // Xóa sản phẩm
    $stmt = $pdo->prepare("DELETE FROM products WHERE id = ?");
    $stmt->execute([$product_id]);
    
    // Xóa ảnh sản phẩm nếu không phải ảnh mặc định                                                                                                                                                     
    if (!empty($product['image']) && $product['image'] !== 'default.jpg') {
        $image_path = '../../uploads/products/' . $product['image'];
        if (file_exists($image_path)) {
            unlink($image_path);
        }
    }
    
    // Hoàn tất giao dịch
    $pdo->commit();
    
    setFlashMessage('success', 'Đã xóa sản phẩm "' . htmlspecialchars($product['name']) . '" thành công');
    redirect('index.php');
} catch (PDOException $e) {
    // Hoàn tác giao dịch nếu có lỗi
    $pdo->rollBack();
    setFlashMessage('error', 'Lỗi khi xóa sản phẩm: ' . $e->getMessage());
    redirect('index.php');
}
?>