<?php
require_once 'includes/functions.php';
require_once 'config/database.php';

// Lấy sản phẩm theo slug
$slug = isset($_GET['slug']) ? clean($_GET['slug']) : '';

if (empty($slug)) {
    setFlashMessage('error', 'Không tìm thấy sản phẩm');
    redirect('products.php');
}

try {
    $stmt = $pdo->prepare("SELECT p.*, c.name as category_name 
                          FROM products p 
                          LEFT JOIN categories c ON p.category_id = c.id 
                          WHERE p.slug = ?");
    $stmt->execute([$slug]);
    
    if ($stmt->rowCount() === 0) {
        setFlashMessage('error', 'Không tìm thấy sản phẩm');
        redirect('products.php');
    }
    
    $product = $stmt->fetch();
    
    // Lấy sản phẩm liên quan
    $stmt = $pdo->prepare("SELECT p.*, c.name as category_name 
                          FROM products p 
                          LEFT JOIN categories c ON p.category_id = c.id 
                          WHERE p.category_id = ? AND p.id != ? 
                          ORDER BY RAND() 
                          LIMIT 4");
    $stmt->execute([$product['category_id'], $product['id']]);
    $relatedProducts = $stmt->fetchAll();
    
    // Lấy đánh giá sản phẩm
    $stmt = $pdo->prepare("SELECT r.*, u.name as user_name 
                          FROM reviews r 
                          JOIN users u ON r.user_id = u.id 
                          WHERE r.product_id = ? AND r.status = 'approved' 
                          ORDER BY r.created_at DESC");
    $stmt->execute([$product['id']]);
    $reviews = $stmt->fetchAll();
    
    // Tính điểm đánh giá trung bình
    $avgRating = 0;
    $totalReviews = count($reviews);
    
    if ($totalReviews > 0) {
        $totalRating = 0;
        foreach ($reviews as $review) {
            $totalRating += $review['rating'];
        }
        $avgRating = round($totalRating / $totalReviews, 1);
    }
    
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi tải sản phẩm: ' . $e->getMessage());
    redirect('products.php');
}

// Xử lý thêm vào giỏ hàng
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'add_to_cart') {
    $quantity = isset($_POST['quantity']) ? (int)$_POST['quantity'] : 1;
    
    // Kiểm tra số lượng
    if ($quantity <= 0) {
        $quantity = 1;
    }
    
    // Kiểm tra tồn kho
    if ($quantity > $product['stock']) {
        setFlashMessage('error', 'Không đủ hàng trong kho. Chỉ còn ' . $product['stock'] . ' sản phẩm.');
    } else {
        // Khởi tạo giỏ hàng nếu chưa có
        if (!isset($_SESSION['cart']) || !is_array($_SESSION['cart'])) {
            $_SESSION['cart'] = [];
        }
        
        // Kiểm tra sản phẩm đã có trong giỏ hàng chưa
        $productInCart = false;
        foreach ($_SESSION['cart'] as $key => $item) {
            if ($item['id'] == $product['id']) {
                // Cập nhật số lượng
                $_SESSION['cart'][$key]['quantity'] += $quantity;
                $productInCart = true;
                break;
            }
        }
        
        // Thêm sản phẩm vào giỏ hàng nếu chưa có
        if (!$productInCart) {
            $_SESSION['cart'][] = [
                'id' => $product['id'],
                'name' => $product['name'],
                'price' => $product['price'],
                'quantity' => $quantity,
                'image' => $product['image']
            ];
        }
        
        setFlashMessage('success', 'Đã thêm sản phẩm vào giỏ hàng thành công');
        redirect('product-detail.php?slug=' . $slug);
    }
}

// Xử lý thêm đánh giá
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'add_review') {
    // Kiểm tra đăng nhập
    if (!isLoggedIn()) {
        setFlashMessage('error', 'Vui lòng đăng nhập để đánh giá');
        redirect('login.php?redirect=product-detail.php?slug=' . $slug);
    }
    
    $rating = isset($_POST['rating']) ? (int)$_POST['rating'] : 0;
    $comment = isset($_POST['comment']) ? clean($_POST['comment']) : '';
    
    // Kiểm tra đánh giá
    if ($rating < 1 || $rating > 5) {
        setFlashMessage('error', 'Vui lòng chọn số sao từ 1-5');
    } else {
        try {
            // Kiểm tra người dùng đã đánh giá sản phẩm này chưa
            $stmt = $pdo->prepare("SELECT id FROM reviews WHERE product_id = ? AND user_id = ?");
            $stmt->execute([$product['id'], $_SESSION['user_id']]);
            
            if ($stmt->rowCount() > 0) {
                // Cập nhật đánh giá cũ
                $stmt = $pdo->prepare("UPDATE reviews SET rating = ?, comment = ?, status = 'pending' WHERE product_id = ? AND user_id = ?");
                $stmt->execute([$rating, $comment, $product['id'], $_SESSION['user_id']]);
                setFlashMessage('success', 'Đánh giá của bạn đã được cập nhật và đang chờ duyệt');
            } else {
                // Thêm đánh giá mới
                $stmt = $pdo->prepare("INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)");
                $stmt->execute([$product['id'], $_SESSION['user_id'], $rating, $comment]);
                setFlashMessage('success', 'Đánh giá của bạn đã được gửi và đang chờ duyệt');
            }
            
            redirect('product-detail.php?slug=' . $slug);
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi gửi đánh giá: ' . $e->getMessage());
        }
    }
}

// Tiêu đề trang
$pageTitle = $product['name'];

// Thêm header
include 'includes/header.php';
?>

<div class="container py-5">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="index.php">Trang chủ</a></li>
            <li class="breadcrumb-item"><a href="products.php">Sản phẩm</a></li>
            <?php if (!empty($product['category_name'])): ?>
            <li class="breadcrumb-item"><a href="products.php?category=<?php echo $product['category_id']; ?>"><?php echo ucfirst(strtolower(htmlspecialchars($product['category_name']))); ?></a></li>
            <?php endif; ?>
            <li class="breadcrumb-item active" aria-current="page"><?php echo htmlspecialchars($product['name']); ?></li>
        </ol>
    </nav>
    
    <div class="row">
        <!-- Ảnh sản phẩm -->
        <div class="col-md-5 mb-4">
            <div class="card h-100">
                <?php if (!empty($product['image'])): ?>
                    <div style="height: 400px; overflow: hidden;">
                        <img src="uploads/products/<?php echo $product['image']; ?>" class="card-img-top h-100 w-100" alt="<?php echo htmlspecialchars($product['name']); ?>" style="object-fit: contain;">
                    </div>
                <?php else: ?>
                    <div style="height: 400px; overflow: hidden;">
                        <img src="assets/images/no-image.jpg" class="card-img-top h-100 w-100" alt="Không có ảnh" style="object-fit: contain;">
                    </div>
                <?php endif; ?>
            </div>
        </div>
        
        <!-- Chi tiết sản phẩm -->
        <div class="col-md-7 mb-4">
            <h1 class="mb-3"><?php echo htmlspecialchars($product['name']); ?></h1>
            
            <!-- Đánh giá -->
            <div class="mb-3">
                <?php for ($i = 1; $i <= 5; $i++): ?>
                    <?php if ($i <= $avgRating): ?>
                        <i class="fas fa-star text-warning"></i>
                    <?php elseif ($i <= $avgRating + 0.5): ?>
                        <i class="fas fa-star-half-alt text-warning"></i>
                    <?php else: ?>
                        <i class="far fa-star text-warning"></i>
                    <?php endif; ?>
                <?php endfor; ?>
                <span class="ms-2"><?php echo $avgRating; ?> (<?php echo $totalReviews; ?> đánh giá)</span>
            </div>
            
            <!-- Giá -->
            <div class="mb-3">
                <h2 class="text-primary"><?php echo number_format($product['price'], 0) . " VNĐ"; ?></h2>
            </div>
            
            <!-- Danh mục -->
            <?php if (!empty($product['category_name'])): ?>
            <div class="mb-3">
                <p><strong>Danh mục:</strong> <a href="products.php?category=<?php echo $product['category_id']; ?>"><?php echo ucfirst(strtolower(htmlspecialchars($product['category_name']))); ?></a></p>
            </div>
            <?php endif; ?>
            
            <!-- Tồn kho -->
            <div class="mb-3">
                <p>
                    <strong>Tình trạng:</strong> 
                    <?php if ($product['stock'] > 0): ?>
                        <span class="text-success">Còn hàng (<?php echo $product['stock']; ?> sản phẩm)</span>
                    <?php else: ?>
                        <span class="text-danger">Hết hàng</span>
                    <?php endif; ?>
                </p>
            </div>
            
            <!-- Mô tả -->
            <div class="mb-4">
                <h5>Mô tả sản phẩm:</h5>
                <p><?php echo nl2br(htmlspecialchars($product['description'])); ?></p>
            </div>
            
            <!-- Form thêm vào giỏ hàng -->
            <?php if ($product['stock'] > 0): ?>
            <form action="" method="POST" class="mb-4">
                <input type="hidden" name="action" value="add_to_cart">
                <div class="row g-3 align-items-center">
                    <div class="col-auto">
                        <label for="quantity" class="col-form-label">Số lượng:</label>
                    </div>
                    <div class="col-auto">
                        <input type="number" id="quantity" name="quantity" class="form-control" value="1" min="1" max="<?php echo $product['stock']; ?>">
                    </div>
                    <div class="col-auto">
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-cart-plus me-2"></i> Thêm vào giỏ hàng
                        </button>
                    </div>
                </div>
            </form>
            <?php else: ?>
            <div class="alert alert-warning">
                Sản phẩm hiện đã hết hàng
            </div>
            <?php endif; ?>
            
            <!-- Nút chia sẻ -->
            <div class="mt-4">
                <h5>Chia sẻ sản phẩm</h5>
                <div class="d-flex">
                    <a href="#" class="btn btn-outline-primary me-2"><i class="fab fa-facebook-f"></i></a>
                    <a href="#" class="btn btn-outline-info me-2"><i class="fab fa-twitter"></i></a>
                    <a href="#" class="btn btn-outline-danger me-2"><i class="fab fa-pinterest"></i></a>
                    <a href="#" class="btn btn-outline-success"><i class="fab fa-whatsapp"></i></a>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Tab đánh giá và thông tin bổ sung -->
    <div class="row mt-5">
        <div class="col-12">
            <ul class="nav nav-tabs" id="productTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="reviews-tab" data-bs-toggle="tab" data-bs-target="#reviews" type="button" role="tab" aria-controls="reviews" aria-selected="true">Đánh giá (<?php echo $totalReviews; ?>)</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="shipping-tab" data-bs-toggle="tab" data-bs-target="#shipping" type="button" role="tab" aria-controls="shipping" aria-selected="false">Giao hàng & Đổi trả</button>
                </li>
            </ul>
            <div class="tab-content p-4 border border-top-0 rounded-bottom" id="productTabsContent">
                <!-- Tab đánh giá -->
                <div class="tab-pane fade show active" id="reviews" role="tabpanel" aria-labelledby="reviews-tab">
                    <!-- Form đánh giá -->
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="mb-0">Đánh giá của bạn</h5>
                        </div>
                        <div class="card-body">
                            <?php if (isLoggedIn()): ?>
                            <form action="" method="POST">
                                <input type="hidden" name="action" value="add_review">
                                <div class="mb-3">
                                    <label for="rating" class="form-label">Số sao</label>
                                    <div class="rating">
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" name="rating" id="rating1" value="1" required>
                                            <label class="form-check-label" for="rating1">1</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" name="rating" id="rating2" value="2">
                                            <label class="form-check-label" for="rating2">2</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" name="rating" id="rating3" value="3">
                                            <label class="form-check-label" for="rating3">3</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" name="rating" id="rating4" value="4">
                                            <label class="form-check-label" for="rating4">4</label>
                                        </div>
                                        <div class="form-check form-check-inline">
                                            <input class="form-check-input" type="radio" name="rating" id="rating5" value="5">
                                            <label class="form-check-label" for="rating5">5</label>
                                        </div>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label for="comment" class="form-label">Nhận xét của bạn</label>
                                    <textarea class="form-control" id="comment" name="comment" rows="3" required></textarea>
                                </div>
                                <button type="submit" class="btn btn-primary">Gửi đánh giá</button>
                            </form>
                            <?php else: ?>
                            <div class="alert alert-info">
                                Vui lòng <a href="login.php?redirect=product-detail.php?slug=<?php echo $slug; ?>">đăng nhập</a> để đánh giá sản phẩm.
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                    
                    <!-- Danh sách đánh giá -->
                    <?php if (count($reviews) > 0): ?>
                    <div class="reviews">
                        <?php foreach ($reviews as $review): ?>
                        <div class="card mb-3">
                            <div class="card-body">
                                <div class="d-flex justify-content-between mb-2">
                                    <div>
                                        <h5 class="mb-0"><?php echo htmlspecialchars($review['user_name']); ?></h5>
                                        <div class="text-muted small">
                                            <?php echo date('d/m/Y', strtotime($review['created_at'])); ?>
                                        </div>
                                    </div>
                                    <div>
                                        <?php for ($i = 1; $i <= 5; $i++): ?>
                                            <?php if ($i <= $review['rating']): ?>
                                                <i class="fas fa-star text-warning"></i>
                                            <?php else: ?>
                                                <i class="far fa-star text-warning"></i>
                                            <?php endif; ?>
                                        <?php endfor; ?>
                                    </div>
                                </div>
                                <p class="mb-0"><?php echo nl2br(htmlspecialchars($review['comment'])); ?></p>
                            </div>
                        </div>
                        <?php endforeach; ?>
                    </div>
                    <?php else: ?>
                    <div class="alert alert-info">
                        Chưa có đánh giá nào. Hãy là người đầu tiên đánh giá sản phẩm này!
                    </div>
                    <?php endif; ?>
                </div>
                
                <!-- Tab giao hàng & đổi trả -->
                <div class="tab-pane fade" id="shipping" role="tabpanel" aria-labelledby="shipping-tab">
                    <h4>Thông tin giao hàng</h4>
                    <p>Chúng tôi cung cấp các phương thức giao hàng sau:</p>
                    <ul>
                        <li><strong>Giao hàng tiêu chuẩn:</strong> 3-5 ngày làm việc (miễn phí cho đơn hàng trên 1.000.000đ)</li>
                        <li><strong>Giao hàng nhanh:</strong> 1-2 ngày làm việc (phí 100.000đ)</li>
                        <li><strong>Giao hàng hỏa tốc:</strong> Trong ngày (phí 200.000đ)</li>
                    </ul>
                    
                    <h4 class="mt-4">Chính sách đổi trả</h4>
                    <p>Chúng tôi chấp nhận đổi trả trong vòng 30 ngày kể từ ngày mua. Sản phẩm phải còn nguyên vẹn và chưa qua sử dụng.</p>
                    <p>Quy trình đổi trả:</p>
                    <ol>
                        <li>Đăng nhập vào tài khoản của bạn</li>
                        <li>Chọn đơn hàng và sản phẩm cần đổi trả</li>
                        <li>In phiếu đổi trả và gửi sản phẩm về cho chúng tôi</li>
                    </ol>
                    <p>Thời gian xử lý đổi trả: 5-7 ngày làm việc sau khi nhận được hàng.</p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Sản phẩm liên quan -->
    <?php if (count($relatedProducts) > 0): ?>
    <div class="row mt-5">
        <div class="col-12">
            <h3 class="mb-4">Sản phẩm liên quan</h3>
            <div class="row">
                <?php foreach ($relatedProducts as $relatedProduct): ?>
                <div class="col-md-3 col-sm-6 mb-4">
                    <div class="card h-100 shadow-sm">
                        <div style="height: 200px; overflow: hidden;">
                            <?php if (!empty($relatedProduct['image'])): ?>
                                <img src="uploads/products/<?php echo $relatedProduct['image']; ?>" class="card-img-top h-100 w-100" alt="<?php echo htmlspecialchars($relatedProduct['name']); ?>" style="object-fit: contain;">
                            <?php else: ?>
                                <img src="assets/images/no-image.jpg" class="card-img-top h-100 w-100" alt="Không có ảnh" style="object-fit: contain;">
                            <?php endif; ?>
                        </div>
                        <div class="card-body">
                            <h5 class="card-title"><?php echo htmlspecialchars($relatedProduct['name']); ?></h5>
                            <p class="card-text fw-bold"><?php echo formatPrice($relatedProduct['price']); ?> VNĐ</p>
                            <div class="d-flex justify-content-between">
                                <a href="product-detail.php?slug=<?php echo $relatedProduct['slug']; ?>" class="btn btn-outline-primary">Xem chi tiết</a>
                                <form action="cart.php" method="POST">
                                    <input type="hidden" name="product_id" value="<?php echo $relatedProduct['id']; ?>">
                                    <input type="hidden" name="action" value="add">
                                    <button type="submit" class="btn btn-primary">
                                        <i class="fas fa-cart-plus"></i>
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>
    </div>
    <?php endif; ?>
</div>

<?php include 'includes/footer.php'; ?>