<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Xử lý xóa danh mục
if (isset($_GET['action']) && $_GET['action'] === 'delete' && isset($_GET['id'])) {
    $category_id = (int)$_GET['id'];
    
    try {
        // Kiểm tra danh mục tồn tại
        $stmt = $pdo->prepare("SELECT id FROM categories WHERE id = ?");
        $stmt->execute([$category_id]);
        
        if ($stmt->rowCount() === 0) {
            setFlashMessage('error', 'Không tìm thấy danh mục');
            redirect('index.php');
        }
        
        // Kiểm tra danh mục có sản phẩm không
        $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM products WHERE category_id = ?");
        $stmt->execute([$category_id]);
        $productCount = $stmt->fetch()['count'];
        
        if ($productCount > 0) {
            setFlashMessage('error', 'Không thể xóa danh mục. Có ' . $productCount . ' sản phẩm thuộc danh mục này.');
            redirect('index.php');
        }
        
        // Xóa danh mục
        $stmt = $pdo->prepare("DELETE FROM categories WHERE id = ?");
        $stmt->execute([$category_id]);
        
        setFlashMessage('success', 'Đã xóa danh mục thành công');
        redirect('index.php');
    } catch (PDOException $e) {
        setFlashMessage('error', 'Lỗi khi xóa danh mục: ' . $e->getMessage());
        redirect('index.php');
    }
}

// Phân trang
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$perPage = 10;
$offset = ($page - 1) * $perPage;

// Chức năng tìm kiếm
$search = isset($_GET['search']) ? clean($_GET['search']) : '';
$searchCondition = '';
$searchParams = [];

if (!empty($search)) {
    $searchCondition = "WHERE name LIKE ?";
    $searchParams = ["%$search%"];
}

// Lấy tổng số danh mục
try {
    if (!empty($searchCondition)) {
        $stmt = $pdo->prepare("SELECT COUNT(*) as total FROM categories $searchCondition");
        $stmt->execute($searchParams);
    } else {
        $stmt = $pdo->query("SELECT COUNT(*) as total FROM categories");
    }
    $totalCategories = $stmt->fetch()['total'];
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh mục: ' . $e->getMessage());
    $totalCategories = 0;
}

// Lấy danh sách danh mục có phân trang
try {
    if (!empty($searchCondition)) {
        $stmt = $pdo->prepare("SELECT c.*, 
                              (SELECT COUNT(*) FROM products WHERE category_id = c.id) as product_count 
                              FROM categories c 
                              $searchCondition 
                              ORDER BY c.name ASC 
                              LIMIT $perPage OFFSET $offset");
        $stmt->execute($searchParams);
    } else {
        $stmt = $pdo->query("SELECT c.*, 
                            (SELECT COUNT(*) FROM products WHERE category_id = c.id) as product_count 
                            FROM categories c 
                            ORDER BY c.name ASC 
                            LIMIT $perPage OFFSET $offset");
    }
    $categories = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh mục: ' . $e->getMessage());
    $categories = [];
}

// Tiêu đề trang
$pageTitle = 'Danh Mục';

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
                <h1 class="h2">Danh Mục</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="create.php" class="btn btn-sm btn-primary">
                        <i class="fas fa-plus"></i> Thêm Danh Mục Mới
                    </a>
                </div>
            </div>
            
            <!-- Form tìm kiếm -->
            <div class="row mb-3">
                <div class="col-md-6">
                    <form action="" method="GET" class="d-flex">
                        <input type="text" name="search" class="form-control me-2" placeholder="Tìm kiếm danh mục..." value="<?php echo htmlspecialchars($search); ?>">
                        <button type="submit" class="btn btn-outline-primary">Search</button>
                        <?php if (!empty($search)): ?>
                            <a href="index.php" class="btn btn-outline-secondary ms-2">Xóa</a>
                        <?php endif; ?>
                    </form>
                </div>
            </div>
            
            <!-- Bảng danh mục -->
            <div class="table-responsive">
                <table class="table table-striped table-sm">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Tên</th>
                            <th>Đường Dẫn</th>
                            <th>Sản Phẩm</th>
                            <th>Ngày Tạo</th>
                            <th>Thao Tác</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($categories as $category): ?>
                        <tr>
                            <td><?php echo $category['id']; ?></td>
                            <td><?php echo htmlspecialchars($category['name']); ?></td>
                            <td><?php echo htmlspecialchars($category['slug']); ?></td>
                            <td>
                                <?php if ($category['product_count'] > 0): ?>
                                    <a href="../products/index.php?category=<?php echo $category['id']; ?>" class="badge bg-primary">
                                        <?php echo $category['product_count']; ?> sản phẩm
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 sản phẩm</span>
                                <?php endif; ?>
                            </td>
                            <td><?php echo date('d/m/Y', strtotime($category['created_at'])); ?></td>
                            <td>
                                <a href="edit.php?id=<?php echo $category['id']; ?>" class="btn btn-sm btn-primary">
                                    <i class="fas fa-edit"></i>
                                </a>
                                <?php if ($category['product_count'] == 0): ?>
                                <a href="index.php?action=delete&id=<?php echo $category['id']; ?>" class="btn btn-sm btn-danger" onclick="return confirm('Bạn có chắc chắn muốn xóa danh mục này?')">
                                    <i class="fas fa-trash"></i>
                                </a>
                                <?php else: ?>
                                <button class="btn btn-sm btn-danger" disabled title="Không thể xóa danh mục có sản phẩm">
                                    <i class="fas fa-trash"></i>
                                </button>
                                <?php endif; ?>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                        <?php if (empty($categories)): ?>
                        <tr>
                            <td colspan="6" class="text-center">Không tìm thấy danh mục nào</td>
                        </tr>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>
            
            <!-- Phân trang -->
            <div class="d-flex justify-content-center">
                <?php
                $totalPages = ceil($totalCategories / $perPage);
                $url = 'index.php';
                if (!empty($search)) {
                    $url .= '?search=' . urlencode($search) . '&';
                } else {
                    $url .= '?';
                }
                echo paginate($totalCategories, $perPage, $page, $url);
                ?>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>