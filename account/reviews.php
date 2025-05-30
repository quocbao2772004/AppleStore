<?php
require_once '../includes/functions.php';
require_once '../includes/auth.php';
require_once '../config/database.php';

// Kiểm tra đăng nhập
if (!isLoggedIn()) {
    setFlashMessage('error', 'Vui lòng đăng nhập để xem đánh giá của bạn');
    redirect('../login.php');
}

// Lấy thông tin người dùng
$user_id = $_SESSION['user_id'];

// Xử lý các hành động đánh giá
if (isset($_GET['action'])) {
    $action = $_GET['action'];
    
    // Xóa đánh giá
    if ($action === 'delete' && isset($_GET['id'])) {
        $review_id = (int)$_GET['id'];
        
        try {
            $stmt = $pdo->prepare("DELETE FROM reviews WHERE id = ? AND user_id = ?");
            $stmt->execute([$review_id, $user_id]);
            
            setFlashMessage('success', 'Xóa đánh giá thành công');
            redirect('reviews.php');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi xóa đánh giá: ' . $e->getMessage());
            redirect('reviews.php');
        }
    }
}

// Xử lý gửi form chỉnh sửa đánh giá
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['edit_review'])) {
    $review_id = (int)$_POST['review_id'];
    $rating = (int)$_POST['rating'];
    $comment = clean($_POST['comment']);
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if ($rating < 1 || $rating > 5) {
        $errors[] = 'Đánh giá phải từ 1 đến 5 sao';
    }
    
    if (empty($comment)) {
        $errors[] = 'Vui lòng nhập nội dung đánh giá';
    }
    
    // Nếu không có lỗi, cập nhật đánh giá
    if (empty($errors)) {
        try {
            $stmt = $pdo->prepare("
                UPDATE reviews 
                SET rating = ?, comment = ?, status = 'pending', updated_at = NOW()
                WHERE id = ? AND user_id = ?
            ");
            $stmt->execute([$rating, $comment, $review_id, $user_id]);
            
            setFlashMessage('success', 'Cập nhật đánh giá thành công. Đánh giá sẽ hiển thị sau khi được duyệt.');
            redirect('reviews.php');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật đánh giá: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Lấy đánh giá để chỉnh sửa nếu có ID
$edit_review = null;
if (isset($_GET['edit']) && !empty($_GET['edit'])) {
    $edit_id = (int)$_GET['edit'];
    
    try {
        $stmt = $pdo->prepare("
            SELECT r.*, p.name as product_name
            FROM reviews r
            JOIN products p ON r.product_id = p.id
            WHERE r.id = ? AND r.user_id = ?
        ");
        $stmt->execute([$edit_id, $user_id]);
        $edit_review = $stmt->fetch();
        
        if (!$edit_review) {
            setFlashMessage('error', 'Không tìm thấy đánh giá');
            redirect('reviews.php');
        }
    } catch (PDOException $e) {
        setFlashMessage('error', 'Lỗi khi lấy đánh giá: ' . $e->getMessage());
        redirect('reviews.php');
    }
}

// Lấy tất cả đánh giá của người dùng
try {
    $stmt = $pdo->prepare("
        SELECT r.*, p.name as product_name, p.image as product_image
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
    ");
    $stmt->execute([$user_id]);
    $reviews = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh sách đánh giá: ' . $e->getMessage());
    $reviews = [];
}

// Tiêu đề trang
$pageTitle = 'Đánh Giá Của Tôi';

// Include header
include '../includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <!-- Thanh bên -->
        <div class="col-lg-3">
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Tài Khoản Của Tôi</h5>
                </div>
                <div class="list-group list-group-flush">
                    <a href="index.php" class="list-group-item list-group-item-action">
                        <i class="fas fa-tachometer-alt me-2"></i> Bảng Điều Khiển
                    </a>
                    <a href="profile.php" class="list-group-item list-group-item-action">
                        <i class="fas fa-user me-2"></i> Hồ Sơ Của Tôi
                    </a>
                    
                    <a href="reviews.php" class="list-group-item list-group-item-action active">
                        <i class="fas fa-star me-2"></i> Đánh Giá Của Tôi
                    </a>
                    <a href="../logout.php" class="list-group-item list-group-item-action text-danger">
                        <i class="fas fa-sign-out-alt me-2"></i> Đăng Xuất
                    </a>
                </div>
            </div>
        </div>
        
        <!-- Nội dung chính -->
        <div class="col-lg-9">
            <?php if ($edit_review): ?>
            <!-- Form chỉnh sửa đánh giá -->
            <div class="card mb-4">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Chỉnh Sửa Đánh Giá cho <?php echo htmlspecialchars($edit_review['product_name']); ?></h5>
                </div>
                <div class="card-body">
                    <form action="" method="POST">
                        <input type="hidden" name="review_id" value="<?php echo $edit_review['id']; ?>">
                        
                        <div class="mb-3">
                            <label class="form-label">Đánh Giá <span class="text-danger">*</span></label>
                            <div class="star-rating">
                                <?php for ($i = 1; $i <= 5; $i++): ?>
                                    <div class="form-check form-check-inline">
                                        <input class="form-check-input" type="radio" name="rating" id="rating<?php echo $i; ?>" value="<?php echo $i; ?>" <?php echo $edit_review['rating'] == $i ? 'checked' : ''; ?> required>
                                        <label class="form-check-label" for="rating<?php echo $i; ?>">
                                            <i class="fas fa-star text-warning"></i>
                                            <?php if ($i === 1): ?>Kém<?php endif; ?>
                                            <?php if ($i === 3): ?>Bình thường<?php endif; ?>
                                            <?php if ($i === 5): ?>Xuất sắc<?php endif; ?>
                                        </label>
                                    </div>
                                <?php endfor; ?>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="comment" class="form-label">Nội Dung Đánh Giá <span class="text-danger">*</span></label>
                            <textarea class="form-control" id="comment" name="comment" rows="4" required><?php echo htmlspecialchars($edit_review['comment']); ?></textarea>
                        </div>
                        
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i> Đánh giá của bạn sẽ được hiển thị sau khi được quản trị viên phê duyệt.
                        </div>
                        
                        <div class="d-flex">
                            <button type="submit" name="edit_review" class="btn btn-primary">
                                <i class="fas fa-save me-2"></i> Cập Nhật Đánh Giá
                            </button>
                            <a href="reviews.php" class="btn btn-outline-secondary ms-2">
                                <i class="fas fa-times me-2"></i> Hủy
                            </a>
                        </div>
                    </form>
                </div>
            </div>
            <?php endif; ?>
            
            <!-- Danh sách đánh giá -->
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Đánh Giá Của Tôi</h5>
                </div>
                <div class="card-body">
                    <?php if (!empty($reviews)): ?>
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead class="table-light">
                                    <tr>
                                        <th>Sản Phẩm</th>
                                        <th>Đánh Giá</th>
                                        <th>Nội Dung</th>
                                        <th>Ngày</th>
                                        <th>Trạng Thái</th>
                                        <th>Thao Tác</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($reviews as $review): ?>
                                        <tr>
                                            <td>
                                                <div class="d-flex align-items-center">
                                                    <img src="../uploads/products/<?php echo !empty($review['product_image']) ? $review['product_image'] : 'default.jpg'; ?>" 
                                                         alt="<?php echo htmlspecialchars($review['product_name']); ?>" 
                                                         class="img-thumbnail me-2" style="width: 50px; height: 50px; object-fit: cover;">
                                                    <a href="../product.php?id=<?php echo $review['product_id']; ?>" class="text-decoration-none">
                                                        <?php echo htmlspecialchars($review['product_name']); ?>
                                                    </a>
                                                </div>
                                            </td>
                                            <td>
                                                <div>
                                                    <?php for ($i = 1; $i <= 5; $i++): ?>
                                                        <?php if ($i <= $review['rating']): ?>
                                                            <i class="fas fa-star text-warning"></i>
                                                        <?php else: ?>
                                                            <i class="far fa-star text-warning"></i>
                                                        <?php endif; ?>
                                                    <?php endfor; ?>
                                                </div>
                                            </td>
                                            <td>
                                                <?php 
                                                $comment = htmlspecialchars($review['comment']);
                                                echo strlen($comment) > 100 ? substr($comment, 0, 100) . '...' : $comment;
                                                ?>
                                            </td>
                                            <td><?php echo date('d/m/Y', strtotime($review['created_at'])); ?></td>
                                            <td>
                                                <span class="badge bg-<?php 
                                                    echo $review['status'] === 'approved' ? 'success' : 
                                                        ($review['status'] === 'rejected' ? 'danger' : 'warning'); 
                                                ?>">
                                                    <?php 
                                                    $status_text = [
                                                        'pending' => 'Chờ duyệt',
                                                        'approved' => 'Đã duyệt',
                                                        'rejected' => 'Từ chối'
                                                    ];
                                                    echo $status_text[$review['status']] ?? ucfirst($review['status']); 
                                                    ?>
                                                </span>
                                            </td>
                                            <td>
                                                <a href="reviews.php?edit=<?php echo $review['id']; ?>" class="btn btn-sm btn-primary">
                                                    <i class="fas fa-edit"></i>
                                                </a>
                                                <a href="reviews.php?action=delete&id=<?php echo $review['id']; ?>" 
                                                   class="btn btn-sm btn-danger" 
                                                   onclick="return confirm('Bạn có chắc chắn muốn xóa đánh giá này?')">
                                                    <i class="fas fa-trash"></i>
                                                </a>
                                            </td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    <?php else: ?>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i> Bạn chưa có đánh giá nào.
                        </div>
                        <div class="text-center mt-3">
                            <a href="../products.php" class="btn btn-primary">
                                <i class="fas fa-shopping-bag me-2"></i> Xem Sản Phẩm Để Đánh Giá
                            </a>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
            
            <!-- Hướng dẫn đánh giá -->
            <div class="card mt-4">
                <div class="card-header bg-light">
                    <h5 class="mb-0">Hướng Dẫn Đánh Giá</h5>
                </div>
                <div class="card-body">
                    <ul class="list-group list-group-flush">
                        <li class="list-group-item">
                            <i class="fas fa-check-circle text-success me-2"></i> Hãy trung thực và cụ thể về trải nghiệm của bạn với sản phẩm
                        </li>
                        <li class="list-group-item">
                            <i class="fas fa-check-circle text-success me-2"></i> Nêu rõ những điểm bạn thích hoặc không thích về sản phẩm
                        </li>
                        <li class="list-group-item">
                            <i class="fas fa-check-circle text-success me-2"></i> Đánh giá của bạn sẽ được hiển thị sau khi được đội ngũ của chúng tôi phê duyệt
                        </li>
                        <li class="list-group-item">
                            <i class="fas fa-times-circle text-danger me-2"></i> Tránh sử dụng ngôn ngữ không phù hợp hoặc tấn công cá nhân
                        </li>
                        <li class="list-group-item">
                            <i class="fas fa-times-circle text-danger me-2"></i> Không đưa thông tin cá nhân hoặc thông tin liên hệ vào đánh giá
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<?php include '../includes/footer.php'; ?>