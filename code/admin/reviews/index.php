<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Xử lý cập nhật trạng thái đánh giá
if (isset($_GET['action']) && isset($_GET['id'])) {
    $review_id = (int)$_GET['id'];
    $action = $_GET['action'];
    
    if (in_array($action, ['approve', 'reject', 'delete'])) {
        try {
            // Kiểm tra đánh giá tồn tại
            $stmt = $pdo->prepare("SELECT id FROM reviews WHERE id = ?");
            $stmt->execute([$review_id]);
            
            if ($stmt->rowCount() === 0) {
                setFlashMessage('error', 'Không tìm thấy đánh giá');
                redirect('index.php');
            }
            
            if ($action === 'approve') {
                $stmt = $pdo->prepare("UPDATE reviews SET status = 'approved' WHERE id = ?");
                $stmt->execute([$review_id]);
                setFlashMessage('success', 'Đã duyệt đánh giá thành công');
            } elseif ($action === 'reject') {
                $stmt = $pdo->prepare("UPDATE reviews SET status = 'rejected' WHERE id = ?");
                $stmt->execute([$review_id]);
                setFlashMessage('success', 'Đã từ chối đánh giá thành công');
            } elseif ($action === 'delete') {
                $stmt = $pdo->prepare("DELETE FROM reviews WHERE id = ?");
                $stmt->execute([$review_id]);
                setFlashMessage('success', 'Đã xóa đánh giá thành công');
            }
            
            redirect('index.php');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật đánh giá: ' . $e->getMessage());
            redirect('index.php');
        }
    }
}

// Phân trang
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$perPage = 10;
$offset = ($page - 1) * $perPage;

// Bộ lọc
$status = isset($_GET['status']) ? clean($_GET['status']) : '';
$product_id = isset($_GET['product_id']) ? (int)$_GET['product_id'] : null;
$user_id = isset($_GET['user_id']) ? (int)$_GET['user_id'] : null;
$search = isset($_GET['search']) ? clean($_GET['search']) : '';

// Xây dựng điều kiện truy vấn
$conditions = [];
$params = [];

if (!empty($status)) {
    $conditions[] = "r.status = ?";
    $params[] = $status;
}

if (!empty($product_id)) {
    $conditions[] = "r.product_id = ?";
    $params[] = $product_id;
}

if (!empty($user_id)) {
    $conditions[] = "r.user_id = ?";
    $params[] = $user_id;
}

if (!empty($search)) {
    $conditions[] = "(u.name LIKE ? OR p.name LIKE ? OR r.comment LIKE ?)";
    $params[] = "%$search%";
    $params[] = "%$search%";
    $params[] = "%$search%";
}

$whereClause = !empty($conditions) ? "WHERE " . implode(" AND ", $conditions) : "";

// Lấy tổng số đánh giá
try {
    $query = "SELECT COUNT(*) as total 
              FROM reviews r 
              JOIN users u ON r.user_id = u.id 
              JOIN products p ON r.product_id = p.id 
              $whereClause";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $totalReviews = $stmt->fetch()['total'];
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy đánh giá: ' . $e->getMessage());
    $totalReviews = 0;
}

// Lấy danh sách đánh giá có phân trang
try {
    $query = "SELECT r.*, u.name as user_name, p.name as product_name 
              FROM reviews r 
              JOIN users u ON r.user_id = u.id 
              JOIN products p ON r.product_id = p.id 
              $whereClause 
              ORDER BY r.created_at DESC 
              LIMIT $perPage OFFSET $offset";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $reviews = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy đánh giá: ' . $e->getMessage());
    $reviews = [];
}

