<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
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
    $searchCondition = "WHERE p.name LIKE ? OR p.description LIKE ?";
    $searchParams = ["%$search%", "%$search%"];
}

// Lấy tổng số sản phẩm
try {
    if (!empty($searchCondition)) {
        $stmt = $pdo->prepare('SELECT COUNT(*) as total FROM products p ' . $searchCondition);
        $stmt->execute($searchParams);
    } else {
        $stmt = $pdo->query('SELECT COUNT(*) as total FROM products');
    }
    $totalProducts = $stmt->fetch()['total'];
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy sản phẩm: ' . $e->getMessage());
    $totalProducts = 0;
}

// Lấy danh sách sản phẩm có phân trang
try {
    if (!empty($searchCondition)) {
        $stmt = $pdo->prepare("SELECT p.*, c.name as category_name 
                              FROM products p 
                              LEFT JOIN categories c ON p.category_id = c.id 
                              $searchCondition 
                              ORDER BY p.id DESC 
                              LIMIT $perPage OFFSET $offset");
        $stmt->execute($searchParams);
    } else {
        $stmt = $pdo->query("SELECT p.*, c.name as category_name 
                            FROM products p 
                            LEFT JOIN categories c ON p.category_id = c.id 
                            ORDER BY p.id DESC 
                            LIMIT $perPage OFFSET $offset");
    }
    $products = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy sản phẩm: ' . $e->getMessage());
    $products = [];
}

// Tiêu đề trang
$pageTitle = 'Sản Phẩm';

// Thêm header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Thanh bên -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Sản Phẩm</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="create.php" class="btn btn-sm btn-primary">
                        <i class="fas fa-plus"></i> Thêm Sản Phẩm Mới
                    </a>
                </div>
            </div>
            
            <!-- Form tìm kiếm -->
            <div class="row mb-3">
                <div class="col-md-6">
                    <form action="" method="GET" class="d-flex">
                        <input type="text" name="search" class="form-control me-2" placeholder="Tìm kiếm sản phẩm..." value="<?php echo htmlspecialchars($search); ?>">
                        <button type="submit" class="btn btn-outline-primary">Search</button>
                        <?php if (!empty($search)): ?>
                            <a href="index.php" class="btn btn-outline-secondary ms-2">Xóa</a>
                        <?php endif; ?>
                    </form>
                </div>
            </div>
            
            <!-- Bảng sản phẩm -->
            <div class="table-responsive">
                <table class="table table-striped table-sm">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Hình Ảnh</th>
                            <th>Tên</th>
                            <th>Danh Mục</th>
                            <th>Giá</th>
                            <th>Tồn Kho</th>
                            <th>Ngày Tạo</th>
                            <th>Thao Tác</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($products as $product): ?>
                        <tr>
                            <td><?php echo $product['id']; ?></td>
                            <td>
                                <?php if (!empty($product['image'])): ?>
                                    <img src="../../uploads/products/<?php echo $product['image']; ?>" alt="<?php echo htmlspecialchars($product['name']); ?>" width="50" height="50" class="img-thumbnail">
                                <?php else: ?>
                                    <img src="../../assets/images/no-image.jpg" alt="Không có hình" width="50" height="50" class="img-thumbnail">
                                <?php endif; ?>
                            </td>
                            <td><?php echo htmlspecialchars($product['name']); ?></td>
                            <td><?php echo htmlspecialchars($product['category_name'] ?? 'Chưa phân loại'); ?></td>
                            <td><?php echo number_format($product['price'], 0, ',', '.') . " VNĐ"; ?></td>
                            <td>
                                <span class="badge bg-<?php echo $product['stock'] <= 5 ? 'danger' : ($product['stock'] <= 10 ? 'warning' : 'success'); ?>">
                                    <?php echo $product['stock']; ?>
                                </span>
                            </td>
                            <td><?php echo date('d/m/Y', strtotime($product['created_at'])); ?></td>
                            <td>
                                <a href="edit.php?id=<?php echo $product['id']; ?>" class="btn btn-sm btn-primary">
                                    <i class="fas fa-edit"></i>
                                </a>
                                <a href="view.php?id=<?php echo $product['id']; ?>" class="btn btn-sm btn-info">
                                    <i class="fas fa-eye"></i>
                                </a>
                                <a href="delete.php?id=<?php echo $product['id']; ?>" class="btn btn-sm btn-danger" onclick="return confirm('Bạn có chắc chắn muốn xóa sản phẩm này?')">
                                    <i class="fas fa-trash"></i>
                                </a>
                            </td>
                        </tr>
                        <?php endforeach; ?>
                        <?php if (empty($products)): ?>
                        <tr>
                            <td colspan="8" class="text-center">Không tìm thấy sản phẩm nào</td>
                        </tr>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>
            
            <!-- Phân trang -->
            <div class="d-flex justify-content-center">
                <?php
                $totalPages = ceil($totalProducts / $perPage);
                $url = 'index.php';
                if (!empty($search)) {
                    $url .= '?search=' . urlencode($search) . '&';
                } else {
                    $url .= '?';
                }
                echo paginate($totalProducts, $perPage, $page, $url);
                ?>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>