<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra xem người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}
// Lấy tất cả danh mục cho dropdown
try {
    $stmt = $pdo->query("SELECT id, name FROM categories ORDER BY name ASC");
    $categories = $stmt->fetchAll();
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh mục: ' . $e->getMessage());
    $categories = [];
}

// Xử lý gửi form
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Validate input
    $name = clean($_POST['name']);
    $description = clean($_POST['description']);
    $price = (float)$_POST['price'];
    $stock = (int)$_POST['stock'];
    $category_id = !empty($_POST['category_id']) ? (int)$_POST['category_id'] : null;
    
    // Tạo slug
    $slug = generateSlug($name);
    
    // Kiểm tra các trường bắt buộc
    $errors = [];
    
    if (empty($name)) {
        $errors[] = 'Tên sản phẩm là bắt buộc';
    }
    
    if ($price < 0) {
        $errors[] = 'Giá phải là số dương';
    }
    
    if ($stock < 0) {
        $errors[] = 'Số lượng tồn kho phải là số dương';
    }
    
    // Kiểm tra xem tên sản phẩm đã tồn tại
    try {
        $stmt = $pdo->prepare("SELECT id FROM products WHERE name = ?");
        $stmt->execute([$name]);
        if ($stmt->rowCount() > 0) {
            $errors[] = 'Tên sản phẩm đã tồn tại';
        }
    } catch (PDOException $e) {
        $errors[] = 'Lỗi kiểm tra tên sản phẩm: ' . $e->getMessage();
    }
    
    // Xử lý upload hình ảnh
    $image = null;
    if (isset($_FILES['image']) && $_FILES['image']['error'] === UPLOAD_ERR_OK) {
        $uploadDir = '../../uploads/products/';
        
        // Tạo thư mục nếu không tồn tại
        if (!file_exists($uploadDir)) {
            mkdir($uploadDir, 0777, true);
        }
        
        $image = uploadImage($_FILES['image'], $uploadDir);
        
        if ($image === false) {
            $errors[] = 'File ảnh không hợp lệ. Vui lòng tải lên ảnh hợp lệ (JPG, JPEG, PNG, GIF) dưới 5MB.';
        }
    }
    
    // Nếu không có lỗi, thêm sản phẩm
    if (empty($errors)) {
        try {
            $stmt = $pdo->prepare("INSERT INTO products (name, slug, description, price, stock, image, category_id) VALUES (?, ?, ?, ?, ?, ?, ?)");
            $stmt->execute([$name, $slug, $description, $price, $stock, $image, $category_id]);
            
            setFlashMessage('success', 'Tạo sản phẩm thành công');
            redirect('index.php');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi tạo sản phẩm: ' . $e->getMessage());
        }
    } else {
        // Thiết lập thông báo lỗi
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Tiêu đề trang
$pageTitle = 'Tạo Sản Phẩm Mới';

// Thêm header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Main content -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Tạo Sản Phẩm Mới</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại Danh Sách
                    </a>
                </div>
            </div>
            
            <!-- Product form -->
            <div class="card">
                <div class="card-body">
                    <form action="" method="POST" enctype="multipart/form-data">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="name" class="form-label">Tên Sản Phẩm <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="name" name="name" required value="<?php echo isset($_POST['name']) ? htmlspecialchars($_POST['name']) : ''; ?>">
                            </div>
                            <div class="col-md-6">
                                <label for="category_id" class="form-label">Danh Mục</label>
                                <select class="form-select" id="category_id" name="category_id">
                                    <option value="">Chọn Danh Mục</option>
                                    <?php foreach ($categories as $category): ?>
                                    <option value="<?php echo $category['id']; ?>" <?php echo isset($_POST['category_id']) && $_POST['category_id'] == $category['id'] ? 'selected' : ''; ?>>
                                        <?php echo htmlspecialchars($category['name']); ?>
                                    </option>
                                    <?php endforeach; ?>
                                </select>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="price" class="form-label">Giá <span class="text-danger">*</span></label>
                                <div class="input-group">
                                    <span class="input-group-text">₫</span>
                                    <input type="number" class="form-control" id="price" name="price" step="0.01" min="0" required value="<?php echo isset($_POST['price']) ? htmlspecialchars($_POST['price']) : '0.00'; ?>">
                                </div>
                            </div>
                            <div class="col-md-6">
                                <label for="stock" class="form-label">Tồn Kho <span class="text-danger">*</span></label>
                                <input type="number" class="form-control" id="stock" name="stock" min="0" required value="<?php echo isset($_POST['stock']) ? htmlspecialchars($_POST['stock']) : '0'; ?>">
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="description" class="form-label">Mô Tả</label>
                            <textarea class="form-control" id="description" name="description" rows="5"><?php echo isset($_POST['description']) ? htmlspecialchars($_POST['description']) : ''; ?></textarea>
                        </div>
                        
                        <div class="mb-3">
                            <label for="image" class="form-label">Hình Ảnh Sản Phẩm</label>
                            <input type="file" class="form-control" id="image" name="image" accept="image/*">
                            <small class="text-muted">Định dạng hỗ trợ: JPG, JPEG, PNG, GIF. Kích thước tối đa: 5MB.</small>
                        </div>
                        
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                            <button type="reset" class="btn btn-secondary">Làm Mới</button>
                            <button type="submit" class="btn btn-primary">Tạo Sản Phẩm</button>
                        </div>
                    </form>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include '../includes/footer.php'; ?>