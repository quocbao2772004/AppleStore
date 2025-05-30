<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Kiểm tra ID đã được cung cấp
if (!isset($_GET['id']) || empty($_GET['id'])) {
    setFlashMessage('error', 'ID danh mục là bắt buộc');
    redirect('index.php');
}

$category_id = (int)$_GET['id'];

// Lấy dữ liệu danh mục
try {
    $stmt = $pdo->prepare("SELECT * FROM categories WHERE id = ?");
    $stmt->execute([$category_id]);
    $category = $stmt->fetch();
    
    if (!$category) {
        setFlashMessage('error', 'Không tìm thấy danh mục');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh mục: ' . $e->getMessage());
    redirect('index.php');
}

// Lấy sản phẩm trong danh mục này
try {
    $stmt = $pdo->prepare("SELECT id, name, price, stock, status FROM products WHERE category_id = ? ORDER BY name ASC LIMIT 10");
    $stmt->execute([$category_id]);
    $products = $stmt->fetchAll();
    
    // Lấy tổng số sản phẩm
    $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM products WHERE category_id = ?");
    $stmt->execute([$category_id]);
    $productCount = $stmt->fetch()['count'];
} catch (PDOException $e) {
    $products = [];
    $productCount = 0;
}

// Tiêu đề trang
$pageTitle = 'Xem Danh Mục';

// Thêm header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Chi Tiết Danh Mục</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="edit.php?id=<?php echo $category_id; ?>" class="btn btn-sm btn-primary me-2">
                        <i class="fas fa-edit"></i> Chỉnh Sửa Danh Mục
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại Danh Mục
                    </a>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Danh Mục</h5>
                        </div>
                        <div class="card-body">
                            <table class="table">
                                <tr>
                                    <th style="width: 150px;">ID:</th>
                                    <td><?php echo $category['id']; ?></td>
                                </tr>
                                <tr>
                                    <th>Tên:</th>
                                    <td><?php echo htmlspecialchars($category['name']); ?></td>
                                </tr>
                                <tr>
                                    <th>Đường Dẫn:</th>
                                    <td><?php echo htmlspecialchars($category['slug']); ?></td>
                                </tr>
                                <tr>
                                    <th>Mô Tả:</th>
                                    <td><?php echo !empty($category['description']) ? nl2br(htmlspecialchars($category['description'])) : '<em>Chưa có mô tả</em>'; ?></td>
                                </tr>
                                <tr>
                                    <th>Ngày Tạo:</th>
                                    <td><?php echo date('d/m/Y', strtotime($category['created_at'])); ?></td>
                                </tr>
                                <tr>
                                    <th>Cập Nhật Lần Cuối:</th>
                                    <td><?php echo date('d/m/Y', strtotime($category['updated_at'])); ?></td>
                                </tr>
                                <tr>
                                    <th>Sản Phẩm:</th>
                                    <td>
                                        <span class="badge bg-<?php echo $productCount > 0 ? 'primary' : 'secondary'; ?>">
                                            <?php echo $productCount; ?> sản phẩm
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Sản Phẩm Trong Danh Mục</h5>
                            <?php if ($productCount > 0): ?>
                            <a href="../products/index.php?category=<?php echo $category_id; ?>" class="btn btn-sm btn-light">
                                Xem Tất Cả
                            </a>
                            <?php endif; ?>
                        </div>
                        <div class="card-body">
                            <?php if (!empty($products)): ?>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Tên</th>
                                                <th>Giá</th>
                                                <th>Tồn Kho</th>
                                                <th>Trạng Thái</th>
                                                <th></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach ($products as $product): ?>
                                            <tr>
                                                <td><?php echo $product['id']; ?></td>
                                                <td><?php echo htmlspecialchars($product['name']); ?></td>
                                                <td><?php echo number_format($product['price'], 0, ',', '.'); ?>đ</td>
                                                <td><?php echo $product['stock']; ?></td>
                                                <td>
                                                    <span class="badge bg-<?php echo $product['status'] === 'active' ? 'success' : 'danger'; ?>">
                                                        <?php echo $product['status'] === 'active' ? 'Hoạt Động' : 'Không Hoạt Động'; ?>
                                                    </span>
                                                </td>
                                                <td>
                                                    <a href="../products/view.php?id=<?php echo $product['id']; ?>" class="btn btn-sm btn-info">
                                                        <i class="fas fa-eye"></i>
                                                    </a>
                                                </td>
                                            </tr>
                                            <?php endforeach; ?>
                                        </tbody>
                                    </table>
                                </div>
                                
                                <?php if ($productCount > count($products)): ?>
                                <div class="text-center mt-3">
                                    <a href="../products/index.php?category=<?php echo $category_id; ?>" class="btn btn-primary">
                                        Xem Tất Cả <?php echo $productCount; ?> Sản Phẩm
                                    </a>
                                </div>
                                <?php endif; ?>
                                
                            <?php else: ?>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i> Chưa có sản phẩm nào trong danh mục này.
                                </div>
                                <div class="text-center">
                                    <a href="../products/create.php?category=<?php echo $category_id; ?>" class="btn btn-primary">
                                        <i class="fas fa-plus"></i> Thêm Sản Phẩm Vào Danh Mục
                                    </a>
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>