<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Check if user is logged in and is admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Check if ID is provided
if (!isset($_GET['id']) || empty($_GET['id'])) {
    setFlashMessage('error', 'ID sản phẩm là bắt buộc');
    redirect('index.php');
}

$product_id = (int)$_GET['id'];

// Get product data
try {
    $stmt = $pdo->prepare("
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    ");
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

// Get product reviews
try {
    $stmt = $pdo->prepare("
        SELECT r.*, u.name as user_name 
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = ?
        ORDER BY r.created_at DESC
        LIMIT 5
    ");
    $stmt->execute([$product_id]);
    $reviews = $stmt->fetchAll();
    
    // Get total review count
    $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM reviews WHERE product_id = ?");
    $stmt->execute([$product_id]);
    $reviewCount = $stmt->fetch()['count'];
    
    // Get average rating
    $stmt = $pdo->prepare("SELECT AVG(rating) as avg_rating FROM reviews WHERE product_id = ? AND status = 'approved'");
    $stmt->execute([$product_id]);
    $avgRating = $stmt->fetch()['avg_rating'];
} catch (PDOException $e) {
    $reviews = [];
    $reviewCount = 0;
    $avgRating = 0;
}

// Get product orders
try {
    $stmt = $pdo->prepare("
        SELECT o.*, u.name as user_name 
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.product_id = ?
        ORDER BY o.created_at DESC
        LIMIT 5
    ");
    $stmt->execute([$product_id]);
    $orders = $stmt->fetchAll();
    
    // Get total order count
    $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM orders WHERE product_id = ?");
    $stmt->execute([$product_id]);
    $orderCount = $stmt->fetch()['count'];
    
    // Get total sales
    $stmt = $pdo->prepare("SELECT SUM(quantity) as total_sold FROM orders WHERE product_id = ?");
    $stmt->execute([$product_id]);
    $totalSold = $stmt->fetch()['total_sold'] ?? 0;
} catch (PDOException $e) {
    $orders = [];
    $orderCount = 0;
    $totalSold = 0;
}

// Page title
$pageTitle = 'Xem Sản Phẩm';

// Include header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Main content -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Chi Tiết Sản Phẩm</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="edit.php?id=<?php echo $product_id; ?>" class="btn btn-sm btn-primary me-2">
                        <i class="fas fa-edit"></i> Sửa Sản Phẩm
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại
                    </a>
                </div>
            </div>
            
            <div class="row">
                <!-- Product Information -->
                <div class="col-md-8 mb-4">
                    <div class="card">
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-4 text-center">
                                    <img src="../../uploads/products/<?php echo !empty($product['image']) ? $product['image'] : 'default.jpg'; ?>" 
                                         alt="<?php echo htmlspecialchars($product['name']); ?>" 
                                         class="img-fluid rounded mb-3" style="max-height: 200px;">
                                </div>
                                <div class="col-md-8">
                                    <h3><?php echo htmlspecialchars($product['name']); ?></h3>
                                    <p class="text-muted">Mã SP: <?php echo htmlspecialchars($product['sku']); ?></p>
                                    
                                    <div class="d-flex align-items-center mb-2">
                                        <span class="badge bg-success me-2">
                                            Có sẵn
                                        </span>
                                        
                                        <?php if ($avgRating > 0): ?>
                                        <div class="ms-2">
                                            <?php for ($i = 1; $i <= 5; $i++): ?>
                                                <?php if ($i <= round($avgRating)): ?>
                                                    <i class="fas fa-star text-warning"></i>
                                                <?php elseif ($i - 0.5 <= $avgRating): ?>
                                                    <i class="fas fa-star-half-alt text-warning"></i>
                                                <?php else: ?>
                                                    <i class="far fa-star text-warning"></i>
                                                <?php endif; ?>
                                            <?php endfor; ?>
                                            <span class="ms-1">(<?php echo number_format($avgRating, 1); ?>)</span>
                                        </div>
                                        <?php endif; ?>
                                    </div>
                                    
                                    <h4 class="text-primary mb-3"><?php echo number_format($product['price'], 0, ',', '.'); ?>đ</h4>
                                    
                                    <div class="mb-3">
                                        <strong>Danh mục:</strong> 
                                        <?php if (!empty($product['category_id'])): ?>
                                            <a href="../categories/view.php?id=<?php echo $product['category_id']; ?>">
                                                <?php echo htmlspecialchars($product['category_name']); ?>
                                            </a>
                                        <?php else: ?>
                                            <em>Chưa phân loại</em>
                                        <?php endif; ?>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <strong>Tồn kho:</strong> 
                                        <span class="badge bg-<?php echo $product['stock'] > 0 ? 'info' : 'warning'; ?>">
                                            <?php echo $product['stock']; ?> sản phẩm
                                        </span>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <strong>Đã bán:</strong> <?php echo $totalSold; ?> sản phẩm
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mt-4">
                                <h5>Mô tả</h5>
                                <div class="p-3 bg-light rounded">
                                    <?php echo !empty($product['description']) ? nl2br(htmlspecialchars($product['description'])) : '<em>Chưa có mô tả</em>'; ?>
                                </div>
                            </div>
                            
                            <?php if (!empty($product['specifications'])): ?>
                            <div class="mt-4">
                                <h5>Thông số kỹ thuật</h5>
                                <div class="p-3 bg-light rounded">
                                    <?php echo nl2br(htmlspecialchars($product['specifications'])); ?>
                                </div>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
                
                <!-- Product Details -->
                <div class="col-md-4 mb-4">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Sản Phẩm</h5>
                        </div>
                        <div class="card-body">
                            <table class="table">
                                <tr>
                                    <th>ID:</th>
                                    <td><?php echo $product['id']; ?></td>
                                </tr>
                                <tr>
                                    <th>Mã SP:</th>
                                    <td><?php echo htmlspecialchars($product['sku']); ?></td>
                                </tr>
                                <tr>
                                    <th>Ngày tạo:</th>
                                    <td><?php echo date('d/m/Y', strtotime($product['created_at'])); ?></td>
                                </tr>
                                <tr>
                                    <th>Cập nhật:</th>
                                    <td><?php echo date('d/m/Y', strtotime($product['updated_at'])); ?></td>
                                </tr>
                                <tr>
                                    <th>Trạng thái:</th>
                                    <td>
                                        <span class="badge bg-success">
                                            Có sẵn
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <th>Nổi bật:</th>
                                    <td>
                                        <span class="badge bg-<?php echo $product['featured'] ? 'primary' : 'secondary'; ?>">
                                            <?php echo $product['featured'] ? 'Có' : 'Không'; ?>
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <th>Khối lượng:</th>
                                    <td><?php echo !empty($product['weight']) ? $product['weight'] . ' kg' : 'N/A'; ?></td>
                                </tr>
                                <tr>
                                    <th>Kích thước:</th>
                                    <td><?php echo !empty($product['dimensions']) ? htmlspecialchars($product['dimensions']) : 'N/A'; ?></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thao Tác Nhanh</h5>
                        </div>
                        <div class="card-body">
                            <div class="d-grid gap-2">
                                <a href="edit.php?id=<?php echo $product_id; ?>" class="btn btn-primary">
                                    <i class="fas fa-edit"></i> Sửa Sản Phẩm
                                </a>
                                <a href="../../product.php?id=<?php echo $product_id; ?>" class="btn btn-info" target="_blank">
                                    <i class="fas fa-eye"></i> Xem Trên Website
                                </a>
                                <button type="button" class="btn btn-danger" data-bs-toggle="modal" data-bs-target="#deleteProductModal">
                                    <i class="fas fa-trash"></i> Xóa Sản Phẩm
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Reviews -->
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Đánh Giá Gần Đây</h5>
                            <?php if ($reviewCount > 0): ?>
                            <a href="../reviews/index.php?product_id=<?php echo $product_id; ?>" class="btn btn-sm btn-light">
                                Xem Tất Cả
                            </a>
                            <?php endif; ?>
                        </div>
                        <div class="card-body">
                            <?php if (!empty($reviews)): ?>
                                <div class="list-group">
                                    <?php foreach ($reviews as $review): ?>
                                    <div class="list-group-item">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <h6 class="mb-1">
                                                <a href="../users/view.php?id=<?php echo $review['user_id']; ?>">
                                                    <?php echo htmlspecialchars($review['user_name']); ?>
                                                </a>
                                            </h6>
                                            <small><?php echo date('d/m/Y', strtotime($review['created_at'])); ?></small>
                                        </div>
                                        <div class="mb-2">
                                            <?php for ($i = 1; $i <= 5; $i++): ?>
                                                <?php if ($i <= $review['rating']): ?>
                                                    <i class="fas fa-star text-warning"></i>
                                                <?php else: ?>
                                                    <i class="far fa-star text-warning"></i>
                                                <?php endif; ?>
                                            <?php endfor; ?>
                                            <span class="badge bg-<?php 
                                                echo $review['status'] === 'approved' ? 'success' : 
                                                    ($review['status'] === 'rejected' ? 'danger' : 'warning'); 
                                            ?> ms-2">
                                                <?php 
                                                echo $review['status'] === 'approved' ? 'Đã duyệt' : 
                                                    ($review['status'] === 'rejected' ? 'Từ chối' : 'Chờ duyệt'); 
                                                ?>
                                            </span>
                                        </div>
                                        <p class="mb-1">
                                            <?php 
                                            $comment = htmlspecialchars($review['comment']);
                                            echo strlen($comment) > 100 ? substr($comment, 0, 100) . '...' : $comment;
                                            ?>
                                        </p>
                                        <div class="text-end">
                                            <a href="../reviews/view.php?id=<?php echo $review['id']; ?>" class="btn btn-sm btn-info">
                                                <i class="fas fa-eye"></i> Xem
                                            </a>
                                        </div>
                                    </div>
                                    <?php endforeach; ?>
                                </div>
                                
                                <?php if ($reviewCount > count($reviews)): ?>
                                <div class="text-center mt-3">
                                    <a href="../reviews/index.php?product_id=<?php echo $product_id; ?>" class="btn btn-primary">
                                        Xem Tất Cả <?php echo $reviewCount; ?> Đánh Giá
                                    </a>
                                </div>
                                <?php endif; ?>
                                
                            <?php else: ?>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i> Chưa có đánh giá nào cho sản phẩm này.
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
                
                <!-- Orders -->
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">Đơn Hàng Gần Đây</h5>
                            <?php if ($orderCount > 0): ?>
                            <a href="../orders/index.php?product_id=<?php echo $product_id; ?>" class="btn btn-sm btn-light">
                                Xem Tất Cả
                            </a>
                            <?php endif; ?>
                        </div>
                        <div class="card-body">
                            <?php if (!empty($orders)): ?>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Khách hàng</th>
                                                <th>SL</th>
                                                <th>Tổng tiền</th>
                                                <th>Trạng thái</th>
                                                <th>Ngày</th>
                                                <th></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach ($orders as $order): ?>
                                            <tr>
                                                <td><?php echo $order['id']; ?></td>
                                                <td>
                                                    <a href="../users/view.php?id=<?php echo $order['user_id']; ?>">
                                                        <?php echo htmlspecialchars($order['user_name']); ?>
                                                    </a>
                                                </td>
                                                <td><?php echo $order['quantity']; ?></td>
                                                <td><?php echo number_format($order['total_price'], 0, ',', '.'); ?>đ</td>
                                                <td>
                                                    <span class="badge bg-<?php 
                                                        echo $order['status'] === 'delivered' ? 'success' : 
                                                            ($order['status'] === 'cancelled' ? 'danger' : 
                                                            ($order['status'] === 'processing' ? 'primary' : 
                                                            ($order['status'] === 'shipped' ? 'info' : 'warning'))); 
                                                    ?>">
                                                        <?php 
                                                        echo $order['status'] === 'delivered' ? 'Đã giao' : 
                                                            ($order['status'] === 'cancelled' ? 'Đã hủy' : 
                                                            ($order['status'] === 'processing' ? 'Đang xử lý' : 
                                                            ($order['status'] === 'shipped' ? 'Đang giao' : 'Chờ xử lý'))); 
                                                        ?>
                                                    </span>
                                                </td>
                                                <td><?php echo date('d/m/Y', strtotime($order['created_at'])); ?></td>
                                                <td>
                                                    <a href="../orders/view.php?id=<?php echo $order['id']; ?>" class="btn btn-sm btn-info">
                                                        <i class="fas fa-eye"></i>
                                                    </a>
                                                </td>
                                            </tr>
                                            <?php endforeach; ?>
                                        </tbody>
                                    </table>
                                </div>
                                
                                <?php if ($orderCount > count($orders)): ?>
                                <div class="text-center mt-3">
                                    <a href="../orders/index.php?product_id=<?php echo $product_id; ?>" class="btn btn-primary">
                                        Xem Tất Cả <?php echo $orderCount; ?> Đơn Hàng
                                    </a>
                                </div>
                                <?php endif; ?>
                                
                            <?php else: ?>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i> Chưa có đơn hàng nào cho sản phẩm này.
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<!-- Delete Product Modal -->
<div class="modal fade" id="deleteProductModal" tabindex="-1" aria-labelledby="deleteProductModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header bg-danger text-white">
                <h5 class="modal-title" id="deleteProductModalLabel">Xóa Sản Phẩm</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <p>Bạn có chắc chắn muốn xóa sản phẩm này?</p>
                <p><strong>Tên:</strong> <?php echo htmlspecialchars($product['name']); ?></p>
                <p><strong>Mã SP:</strong> <?php echo htmlspecialchars($product['sku']); ?></p>
                
                <?php if ($orderCount > 0 || $reviewCount > 0): ?>
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i> Sản phẩm này có 
                    <?php if ($orderCount > 0): ?>
                        <strong><?php echo $orderCount; ?> đơn hàng</strong>
                    <?php endif; ?>
                    
                    <?php if ($orderCount > 0 && $reviewCount > 0): ?>
                        và 
                    <?php endif; ?>
                    
                    <?php if ($reviewCount > 0): ?>
                        <strong><?php echo $reviewCount; ?> đánh giá</strong>
                    <?php endif; ?>
                    liên quan. Việc xóa sản phẩm sẽ không xóa các bản ghi này.
                </div>
                <?php endif; ?>
                
                <p class="text-danger"><strong>Cảnh báo:</strong> Hành động này không thể hoàn tác.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                <form action="delete.php" method="POST">
                    <input type="hidden" name="id" value="<?php echo $product_id; ?>">
                    <button type="submit" class="btn btn-danger">Xóa Sản Phẩm</button>
                </form>
            </div>
        </div>
    </div>
</div>

<?php include '../includes/footer.php'; ?>