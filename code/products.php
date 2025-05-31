<?php
require_once 'includes/functions.php';
require_once 'config/database.php';

// Phân trang
$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$perPage = 12;
$offset = ($page - 1) * $perPage;

// Bộ lọc
$category_id = isset($_GET['category']) ? (int)$_GET['category'] : null;
$search = isset($_GET['search']) ? clean($_GET['search']) : '';
$sort = isset($_GET['sort']) ? clean($_GET['sort']) : 'newest';

// Xây dựng điều kiện truy vấn
$conditions = [];
$params = [];

if (!empty($category_id)) {
    $conditions[] = "p.category_id = ?";
    $params[] = $category_id;
}

if (!empty($search)) {
    $conditions[] = "(p.name LIKE ? OR p.description LIKE ?)";
    $params[] = "%$search%";
    $params[] = "%$search%";
}

$whereClause = !empty($conditions) ? "WHERE " . implode(" AND ", $conditions) : "";

// Sắp xếp
$orderBy = "p.id DESC"; // Mặc định: mới nhất
if ($sort === 'price_low') {
    $orderBy = "p.price ASC";
} elseif ($sort === 'price_high') {
    $orderBy = "p.price DESC";
} elseif ($sort === 'name_asc') {
    $orderBy = "p.name ASC";
} elseif ($sort === 'name_desc') {
    $orderBy = "p.name DESC";
}

// Lấy tổng số sản phẩm
try {
    $query = "SELECT COUNT(*) as total FROM products p $whereClause";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $totalProducts = $stmt->fetch()['total'];
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy sản phẩm: ' . $e->getMessage());
    $totalProducts = 0;
}

// Lấy sản phẩm với phân trang
try {
    $query = "SELECT p.*, c.name as category_name 
              FROM products p 
              LEFT JOIN categories c ON p.category_id = c.id 
              $whereClause 
              ORDER BY $orderBy 
              LIMIT $perPage OFFSET $offset";
    
    if (!empty($params)) {
        $stmt = $pdo->prepare($query);
        $stmt->execute($params);
    } else {
        $stmt = $pdo->query($query);
    }
    
    $products = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy sản phẩm: ' . $e->getMessage());
    $products = [];
}

// Lấy tất cả danh mục để lọc
try {
    $stmt = $pdo->query("SELECT id, name, slug FROM categories ORDER BY name ASC");
    $categories = $stmt->fetchAll();
} catch (PDOException $e) {
    $categories = [];
}

// Lấy tên danh mục nếu bộ lọc danh mục được áp dụng
$categoryName = '';
if (!empty($category_id)) {
    try {
        $stmt = $pdo->prepare("SELECT name FROM categories WHERE id = ?");
        $stmt->execute([$category_id]);
        $categoryData = $stmt->fetch();
        if ($categoryData) {
            $categoryName = $categoryData['name'];
        }
    } catch (PDOException $e) {
        // Bỏ qua lỗi
    }
}

// Tiêu đề trang
$pageTitle = !empty($categoryName) ? $categoryName : 'Sản phẩm';
if (!empty($search)) {
    $pageTitle = 'Kết quả tìm kiếm cho "' . htmlspecialchars($search) . '"';
}

// Bao gồm header
include 'includes/header.php';
?>