// Tiêu đề trang
$pageTitle = 'Đánh giá';

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
                <h1 class="h2">Đánh giá</h1>
            </div>
            
            <!-- Bộ lọc -->
            <div class="row mb-3">
                <div class="col-md-8">
                    <form action="" method="GET" class="d-flex">
                        <input type="text" name="search" class="form-control me-2" placeholder="Tìm kiếm đánh giá..." value="<?php echo htmlspecialchars($search); ?>">
                        <select name="status" class="form-select me-2" style="width: 150px;">
                            <option value="">Tất cả trạng thái</option>
                            <option value="pending" <?php echo $status === 'pending' ? 'selected' : ''; ?>>Chờ duyệt</option>
                            <option value="approved" <?php echo $status === 'approved' ? 'selected' : ''; ?>>Đã duyệt</option>
                            <option value="rejected" <?php echo $status === 'rejected' ? 'selected' : ''; ?>>Đã từ chối</option>
                        </select>
                        <button type="submit" class="btn btn-outline-primary">Lọc</button>
                        <?php if (!empty($search) || !empty($status) || !empty($product_id) || !empty($user_id)): ?>
                            <a href="index.php" class="btn btn-outline-secondary ms-2">Xóa bộ lọc</a>
                        <?php endif; ?>
                    </form>
                </div>
            </div>
            
            <!-- Bảng đánh giá -->
            <div class="table-responsive">
                <table class="table table-striped table-sm">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Sản phẩm</th>
                            <th>Người dùng</th>
                            <th>Đánh giá</th>
                            <th>Bình luận</th>
                            <th>Trạng thái</th>
                            <th>Ngày</th>
                            <th>Thao tác</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($reviews as $review): ?>
                        <tr>
                            <td><?php echo $review['id']; ?></td>
                            <td>
                                <a href="../products/view.php?id=<?php echo $review['product_id']; ?>">
                                    <?php echo htmlspecialchars($review['product_name']); ?>
                                </a>
                            </td>
                            <td>
                                <a href="../users/view.php?id=<?php echo $review['user_id']; ?>">
                                    <?php echo htmlspecialchars($review['user_name']); ?>
                                </a>
                            </td>
                            <td>
                                <?php for ($i = 1; $i <= 5; $i++): ?>
                                    <?php if ($i <= $review['rating']): ?>
                                        <i class="fas fa-star text-warning"></i>
                                    <?php else: ?>
                                        <i class="far fa-star text-warning"></i>
                                    <?php endif; ?>
                                <?php endfor; ?>
                            </td>
                            <td>
                                <?php 
                                $comment = htmlspecialchars($review['comment']);
                                echo strlen($comment) > 50 ? substr($comment, 0, 50) . '...' : $comment;
                                ?>
                            </td>
                            <td>
                                <span class="badge bg-<?php 
                                    echo $review['status'] === 'approved' ? 'success' : 
                                        ($review['status'] === 'rejected' ? 'danger' : 'warning'); 
                                ?>">
                                    <?php 
                                    echo $review['status'] === 'approved' ? 'Đã duyệt' : 
                                        ($review['status'] === 'rejected' ? 'Đã từ chối' : 'Chờ duyệt'); 
                                    ?>
                                </span>
                            </td>
                            <td><?php echo date('d/m/Y', strtotime($review['created_at'])); ?></td>
                            <td>
                                <div class="btn-group">
                                    <a href="view.php?id=<?php echo $review['id']; ?>" class="btn btn-sm btn-info" title="Xem">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <?php if ($review['status'] === 'pending'): ?>
                                    <a href="index.php?action=approve&id=<?php echo $review['id']; ?>" class="btn btn-sm btn-success" title="Duyệt">
                                        <i class="fas fa-check"></i>
                                    </a>
                                    <a href="index.php?action=reject&id=<?php echo $review['id']; ?>" class="btn btn-sm btn-warning" title="Từ chối">
                                        <i class="fas fa-times"></i>
                                    </a>
                                    <?php endif; ?>
                                    <a href="index.php?action=delete&id=<?php echo $review['id']; ?>" class="btn btn-sm btn-danger" onclick="return confirm('Bạn có chắc chắn muốn xóa đánh giá này?')" title="Xóa">
                                        <i class="fas fa-trash"></i>
                                    </a>
                                </div>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                        <?php if (empty($reviews)): ?>
                        <tr>
                            <td colspan="8" class="text-center">Không tìm thấy đánh giá nào</td>
                        </tr>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>
            
            <!-- Phân trang -->
            <div class="d-flex justify-content-center">
                <?php
                $totalPages = ceil($totalReviews / $perPage);
                $url = 'index.php';
                $queryParams = [];
                
                if (!empty($status)) {
                    $queryParams[] = "status=" . urlencode($status);
                }
                
                if (!empty($product_id)) {
                    $queryParams[] = "product_id=" . $product_id;
                }
                
                if (!empty($user_id)) {
                    $queryParams[] = "user_id=" . $user_id;
                }
                
                if (!empty($search)) {
                    $queryParams[] = "search=" . urlencode($search);
                }
                
                if (!empty($queryParams)) {
                    $url .= '?' . implode('&', $queryParams) . '&';
                } else {
                    $url .= '?';
                }
                
                echo paginate($totalReviews, $perPage, $page, $url);
                ?>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>