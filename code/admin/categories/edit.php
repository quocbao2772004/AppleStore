<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../index.php');
}

// Kiểm tra ID đã được cung cấp
if (!isset($_GET['id']) || empty($_GET['id'])) {
    setFlashMessage('error', 'ID danh mục là bắt buộc');
    redirect('index.php');
}

$category_id = (int)$_GET['id'];

// Lấy dữ liệu danh mục
try {
    $stmt = $pdo->prepare("SELECT * FROM categories WHERE id = ?");
    $stmt->execute([$category_id]);
    $category = $stmt->fetch();
    
    if (!$category) {
        setFlashMessage('error', 'Không tìm thấy danh mục');
        redirect('index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy danh mục: ' . $e->getMessage());
    redirect('index.php');
}

// Xử lý gửi form
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name = clean($_POST['name']);
    $slug = !empty($_POST['slug']) ? clean($_POST['slug']) : createSlug($name);
    $description = !empty($_POST['description']) ? clean($_POST['description']) : null;
    
    // Kiểm tra dữ liệu
    $errors = [];
    
    if (empty($name)) {
        $errors[] = 'Tên danh mục là bắt buộc';
    }
    
    // Kiểm tra slug đã tồn tại chưa (trừ danh mục hiện tại)
    try {
        $stmt = $pdo->prepare("SELECT id FROM categories WHERE slug = ? AND id != ?");
        $stmt->execute([$slug, $category_id]);
        if ($stmt->rowCount() > 0) {
            $errors[] = 'Đã tồn tại danh mục với slug này';
        }
    } catch (PDOException $e) {
        $errors[] = 'Lỗi khi kiểm tra slug: ' . $e->getMessage();
    }
    
    // Nếu không có lỗi, cập nhật danh mục
    if (empty($errors)) {
        try {
            $stmt = $pdo->prepare("UPDATE categories SET name = ?, slug = ?, description = ?, updated_at = NOW() WHERE id = ?");
            $stmt->execute([$name, $slug, $description, $category_id]);
            
            setFlashMessage('success', 'Đã cập nhật danh mục thành công');
            redirect('index.php');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi cập nhật danh mục: ' . $e->getMessage());
        }
    } else {
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Tiêu đề trang
$pageTitle = 'Chỉnh Sửa Danh Mục';

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
                <h1 class="h2">Chỉnh Sửa Danh Mục</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <a href="index.php" class="btn btn-sm btn-secondary">
                        <i class="fas fa-arrow-left"></i> Quay Lại Danh Mục
                    </a>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-body">
                            <form action="" method="POST">
                                <div class="mb-3">
                                    <label for="name" class="form-label">Tên Danh Mục <span class="text-danger">*</span></label>
                                    <input type="text" class="form-control" id="name" name="name" value="<?php echo htmlspecialchars($category['name']); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="slug" class="form-label">Slug</label>
                                    <input type="text" class="form-control" id="slug" name="slug" value="<?php echo htmlspecialchars($category['slug']); ?>">
                                    <small class="text-muted">Để trống để tự động tạo từ tên</small>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="description" class="form-label">Mô Tả</label>
                                    <textarea class="form-control" id="description" name="description" rows="4"><?php echo htmlspecialchars($category['description'] ?? ''); ?></textarea>
                                </div>
                                
                                <div class="d-grid gap-2">
                                    <button type="submit" class="btn btn-primary">Cập Nhật Danh Mục</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Thông Tin Danh Mục</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>ID:</strong> <?php echo $category['id']; ?></p>
                            <p><strong>Ngày Tạo:</strong> <?php echo date('d/m/Y', strtotime($category['created_at'])); ?></p>
                            <p><strong>Cập Nhật Lần Cuối:</strong> <?php echo date('d/m/Y', strtotime($category['updated_at'])); ?></p>
                            
                            <?php
                            // Lấy số lượng sản phẩm
                            try {
                                $stmt = $pdo->prepare("SELECT COUNT(*) as count FROM products WHERE category_id = ?");
                                $stmt->execute([$category_id]);
                                $productCount = $stmt->fetch()['count'];
                            } catch (PDOException $e) {
                                $productCount = 0;
                            }
                            ?>
                            
                            <p>
                                <strong>Sản Phẩm:</strong> 
                                <?php if ($productCount > 0): ?>
                                    <a href="../products/index.php?category=<?php echo $category_id; ?>" class="badge bg-primary">
                                        <?php echo $productCount; ?> sản phẩm
                                    </a>
                                <?php else: ?>
                                    <span class="badge bg-secondary">0 sản phẩm</span>
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
                                <li><i class="fas fa-info-circle text-primary me-2"></i> Tên danh mục nên rõ ràng và mô tả được nội dung.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Slug được sử dụng trong URL và chỉ nên chứa chữ thường, số và dấu gạch ngang.</li>
                                <li class="mt-2"><i class="fas fa-info-circle text-primary me-2"></i> Mô tả tốt giúp người dùng hiểu rõ những sản phẩm thuộc danh mục này.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<script>
// Tự động tạo slug từ tên
document.getElementById('name').addEventListener('keyup', function() {
    const nameValue = this.value.trim();
    const slugField = document.getElementById('slug');
    const originalSlug = "<?php echo htmlspecialchars($category['slug']); ?>";
    
    // Chỉ cập nhật slug nếu nó trống hoặc chưa được chỉnh sửa thủ công
    if (!slugField.value || slugField.value === createSlug(nameValue.substring(0, nameValue.length - 1))) {
        slugField.value = createSlug(nameValue);
    }
});

function createSlug(text) {
    return text
        .toLowerCase()
        .replace(/[^\w ]+/g, '')
        .replace(/ +/g, '-');
}
</script>

<?php include '../includes/footer.php'; ?>