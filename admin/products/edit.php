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
    $stmt = $pdo->prepare("SELECT * FROM products WHERE id = ?");
    $stmt->execute([$product_id]);
    $product = $stmt->fetch();
    
    if (!$product) {
        setFlashMessage('error', 'Không tìm thấy sản phẩm');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy sản phẩm: ' . $e->getMessage());
    redirect('index.php');
}

// Get categories for dropdown
try {
    $stmt = $pdo->query("SELECT id, name FROM categories ORDER BY name ASC");
    $categories = $stmt->fetchAll();
} catch (PDOException $e) {
    $categories = [];
}

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name = clean($_POST['name']);
    $price = (float)$_POST['price'];
    $stock = (int)$_POST['stock'];
    $category_id = !empty($_POST['category_id']) ? (int)$_POST['category_id'] : null;
    $description = !empty($_POST['description']) ? clean($_POST['description']) : null;
    
    // Validate input
    $errors = [];
    
    if (empty($name)) {
        $errors[] = 'Tên sản phẩm là bắt buộc';
    }
    
    if ($price <= 0) {
        $errors[] = 'Giá phải lớn hơn 0';
    }
    
    if ($stock < 0) {
        $errors[] = 'Số lượng tồn kho không thể âm';
    }
    
    // Handle image upload
    $image = $product['image']; // Default to current image
    
    if (isset($_FILES['image']) && $_FILES['image']['size'] > 0) {
        $upload_dir = '../../uploads/products/';
        $allowed_types = ['image/jpeg', 'image/png', 'image/gif'];
        $max_size = 2 * 1024 * 1024; // 2MB
        
        // Check if upload directory exists, if not create it
        if (!file_exists($upload_dir)) {
            mkdir($upload_dir, 0755, true);
        }
        
        // Validate file
        if (!in_array($_FILES['image']['type'], $allowed_types)) {
            $errors[] = 'Định dạng file không hợp lệ. Chỉ chấp nhận JPG, PNG và GIF';
        } elseif ($_FILES['image']['size'] > $max_size) {
            $errors[] = 'Kích thước file vượt quá giới hạn. Tối đa 2MB';
        } else {
            // Generate unique filename
            $file_extension = pathinfo($_FILES['image']['name'], PATHINFO_EXTENSION);
            $new_filename = uniqid('product_') . '.' . $file_extension;
            $upload_path = $upload_dir . $new_filename;
            
            // Move uploaded file
            if (move_uploaded_file($_FILES['image']['tmp_name'], $upload_path)) {
                // Delete old image if it exists and is not the default
                if (!empty($product['image']) && $product['image'] !== 'default.jpg' && file_exists($upload_dir . $product['image'])) {
                    unlink($upload_dir . $product['image']);
                }
                
                $image = $new_filename;
            } else {
                $errors[] = 'Không thể tải lên hình ảnh';
            }
        }
    }
    
    // If no errors, update product
    if (empty($errors)) {
        try {
            $stmt = $pdo->prepare("
                UPDATE products 
                SET name = ?, price = ?, stock = ?, category_id = ?, description = ?, 
                    image = ?
                WHERE id = ?
            ");
            $stmt->execute([
                $name, $price, $stock, $category_id, $description,
                $image, $product_id
            ]);
            
            setFlashMessage('success', 'Cập nhật sản phẩm thành công');
            redirect('view.php?id=' . $product_id);
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật sản phẩm: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Page title
$pageTitle = 'Chỉnh Sửa Sản Phẩm';

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
                <h1 class="h2">Chỉnh Sửa Sản Phẩm</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="view.php?id=<?php echo $product_id; ?>" class="btn btn-sm btn-info me-2">
                        <i class="fas fa-eye"></i> Xem Sản Phẩm
                    </a>
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại
                    </a>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-body">
                            <form action="" method="POST" enctype="multipart/form-data">
                                <div class="mb-3">
                                    <label for="name" class="form-label">Tên Sản Phẩm <span class="text-danger">*</span></label>
                                    <input type="text" class="form-control" id="name" name="name" value="<?php echo htmlspecialchars($product['name']); ?>" required>
                                </div>
                                
                                <div class="row mb-3">
                                    <div class="col-md-4">
                                        <label for="price" class="form-label">Giá (₫) <span class="text-danger">*</span></label>
                                        <input type="number" class="form-control" id="price" name="price" min="0.01" step="0.01" value="<?php echo $product['price']; ?>" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label for="stock" class="form-label">Tồn Kho <span class="text-danger">*</span></label>
                                        <input type="number" class="form-control" id="stock" name="stock" min="0" step="1" value="<?php echo $product['stock']; ?>" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label for="category_id" class="form-label">Danh Mục</label>
                                        <select class="form-select" id="category_id" name="category_id">
                                            <option value="">Chọn Danh Mục</option>
                                            <?php foreach ($categories as $category): ?>
                                                <option value="<?php echo $category['id']; ?>" <?php echo $product['category_id'] == $category['id'] ? 'selected' : ''; ?>>
                                                    <?php echo htmlspecialchars($category['name']); ?>
                                                </option>
                                            <?php endforeach; ?>
                                        </select>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="description" class="form-label">Mô Tả</label>
                                    <textarea class="form-control" id="description" name="description" rows="4"><?php echo htmlspecialchars($product['description'] ?? ''); ?></textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="image" class="form-label">Hình Ảnh</label>
                                    <input type="file" class="form-control" id="image" name="image" accept="image/*">
                                    <small class="text-muted">Để trống nếu muốn giữ hình ảnh hiện tại. Tối đa: 2MB. Định dạng: JPG, PNG, GIF</small>
                                    
                                    <?php if (!empty($product['image'])): ?>
                                    <div class="mt-2">
                                        <p>Hình Ảnh Hiện Tại:</p>
                                        <img src="../../uploads/products/<?php echo $product['image']; ?>" alt="Hình Ảnh Sản Phẩm" class="img-thumbnail" style="max-height: 150px;">
                                    </div>
                                    <?php endif; ?>
                                </div>
                                
                                <div class="d-grid gap-2">
                                    <button type="submit" class="btn btn-primary">Cập Nhật Sản Phẩm</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Sản Phẩm</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Mã:</strong> <?php echo $product['id']; ?></p>
                            <p><strong>Ngày Tạo:</strong> <?php echo date('d/m/Y', strtotime($product['created_at'])); ?></p>
                            
                            <?php
                            // Get order count
                            try {
                                $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM orders WHERE product_id = ?");
                                $stmt->execute([$product_id]);
                                $orderCount = $stmt->fetch()['count'];
                            } catch (PDOException $e) {
                                $orderCount = 0;
                            }
                            
                            // Get review count
                            try {
                                $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM reviews WHERE product_id = ?");
                                $stmt->execute([$product_id]);
                                $reviewCount = $stmt->fetch()['count'];
                            } catch (PDOException $e) {
                                $reviewCount = 0;
                            }
                            ?>
                            
                            <p>
                                <strong>Đơn Hàng:</strong> 
                                <?php if ($orderCount > 0): ?>
                                    <a href="../orders/index.php?product_id=<?php echo $product_id; ?>" class="badge bg-primary">
                                        <?php echo $orderCount; ?> đơn hàng
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 đơn hàng</span>
                                <?php endif; ?>
                            </p>
                            
                            <p>
                                <strong>Đánh Giá:</strong> 
                                <?php if ($reviewCount > 0): ?>
                                    <a href="../reviews/index.php?product_id=<?php echo $product_id; ?>" class="badge bg-primary">
                                        <?php echo $reviewCount; ?> đánh giá
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 đánh giá</span>
                                <?php endif; ?>
                            </p>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Gợi Ý</h5>
                        </div>
                        <div class="card-body">
                            <ul class="list-unstyled">
                                <li><i class="fas fa-info-circle text-primary me-2"></i> Đặt tên sản phẩm rõ ràng và mô tả.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Mô tả chi tiết giúp khách hàng đưa ra quyết định tốt hơn.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>