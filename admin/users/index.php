<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Xử lý xóa người dùng
if (isset($_GET['action']) && $_GET['action'] === 'delete' && isset($_GET['id'])) {
    $user_id = (int)$_GET['id'];
    
    // Ngăn chặn xóa tài khoản của chính mình
    if ($user_id === (int)$_SESSION['user_id']) {
        setFlashMessage('error', 'Bạn không thể xóa tài khoản của chính mình');
        redirect('index.php');
    }
    
    try {
        // Kiểm tra người dùng tồn tại
        $stmt = $pdo->prepare("SELECT id, role FROM users WHERE id = ?");
        $stmt->execute([$user_id]);
        $user = $stmt->fetch();
        
        if (!$user) {
            setFlashMessage('error', 'Không tìm thấy người dùng');
            redirect('index.php');
        }
        
        // Kiểm tra người dùng có đơn hàng
        $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM orders WHERE user_id = ?");
        $stmt->execute([$user_id]);
        $orderCount = $stmt->fetch()['count'];
        
        if ($orderCount > 0) {
            setFlashMessage('error', 'Không thể xóa người dùng. Họ có ' . $orderCount . ' đơn hàng liên kết với tài khoản.');
            redirect('index.php');
        }
        
        // Xóa đánh giá của người dùng
        $stmt = $pdo->prepare("DELETE FROM reviews WHERE user_id = ?");
        $stmt->execute([$user_id]);
        
        // Xóa người dùng
        $stmt = $pdo->prepare("DELETE FROM users WHERE id = ?");
        $stmt->execute([$user_id]);
        
        setFlashMessage('success', 'Xóa người dùng thành công');
        redirect('index.php');
    } catch (PDOException $e) {
        setFlashMessage('error', 'Lỗi khi xóa người dùng: ' . $e->getMessage());
        redirect('index.php');
    }
}

// Phân trang
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$perPage = 10;
$offset = ($page - 1) * $perPage;

// Bộ lọc
$role = isset($_GET['role']) ? clean($_GET['role']) : '';
$search = isset($_GET['search']) ? clean($_GET['search']) : '';

// Xây dựng điều kiện truy vấn
$conditions = [];
$params = [];

if (!empty($role)) {
    $conditions[] = "role = ?";
    $params[] = $role;
}

if (!empty($search)) {
    $conditions[] = "(name LIKE ? OR email LIKE ? OR phone LIKE ?)";
    $params[] = "%$search%";
    $params[] = "%$search%";
    $params[] = "%$search%";
}

$whereClause = !empty($conditions) ? "WHERE " . implode(" AND ", $conditions) : "";

// Lấy tổng số người dùng
try {
    $query = "SELECT COUNT(*) as total FROM users $whereClause";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $totalUsers = $stmt->fetch()['total'];
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh sách người dùng: ' . $e->getMessage());
    $totalUsers = 0;
}

// Lấy danh sách người dùng có phân trang
try {
    $query = "SELECT u.*, 
              (SELECT COUNT(*) FROM orders WHERE user_id = u.id) as order_count,
              (SELECT COUNT(*) FROM reviews WHERE user_id = u.id) as review_count
              FROM users u 
              $whereClause 
              ORDER BY u.id DESC 
              LIMIT $perPage OFFSET $offset";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $users = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh sách người dùng: ' . $e->getMessage());
    $users = [];
}