<div class="container py-5">
    <!-- Đường dẫn -->
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="index.php">Trang chủ</a></li>
            <?php if (!empty($categoryName)): ?>
                <li class="breadcrumb-item"><a href="products.php">Sản phẩm</a></li>
                <li class="breadcrumb-item active" aria-current="page"><?php echo htmlspecialchars($categoryName); ?></li>
            <?php else: ?>
                <li class="breadcrumb-item active" aria-current="page">Sản phẩm</li>
            <?php endif; ?>
        </ol>
    </nav>
    
    <div class="row">
        <!-- Bộ lọc bên lề -->
        <div class="col-lg-3 mb-4">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">Lọc sản phẩm</h5>
                </div>
                <div class="card-body">
                    <!-- Form tìm kiếm -->
                    <form action="products.php" method="GET" class="mb-4">
                        <?php if (!empty($category_id)): ?>
                            <input type="hidden" name="category" value="<?php echo $category_id; ?>">
                        <?php endif; ?>
                        <div class="input-group">
                            <input type="text" name="search" class="form-control" placeholder="Tìm kiếm sản phẩm..." value="<?php echo htmlspecialchars($search); ?>">
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-search"></i>
                            </button>
                        </div>
                    </form>
                    
                    <!-- Danh mục -->
                    <h6 class="mb-3">Danh mục sản phẩm</h6>
                    <div class="list-group mb-4">
                        <a href="products.php<?php echo !empty($search) ? '?search=' . urlencode($search) : ''; ?>" class="list-group-item list-group-item-action <?php echo empty($category_id) ? 'active' : ''; ?>">
                            Tất cả danh mục
                        </a>
                        <?php foreach ($categories as $category): ?>
                            <a href="products.php?category=<?php echo $category['id']; ?><?php echo !empty($search) ? '&search=' . urlencode($search) : ''; ?>" class="list-group-item list-group-item-action <?php echo $category_id == $category['id'] ? 'active' : ''; ?>">
                                <?php echo ucfirst(strtolower(htmlspecialchars($category['name']))); ?>
                            </a>
                        <?php endforeach; ?>
                    </div>
                    
                    <!-- Sắp xếp theo -->
                    <h6 class="mb-3">Sắp xếp theo</h6>
                    <form action="products.php" method="GET">
                        <?php if (!empty($category_id)): ?>
                            <input type="hidden" name="category" value="<?php echo $category_id; ?>">
                        <?php endif; ?>
                        <?php if (!empty($search)): ?>
                            <input type="hidden" name="search" value="<?php echo htmlspecialchars($search); ?>">
                        <?php endif; ?>
                        <select name="sort" class="form-select" onchange="this.form.submit()">
                            <option value="newest" <?php echo $sort === 'newest' ? 'selected' : ''; ?>>Mới nhất</option>
                            <option value="price_low" <?php echo $sort === 'price_low' ? 'selected' : ''; ?>>Giá thấp đến cao</option>
                            <option value="price_high" <?php echo $sort === 'price_high' ? 'selected' : ''; ?>>Giá cao đến thấp</option>
                            <option value="name_asc" <?php echo $sort === 'name_asc' ? 'selected' : ''; ?>>Tên từ A đến Z</option>
                            <option value="name_desc" <?php echo $sort === 'name_desc' ? 'selected' : ''; ?>>Tên từ Z đến A</option>
                        </select>
                    </form>
                </div>
            </div>
        </div>
        
        <!-- Lưới sản phẩm -->
        <div class="col-lg-9">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h2 class="mb-0"><?php echo "Sản phẩm" ?></h2>
                <span class="text-muted"><?php echo $totalProducts; ?> sản phẩm được tìm thấy</span>
            </div>
            
            <?php if (empty($products)): ?>
                <div class="alert alert-info">
                    Không tìm thấy sản phẩm nào. Vui lòng điều chỉnh lại tìm kiếm hoặc bộ lọc.
                </div>
            <?php else: ?>
                <div class="row">
                    <?php foreach ($products as $product): ?>
                        <div class="col-md-4 col-sm-6 mb-4">
                            <div class="card h-100 shadow-sm">
                                <div style="height: 200px; overflow: hidden;">
                                    <?php if (!empty($product['image'])): ?>
                                        <img src="uploads/products/<?php echo $product['image']; ?>" class="card-img-top h-100 w-100" alt="<?php echo htmlspecialchars($product['name']); ?>" style="object-fit: contain;">
                                    <?php else: ?>
                                        <img src="assets/images/no-image.jpg" class="card-img-top h-100 w-100" alt="Không có hình" style="object-fit: contain;">
                                    <?php endif; ?>
                                </div>
                                <div class="card-body">
                                    <h5 class="card-title"><?php echo htmlspecialchars($product['name']); ?></h5>
                                    <p class="card-text text-muted"><?php echo ucfirst(strtolower(htmlspecialchars($product['category_name'] ?? 'Chưa phân loại'))); ?></p>
                                    <p class="card-text fw-bold"><?php echo number_format($product['price'], 0) . " VNĐ"; ?></p>
                                    <div class="d-flex justify-content-between align-items-center">
                                        <a href="product-detail.php?slug=<?php echo $product['slug']; ?>" class="btn btn-outline-primary">Xem chi tiết</a>
                                        <?php if ($product['stock'] > 0): ?>
                                            <form action="cart.php" method="POST" class="d-flex align-items-center">
                                                <input type="hidden" name="product_id" value="<?php echo $product['id']; ?>">
                                                <input type="hidden" name="action" value="add">
                                                <input type="number" name="quantity" class="form-control me-2" value="1" min="1" max="<?php echo $product['stock']; ?>" style="width: 80px;">
                                                <button type="submit" class="btn btn-primary">
                                                    <i class="fas fa-cart-plus"></i>
                                                </button>
                                            </form>
                                        <?php else: ?>
                                            <button class="btn btn-secondary" disabled>
                                                <i class="fas fa-times"></i> Hết hàng
                                            </button>
                                        <?php endif; ?>
                                    </div>
                                </div>
                            </div>
                        </div>
                    <?php endforeach; ?>
                </div>
                
                <!-- Phân trang -->
                <?php if ($totalProducts > $perPage): ?>
                    <div class="d-flex justify-content-center mt-4">
                        <nav aria-label="Điều hướng trang">
                            <ul class="pagination">
                                <?php
                                $totalPages = ceil($totalProducts / $perPage);
                                $queryParams = [];
                                
                                if (!empty($category_id)) {
                                    $queryParams[] = "category=$category_id";
                                }
                                
                                if (!empty($search)) {
                                    $queryParams[] = "search=" . urlencode($search);
                                }
                                
                                if (!empty($sort)) {
                                    $queryParams[] = "sort=$sort";
                                }
                                
                                $queryString = !empty($queryParams) ? implode("&", $queryParams) . "&" : "";
                                
                                // Nút Trước
                                if ($page > 1): ?>
                                    <li class="page-item">
                                        <a class="page-link" href="products.php?<?php echo $queryString; ?>page=<?php echo $page - 1; ?>" aria-label="Trước">
                                            <span aria-hidden="true">«</span>
                                        </a>
                                    </li>
                                <?php else: ?>
                                    <li class="page-item disabled">
                                        <a class="page-link" href="#" aria-label="Trước">
                                            <span aria-hidden="true">«</span>
                                        </a>
                                    </li>
                                <?php endif; ?>
                                
                                <?php
                                // Số trang
                                $startPage = max(1, $page - 2);
                                $endPage = min($totalPages, $page + 2);
                                
                                if ($startPage > 1): ?>
                                    <li class="page-item">
                                        <a class="page-link" href="products.php?<?php echo $queryString; ?>page=1">1</a>
                                    </li>
                                    <?php if ($startPage > 2): ?>
                                        <li class="page-item disabled">
                                            <a class="page-link" href="#">...</a>
                                        </li>
                                    <?php endif; ?>
                                <?php endif; ?>
                                
                                <?php for ($i = $startPage; $i <= $endPage; $i++): ?>
                                    <li class="page-item <?php echo $i == $page ? 'active' : ''; ?>">
                                        <a class="page-link" href="products.php?<?php echo $queryString; ?>page=<?php echo $i; ?>"><?php echo $i; ?></a>
                                    </li>
                                <?php endfor; ?>
                                
                                <?php if ($endPage < $totalPages): ?>
                                    <?php if ($endPage < $totalPages - 1): ?>
                                        <li class="page-item disabled">
                                            <a class="page-link" href="#">...</a>
                                        </li>
                                    <?php endif; ?>
                                    <li class="page-item">
                                        <a class="page-link" href="products.php?<?php echo $queryString; ?>page=<?php echo $totalPages; ?>"><?php echo $totalPages; ?></a>
                                    </li>
                                <?php endif; ?>
                                
                                <!-- Nút Tiếp -->
                                <?php if ($page < $totalPages): ?>
                                    <li class="page-item">
                                        <a class="page-link" href="products.php?<?php echo $queryString; ?>page=<?php echo $page + 1; ?>" aria-label="Tiếp">
                                            <span aria-hidden="true">»</span>
                                        </a>
                                    </li>
                                <?php else: ?>
                                    <li class="page-item disabled">
                                        <a class="page-link" href="#" aria-label="Tiếp">
                                            <span aria-hidden="true">»</span>
                                        </a>
                                    </li>
                                <?php endif; ?>
                            </ul>
                        </nav>
                    </div>
                <?php endif; ?>
            <?php endif; ?>
        </div>
    </div>
</div>

<?php include 'includes/footer.php'; ?>