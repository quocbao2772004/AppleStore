<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Kiểm tra ID được cung cấp
if (!isset($_GET['id']) || empty($_GET['id'])) {
    setFlashMessage('error', 'ID đánh giá là bắt buộc');
    redirect('index.php');
}

$review_id = (int)$_GET['id'];

// Lấy dữ liệu đánh giá
try {
    $stmt = $pdo->prepare("
        SELECT r.*, u.name as user_name, u.email as user_email, p.name as product_name, p.image as product_image
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        JOIN products p ON r.product_id = p.id
        WHERE r.id = ?
    ");
    $stmt->execute([$review_id]);
    $review = $stmt->fetch();
    
    if (!$review) {
        setFlashMessage('error', 'Không tìm thấy đánh giá');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy đánh giá: ' . $e->getMessage());
    redirect('index.php');
}

// Xử lý cập nhật trạng thái đánh giá
if (isset($_POST['action'])) {
    $action = $_POST['action'];
    
    if (in_array($action, ['approve', 'reject', 'delete'])) {
        try {
            if ($action === 'approve') {
                $stmt = $pdo->prepare("UPDATE reviews SET status = 'approved', updated_at = NOW() WHERE id = ?");
                $stmt->execute([$review_id]);
                setFlashMessage('success', 'Đã duyệt đánh giá thành công');
            } elseif ($action === 'reject') {
                $stmt = $pdo->prepare("UPDATE reviews SET status = 'rejected', updated_at = NOW() WHERE id = ?");
                $stmt->execute([$review_id]);
                setFlashMessage('success', 'Đã từ chối đánh giá thành công');
            } elseif ($action === 'delete') {
                $stmt = $pdo->prepare("DELETE FROM reviews WHERE id = ?");
                $stmt->execute([$review_id]);
                setFlashMessage('success', 'Đã xóa đánh giá thành công');
                redirect('index.php');
            }
            
            // Làm mới dữ liệu đánh giá
            $stmt = $pdo->prepare("
                SELECT r.*, u.name as user_name, u.email as user_email, p.name as product_name, p.image as product_image
                FROM reviews r
                JOIN users u ON r.user_id = u.id
                JOIN products p ON r.product_id = p.id
                WHERE r.id = ?
            ");
            $stmt->execute([$review_id]);
            $review = $stmt->fetch();
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật đánh giá: ' . $e->getMessage());
        }
    }
}

// Tiêu đề trang
$pageTitle = 'Xem Đánh Giá';

// Include header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Chi Tiết Đánh Giá</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại Danh Sách
                    </a>
                </div>
            </div>
            
            <!-- Trạng thái đánh giá -->
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h5 class="card-title">Trạng Thái Đánh Giá</h5>
                                    <p class="mb-0">
                                        <span class="badge bg-<?php 
                                            echo $review['status'] === 'approved' ? 'success' : 
                                                ($review['status'] === 'rejected' ? 'danger' : 'warning'); 
                                        ?> fs-6">
                                            <?php echo $review['status'] === 'approved' ? 'Đã Duyệt' : 
                                                ($review['status'] === 'rejected' ? 'Đã Từ Chối' : 'Chờ Duyệt'); ?>
                                        </span>
                                    </p>
                                </div>
                                <div>
                                    <form action="" method="POST" class="d-inline">
                                        <?php if ($review['status'] !== 'approved'): ?>
                                        <input type="hidden" name="action" value="approve">
                                        <button type="submit" class="btn btn-success me-2">
                                            <i class="fas fa-check"></i> Duyệt
                                        </button>
                                        <?php endif; ?>
                                        
                                        <?php if ($review['status'] !== 'rejected'): ?>
                                        <input type="hidden" name="action" value="reject">
                                        <button type="submit" class="btn btn-warning me-2">
                                            <i class="fas fa-times"></i> Từ Chối
                                        </button>
                                        <?php endif; ?>
                                    </form>
                                    
                                    <form action="" method="POST" class="d-inline" onsubmit="return confirm('Bạn có chắc chắn muốn xóa đánh giá này?')">
                                        <input type="hidden" name="action" value="delete">
                                        <button type="submit" class="btn btn-danger">
                                            <i class="fas fa-trash"></i> Xóa
                                        </button>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <!-- Chi tiết đánh giá -->
                <div class="col-md-8 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Nội Dung Đánh Giá</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-4">
                                <h6>Đánh Giá:</h6>
                                <div class="fs-4">
                                    <?php for ($i = 1; $i <= 5; $i++): ?>
                                        <?php if ($i <= $review['rating']): ?>
                                            <i class="fas fa-star text-warning"></i>
                                        <?php else: ?>
                                            <i class="far fa-star text-warning"></i>
                                        <?php endif; ?>
                                    <?php endfor; ?>
                                    <span class="ms-2 fs-5"><?php echo $review['rating']; ?>/5</span>
                                </div>
                            </div>
                            
                            <div class="mb-4">
                                <h6>Bình Luận:</h6>
                                <div class="p-3 bg-light rounded">
                                    <?php echo nl2br(htmlspecialchars($review['comment'])); ?>
                                </div>
                            </div>
                            
                            <table class="table">
                                <tr>
                                    <th style="width: 150px;">ID Đánh Giá:</th>
                                    <td><?php echo $review['id']; ?></td>
                                </tr>
                                <tr>
                                    <th>Ngày Tạo:</th>
                                    <td><?php echo date('d/m/Y', strtotime($review['created_at'])); ?></td>
                                </tr>
                                <tr>
                                    <th>Cập Nhật Lần Cuối:</th>
                                    <td><?php echo date('d/m/Y', strtotime($review['updated_at'])); ?></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Thông tin bên lề -->
                <div class="col-md-4">
                    <!-- Thông tin sản phẩm -->
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Sản Phẩm</h5>
                        </div>
                        <div class="card-body">
                            <div class="text-center mb-3">
                                <img src="../../uploads/products/<?php echo !empty($review['product_image']) ? $review['product_image'] : 'default.jpg'; ?>" 
                                     alt="<?php echo htmlspecialchars($review['product_name']); ?>" 
                                     class="img-fluid rounded" style="max-height: 150px;">
                            </div>
                            <h5 class="text-center mb-3">
                                <a href="../products/view.php?id=<?php echo $review['product_id']; ?>">
                                    <?php echo htmlspecialchars($review['product_name']); ?>
                                </a>
                            </h5>
                            <div class="d-grid">
                                <a href="../products/view.php?id=<?php echo $review['product_id']; ?>" class="btn btn-primary">
                                    <i class="fas fa-eye"></i> Xem Sản Phẩm
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Thông tin người dùng -->
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Người Dùng</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Tên:</strong> 
                                <a href="../users/view.php?id=<?php echo $review['user_id']; ?>">
                                    <?php echo htmlspecialchars($review['user_name']); ?>
                                </a>
                            </p>
                            <p><strong>Email:</strong> <?php echo htmlspecialchars($review['user_email']); ?></p>
                            
                            <?php
                            // Lấy số lượng đánh giá của người dùng
                            try {
                                $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM reviews WHERE user_id = ?");
                                $stmt->execute([$review['user_id']]);
                                $userReviewCount = $stmt->fetch()['count'];
                                
                                // Lấy các đánh giá khác của người dùng
                                $stmt = $pdo->prepare("
                                    SELECT id, product_id, rating, status 
                                    FROM reviews 
                                    WHERE user_id = ? AND id != ? 
                                    ORDER BY created_at DESC 
                                    LIMIT 3
                                ");
                                $stmt->execute([$review['user_id'], $review_id]);
                                $otherReviews = $stmt->fetchAll();
                            } catch (PDOException $e) {
                                $userReviewCount = 0;
                                $otherReviews = [];
                            }
                            ?>
                            
                            <p><strong>Tổng Số Đánh Giá:</strong> 
                                <a href="../reviews/index.php?user_id=<?php echo $review['user_id']; ?>">
                                    <?php echo $userReviewCount; ?> đánh giá
                                </a>
                            </p>
                            
                            <?php if (!empty($otherReviews)): ?>
                                <h6 class="mt-3">Các Đánh Giá Khác của Người Dùng:</h6>
                                <ul class="list-group">
                                    <?php foreach ($otherReviews as $otherReview): ?>
                                        <li class="list-group-item d-flex justify-content-between align-items-center">
                                            <a href="view.php?id=<?php echo $otherReview['id']; ?>">
                                                Đánh Giá #<?php echo $otherReview['id']; ?>
                                            </a>
                                            <div>
                                                <span class="badge bg-<?php 
                                                    echo $otherReview['status'] === 'approved' ? 'success' : 
                                                        ($otherReview['status'] === 'rejected' ? 'danger' : 'warning'); 
                                                ?>">
                                                    <?php echo $otherReview['status'] === 'approved' ? 'Đã Duyệt' : 
                                                        ($otherReview['status'] === 'rejected' ? 'Đã Từ Chối' : 'Chờ Duyệt'); ?>
                                                </span>
                                                <span class="ms-2">
                                                    <?php echo $otherReview['rating']; ?> <i class="fas fa-star text-warning"></i>
                                                </span>
                                            </div>
                                        </li>
                                    <?php endforeach; ?>
                                </ul>
                            <?php endif; ?>
                            
                            <div class="d-grid mt-3">
                                <a href="../users/view.php?id=<?php echo $review['user_id']; ?>" class="btn btn-primary">
                                    <i class="fas fa-user"></i> Xem Hồ Sơ Người Dùng
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>