// Tiêu đề trang
$pageTitle = 'Quản Lý Người Dùng';

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
                <h1 class="h2">Quản Lý Người Dùng</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="create.php" class="btn btn-sm btn-primary">
                        <i class="fas fa-plus"></i> Thêm Người Dùng
                    </a>
                </div>
            </div>
            
            <!-- Bộ lọc -->
            <div class="row mb-3">
                <div class="col-md-8">
                    <form action="" method="GET" class="d-flex">
                        <input type="text" name="search" class="form-control me-2" placeholder="Tìm theo tên, email hoặc số điện thoại..." value="<?php echo htmlspecialchars($search); ?>">
                        <select name="role" class="form-select me-2" style="width: 150px;">
                            <option value="">Tất Cả Vai Trò</option>
                            <option value="admin" <?php echo $role === 'admin' ? 'selected' : ''; ?>>Quản Trị</option>
                            <option value="customer" <?php echo $role === 'customer' ? 'selected' : ''; ?>>Khách Hàng</option>
                        </select>
                        <button type="submit" class="btn btn-outline-primary">Lọc</button>
                        <?php if (!empty($search) || !empty($role)): ?>
                            <a href="index.php" class="btn btn-outline-secondary ms-2">Xóa Lọc</a>
                        <?php endif; ?>
                    </form>
                </div>
            </div>
            
            <!-- Bảng người dùng -->
            <div class="table-responsive">
                <table class="table table-striped table-sm">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Tên</th>
                            <th>Email</th>
                            <th>Điện Thoại</th>
                            <th>Vai Trò</th>
                            <th>Đơn Hàng</th>
                            <th>Đánh Giá</th>
                            <th>Ngày Đăng Ký</th>
                            <th>Thao Tác</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($users as $user): ?>
                        <tr>
                            <td><?php echo $user['id']; ?></td>
                            <td><?php echo htmlspecialchars($user['name']); ?></td>
                            <td><?php echo htmlspecialchars($user['email']); ?></td>
                            <td><?php echo htmlspecialchars($user['phone'] ?? 'N/A'); ?></td>
                            <td>
                                <span class="badge bg-<?php echo $user['role'] === 'admin' ? 'danger' : 'primary'; ?>">
                                    <?php echo $user['role'] === 'admin' ? 'Quản Trị' : 'Khách Hàng'; ?>
                                </span>
                            </td>
                            <td>
                                <?php if ($user['order_count'] > 0): ?>
                                    <a href="../orders/index.php?user_id=<?php echo $user['id']; ?>" class="badge bg-info">
                                        <?php echo $user['order_count']; ?> đơn hàng
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 đơn hàng</span>
                                <?php endif; ?>
                            </td>
                            <td>
                                <?php if ($user['review_count'] > 0): ?>
                                    <a href="../reviews/index.php?user_id=<?php echo $user['id']; ?>" class="badge bg-info">
                                        <?php echo $user['review_count']; ?> đánh giá
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 đánh giá</span>
                                <?php endif; ?>
                            </td>
                            <td><?php echo date('d/m/Y', strtotime($user['created_at'])); ?></td>
                            <td>
                                <a href="view.php?id=<?php echo $user['id']; ?>" class="btn btn-sm btn-info" title="Xem">
                                    <i class="fas fa-eye"></i>
                                </a>
                                <a href="edit.php?id=<?php echo $user['id']; ?>" class="btn btn-sm btn-primary" title="Sửa">
                                    <i class="fas fa-edit"></i>
                                </a>
                                <?php if ($user['id'] != $_SESSION['user_id'] && $user['order_count'] == 0): ?>
                                <a href="index.php?action=delete&id=<?php echo $user['id']; ?>" class="btn btn-sm btn-danger" onclick="return confirm('Bạn có chắc chắn muốn xóa người dùng này?')" title="Xóa">
                                    <i class="fas fa-trash"></i>
                                </a>
                                <?php else: ?>
                                <button class="btn btn-sm btn-danger" disabled title="<?php echo $user['id'] == $_SESSION['user_id'] ? 'Không thể xóa tài khoản của chính mình' : 'Không thể xóa người dùng có đơn hàng'; ?>">
                                    <i class="fas fa-trash"></i>
                                </button>
                                <?php endif; ?>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                        <?php if (empty($users)): ?>
                        <tr>
                            <td colspan="9" class="text-center">Không tìm thấy người dùng nào</td>
                        </tr>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>
            
            <!-- Phân trang -->
            <div class="d-flex justify-content-center">
                <?php
                $totalPages = ceil($totalUsers / $perPage);
                $url = 'index.php';
                $queryParams = [];
                
                if (!empty($role)) {
                    $queryParams[] = "role=" . urlencode($role);
                }
                
                if (!empty($search)) {
                    $queryParams[] = "search=" . urlencode($search);
                }
                
                if (!empty($queryParams)) {
                    $url .= '?' . implode('&', $queryParams) . '&';
                } else {
                    $url .= '?';
                }
                
                echo paginate($totalUsers, $perPage, $page, $url);
                ?>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>