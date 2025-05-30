<?php
session_start();
require_once 'includes/functions.php';
require_once 'includes/auth.php';
require_once 'config/database.php';

// Check if user is logged in
if (!isLoggedIn()) {
    setFlashMessage('error', 'Vui lòng đăng nhập để quản lý giỏ hàng');
    redirect('login.php?redirect=cart.php');
}

$user_id = $_SESSION['user_id'];

// Fetch cart items from database
try {
    $stmt = $pdo->prepare("
        SELECT c.id AS cart_id, c.product_id, c.quantity, p.name, p.price, p.stock, p.image, p.slug
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ");
    $stmt->execute([$user_id]);
    $cart_items = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi tải giỏ hàng: ' . $e->getMessage());
    $cart_items = [];
}

// Handle cart actions
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];

    // Add product to cart
    if ($action === 'add' && isset($_POST['product_id']) && isset($_POST['quantity'])) {
        $product_id = (int)$_POST['product_id'];
        $quantity = (int)$_POST['quantity'];

        // Validate quantity
        if ($quantity <= 0) {
            $response = ['success' => false, 'message' => 'Số lượng phải lớn hơn 0'];
            if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
                header('Content-Type: application/json');
                echo json_encode($response);
                exit;
            }
            setFlashMessage('error', $response['message']);
            redirect('products.php');
        }

        try {
            // Check if product exists and has enough stock
            $stmt = $pdo->prepare("SELECT id, name, price, stock, image, slug FROM products WHERE id = ?");
            $stmt->execute([$product_id]);
            $product = $stmt->fetch();

            if (!$product) {
                $response = ['success' => false, 'message' => 'Sản phẩm không tồn tại'];
                if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
                    header('Content-Type: application/json');
                    echo json_encode($response);
                    exit;
                }
                setFlashMessage('error', $response['message']);
                redirect('products.php');
            }

            if ($product['stock'] < $quantity) {
                $response = ['success' => false, 'message' => 'Không đủ hàng trong kho. Chỉ còn ' . $product['stock'] . ' sản phẩm.'];
                if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
                    header('Content-Type: application/json');
                    echo json_encode($response);
                    exit;
                }
                setFlashMessage('error', $response['message']);
                redirect('products.php');
            }

            // Check if product is already in cart
            $stmt = $pdo->prepare("SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ?");
            $stmt->execute([$user_id, $product_id]);
            $cart_item = $stmt->fetch();

            if ($cart_item) {
                // Update quantity
                $new_quantity = $cart_item['quantity'] + $quantity;
                if ($new_quantity > $product['stock']) {
                    $response = ['success' => false, 'message' => 'Không thể thêm nhiều hơn. Số lượng tối đa: ' . $product['stock']];
                    if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
                        header('Content-Type: application/json');
                        echo json_encode($response);
                        exit;
                    }
                    setFlashMessage('error', $response['message']);
                    redirect('products.php');
                }
                $stmt = $pdo->prepare("UPDATE cart SET quantity = ? WHERE id = ?");
                $stmt->execute([$new_quantity, $cart_item['id']]);
            } else {
                // Insert new cart item
                $stmt = $pdo->prepare("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)");
                $stmt->execute([$user_id, $product_id, $quantity]);
            }

            $response = ['success' => true, 'message' => 'Đã thêm sản phẩm vào giỏ hàng'];
            if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
                header('Content-Type: application/json');
                echo json_encode($response);
                exit;
            }
            setFlashMessage('success', $response['message']);
            redirect('products.php');
        } catch (PDOException $e) {
            $response = ['success' => false, 'message' => 'Lỗi khi thêm sản phẩm: ' . $e->getMessage()];
            if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
                header('Content-Type: application/json');
                echo json_encode($response);
                exit;
            }
            setFlashMessage('error', $response['message']);
            redirect('products.php');
        }
    }

    // Update cart item quantity
    elseif ($action === 'update' && isset($_POST['cart'])) {
        $cart_updates = $_POST['cart'];
        $errors = [];

        foreach ($cart_updates as $product_id => $quantity) {
            $product_id = (int)$product_id;
            $quantity = (int)$quantity;

            if ($quantity <= 0) {
                try {
                    $stmt = $pdo->prepare("DELETE FROM cart WHERE user_id = ? AND product_id = ?");
                    $stmt->execute([$user_id, $product_id]);
                } catch (PDOException $e) {
                    $errors[] = 'Lỗi khi xóa sản phẩm: ' . $e->getMessage();
                }
                continue;
            }

            try {
                $stmt = $pdo->prepare("SELECT stock FROM products WHERE id = ?");
                $stmt->execute([$product_id]);
                $product = $stmt->fetch();

                if ($product && $quantity <= $product['stock']) {
                    $stmt = $pdo->prepare("
                        INSERT INTO cart (user_id, product_id, quantity)
                        VALUES (?, ?, ?)
                        ON DUPLICATE KEY UPDATE quantity = ?
                    ");
                    $stmt->execute([$user_id, $product_id, $quantity, $quantity]);
                } else {
                    $errors[] = $product ? 'Không đủ hàng. Số lượng tối đa: ' . $product['stock'] : 'Sản phẩm không tồn tại';
                }
            } catch (PDOException $e) {
                $errors[] = 'Lỗi cập nhật giỏ hàng: ' . $e->getMessage();
            }
        }

        $response = empty($errors) ? ['success' => true, 'message' => 'Cập nhật giỏ hàng thành công'] : ['success' => false, 'message' => implode('; ', $errors)];
        if (isset($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest') {
            header('Content-Type: application/json');
            echo json_encode($response);
            exit;
        }

        setFlashMessage($response['success'] ? 'success' : 'error', $response['message']);
        redirect('cart.php');
    }
}

// Handle remove and clear actions (via GET)
if (isset($_GET['action'])) {
    $action = $_GET['action'];

    // Remove item from cart
    if ($action === 'remove' && isset($_GET['id'])) {
        $product_id = (int)$_GET['id'];
        try {
            $stmt = $pdo->prepare("DELETE FROM cart WHERE user_id = ? AND product_id = ?");
            $stmt->execute([$user_id, $product_id]);
            setFlashMessage('success', 'Đã xóa sản phẩm khỏi giỏ hàng');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi xóa sản phẩm: ' . $e->getMessage());
        }
        redirect('cart.php');
    }

    // Clear entire cart
    elseif ($action === 'clear') {
        try {
            $stmt = $pdo->prepare("DELETE FROM cart WHERE user_id = ?");
            $stmt->execute([$user_id]);
            setFlashMessage('success', 'Đã xóa toàn bộ giỏ hàng');
        } catch (PDOException $e) {
            setFlashMessage('error', 'Lỗi khi xóa giỏ hàng: ' . $e->getMessage());
        }
        redirect('cart.php');
    }
}

// Calculate cart totals
$cart_total = 0;
$cart_item_count = 0;

foreach ($cart_items as $item) {
    $cart_total += $item['price'] * $item['quantity'];
    $cart_item_count += $item['quantity'];
}

// Page title
$pageTitle = 'Giỏ hàng';

// Include header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <div class="col-lg-8">
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h4 class="mb-0">Giỏ hàng (<?php echo $cart_item_count; ?> sản phẩm)</h4>
                </div>
                <div class="card-body">
                    <?php if (empty($cart_items)): ?>
                        <div class="alert alert-info">
                            <i class="fas fa-shopping-cart me-2"></i> Giỏ hàng của bạn đang trống.
                        </div>
                        <div class="text-center mt-4">
                            <a href="products.php" class="btn btn-dark">
                                <i class="fas fa-shopping-bag me-2"></i> Tiếp tục mua sắm
                            </a>
                        </div>
                    <?php else: ?>
                        <form id="cart-form" action="cart.php?action=update" method="POST">
                            <div class="table-responsive">
                                <table class="table table-hover">
                                    <thead>
                                        <tr>
                                            <th style="width: 100px;">Hình ảnh</th>
                                            <th>Sản phẩm</th>
                                            <th style="width: 120px;">Giá</th>
                                            <th style="width: 150px;">Số lượng</th>
                                            <th style="width: 120px;">Tổng</th>
                                            <th style="width: 50px;"></th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <?php foreach ($cart_items as $item): ?>
                                            <tr data-product-id="<?php echo $item['product_id']; ?>">
                                                <td>
                                                    <img src="uploads/products/<?php echo !empty($item['image']) ? $item['image'] : 'default.jpg'; ?>" 
                                                         alt="<?php echo htmlspecialchars($item['name']); ?>" 
                                                         class="img-thumbnail" style="max-height: 80px;">
                                                </td>
                                                <td>
                                                    <a href="product-detail.php?slug=<?php echo $item['slug']; ?>" class="text-decoration-none">
                                                        <?php echo htmlspecialchars($item['name']); ?>
                                                    </a>
                                                </td>
                                                <td data-price="<?php echo $item['price']; ?>"><?php echo number_format($item['price'], 0) . '₫'; ?></td>
                                                <td>
                                                    <div class="input-group">
                                                        <button type="button" class="btn btn-outline-secondary btn-sm quantity-btn" data-action="decrease" data-product-id="<?php echo $item['product_id']; ?>">
                                                            <i class="fas fa-minus"></i>
                                                        </button>
                                                        <input type="number" name="cart[<?php echo $item['product_id']; ?>]" value="<?php echo $item['quantity']; ?>" 
                                                               min="1" max="<?php echo $item['stock']; ?>" class="form-control form-control-sm text-center quantity-input" 
                                                               data-product-id="<?php echo $item['product_id']; ?>">
                                                        <button type="button" class="btn btn-outline-secondary btn-sm quantity-btn" data-action="increase" data-product-id="<?php echo $item['product_id']; ?>">
                                                            <i class="fas fa-plus"></i>
                                                        </button>
                                                    </div>
                                                </td>
                                                <td class="item-total"><?php echo number_format($item['price'] * $item['quantity'], 0) . '₫'; ?></td>
                                                <td>
                                                    <a href="cart.php?action=remove&id=<?php echo $item['product_id']; ?>" class="btn btn-sm btn-danger" 
                                                       onclick="return confirm('Bạn có chắc chắn muốn xóa sản phẩm này?')">
                                                        <i class="fas fa-trash"></i>
                                                    </a>
                                                </td>
                                            </tr>
                                        <?php endforeach; ?>
                                    </tbody>
                                </table>
                            </div>
                            
                            <div class="d-flex justify-content-between mt-4">
                                <a href="products.php" class="btn btn-outline-dark">
                                    <i class="fas fa-arrow-left me-2"></i> Tiếp tục mua sắm
                                </a>
                                <div>
                                    <a href="cart.php?action=clear" class="btn btn-outline-danger me-2" 
                                       onclick="return confirm('Bạn có chắc chắn muốn xóa toàn bộ giỏ hàng?')">
                                        <i class="fas fa-trash me-2"></i> Xóa giỏ hàng
                                    </a>
                                    <button type="submit" class="btn btn-dark">
                                        <i class="fas fa-sync-alt me-2"></i> Cập nhật giỏ hàng
                                    </button>
                                </div>
                            </div>
                        </form>
                    <?php endif; ?>
                </div>
            </div>
        </div>
        
        <div class="col-lg-4">
            <!-- Order Summary -->
            <div class="card mb-4">
                <div class="card-header bg-dark text-white">
                    <h5 class="mb-0">Tổng đơn hàng</h5>
                </div>
                <div class="card-body">
                    <div class="d-flex justify-content-between mb-2">
                        <span>Tạm tính:</span>
                        <span class="subtotal"><?php echo number_format($cart_total, 0) . '₫'; ?></span>
                    </div>
                    <div class="d-flex justify-content-between mb-2">
                        <span>Phí vận chuyển:</span>
                        <span><?php echo $cart_total > 0 ? 'Tính khi thanh toán' : '0₫'; ?></span>
                    </div>
                    <div class="d-flex justify-content-between mb-2">
                        <span>Thuế:</span>
                        <span><?php echo $cart_total > 0 ? 'Tính khi thanh toán' : '0₫'; ?></span>
                    </div>
                    <hr>
                    <div class="d-flex justify-content-between mb-4">
                        <strong>Tổng cộng:</strong>
                        <strong class="total"><?php echo number_format($cart_total, 0) . '₫'; ?></strong>
                    </div>
                    
                    <?php if (!empty($cart_items)): ?>
                        <?php if (isLoggedIn()): ?>
                            <div class="d-grid">
                                <a href="checkout.php" class="btn btn-success btn-lg">
                                    <i class="fas fa-credit-card me-2"></i> Tiến hành thanh toán
                                </a>
                            </div>
                        <?php else: ?>
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i> Vui lòng <a href="login.php?redirect=cart.php" class="alert-link">đăng nhập</a> để tiến hành thanh toán.
                            </div>
                            <div class="d-grid gap-2">
                                <a href="login.php?redirect=cart.php" class="btn btn-dark">
                                    <i class="fas fa-sign-in-alt me-2"></i> Đăng nhập để thanh toán
                                </a>
                                <a href="register.php?redirect=cart.php" class="btn btn-outline-dark">
                                    <i class="fas fa-user-plus me-2"></i> Đăng ký
                                </a>
                            </div>
                        <?php endif; ?>
                    <?php endif; ?>
                </div>
            </div>
            
            <!-- Promo Code -->
            <?php if (!empty($cart_items)): ?>
            <div class="card">
                <div class="card-header bg-light">
                    <h5 class="mb-0">Mã giảm giá</h5>
                </div>
                <div class="card-body">
                    <form action="#" method="POST">
                        <div class="input-group mb-3">
                            <input type="text" class="form-control" placeholder="Nhập mã giảm giá" name="promo_code">
                            <button class="btn btn-outline-dark" type="submit">Áp dụng</button>
                        </div>
                    </form>
                </div>
            </div>
            <?php endif; ?>
        </div>
    </div>
    
    <?php if (!empty($cart_items)): ?>
    <!-- Recently Viewed Products -->
    <?php
    // Get recently viewed products from session
    $recently_viewed = isset($_SESSION['recently_viewed']) ? $_SESSION['recently_viewed'] : [];
    
    if (!empty($recently_viewed)) {
        try {
            // Get products that are not in cart
            $placeholders = implode(',', array_fill(0, count($recently_viewed), '?'));
            $cart_ids = array_column($cart_items, 'product_id');
            
            $query = "SELECT id, name, price, image, slug FROM products WHERE id IN ($placeholders)";
            $params = $recently_viewed;
            
            if (!empty($cart_ids)) {
                $query .= " AND id NOT IN (" . implode(',', array_fill(0, count($cart_ids), '?')) . ")";
                $params = array_merge($params, $cart_ids);
            }
            
            $query .= " LIMIT 4";
            
            $stmt = $pdo->prepare($query);
            $stmt->execute($params);
            $recent_products = $stmt->fetchAll();
            
            if (!empty($recent_products)):
    ?>
    <div class="row mt-5">
        <div class="col-12">
            <h3>Sản phẩm đã xem</h3>
            <div class="row">
                <?php foreach ($recent_products as $product): ?>
                <div class="col-md-3 col-sm-6 mb-4">
                    <div class="card h-100">
                        <img src="uploads/products/<?php echo !empty($product['image']) ? $product['image'] : 'default.jpg'; ?>" 
                             class="card-img-top" alt="<?php echo htmlspecialchars($product['name']); ?>"
                             style="height: 200px; object-fit: contain; padding: 10px;">
                        <div class="card-body">
                            <h5 class="card-title"><?php echo htmlspecialchars($product['name']); ?></h5>
                            <p class="card-text text-primary fw-bold"><?php echo number_format($product['price'], 0) . '₫'; ?></p>
                            <div class="d-grid">
                                <a href="product-detail.php?slug=<?php echo $product['slug']; ?>" class="btn btn-outline-dark">Xem chi tiết</a>
                            </div>
                        </div>
                    </div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>
    </div>
    <?php 
            endif;
        } catch (PDOException $e) {
            // Silently fail for recently viewed section
        }
    }
    ?>
    <?php endif; ?>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Get all quantity buttons and inputs
    const quantityButtons = document.querySelectorAll('.quantity-btn');
    const quantityInputs = document.querySelectorAll('.quantity-input');
    
    // Function to update cart totals
    function updateCartTotals() {
        let subtotal = 0;
        document.querySelectorAll('.quantity-input').forEach(input => {
            const row = input.closest('tr');
            const price = parseFloat(row.querySelector('td[data-price]').getAttribute('data-price'));
            const quantity = parseInt(input.value) || 0;
            const itemTotal = price * quantity;
            
            // Update item total
            row.querySelector('.item-total').textContent = numberFormat(itemTotal) + '₫';
            subtotal += itemTotal;
        });
        
        // Update cart totals
        document.querySelector('.subtotal').textContent = numberFormat(subtotal) + '₫';
        document.querySelector('.total').textContent = numberFormat(subtotal) + '₫';
    }
    
    // Function to format number
    function numberFormat(number) {
        return number.toLocaleString('vi-VN', { minimumFractionDigits: 0 });
    }
    
    // Function to show flash messages
    function showFlashMessage(type, message) {
        const existingAlerts = document.querySelectorAll('.alert');
        existingAlerts.forEach(alert => alert.remove());
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.style.position = 'fixed';
        alert.style.top = '20px';
        alert.style.right = '20px';
        alert.style.zIndex = '1050';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.appendChild(alert);
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 200);
        }, 3000);
    }
    
    // Function to update cart via AJAX
    function updateCart(productId, quantity) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('action', 'update');
            formData.append(`cart[${productId}]`, quantity);
            
            fetch('cart.php', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    resolve(data);
                } else {
                    reject(new Error(data.message));
                }
            })
            .catch(error => reject(error));
        });
    }
    
    // Handle quantity buttons
    quantityButtons.forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const action = this.getAttribute('data-action');
            const input = this.parentNode.querySelector('.quantity-input');
            const currentValue = parseInt(input.value) || 0;
            const max = parseInt(input.getAttribute('max'));
            const productId = input.getAttribute('data-product-id');
            
            let newValue = currentValue;
            if (action === 'increase' && currentValue < max) {
                newValue = currentValue + 1;
            } else if (action === 'decrease' && currentValue > 1) {
                newValue = currentValue - 1;
            }
            
            if (newValue !== currentValue) {
                try {
                    // Update UI first
                    input.value = newValue;
                    updateCartTotals();
                    
                    // Then update server
                    const result = await updateCart(productId, newValue);
                    showFlashMessage('success', result.message);
                } catch (error) {
                    console.error('Error:', error);
                    // Revert changes on error
                    input.value = currentValue;
                    updateCartTotals();
                    showFlashMessage('error', error.message || 'Lỗi khi cập nhật giỏ hàng');
                }
            }
        });
    });
    
    // Handle direct input changes
    quantityInputs.forEach(input => {
        input.addEventListener('change', async function() {
            const currentValue = parseInt(this.value) || 0;
            const max = parseInt(this.getAttribute('max'));
            const min = parseInt(this.getAttribute('min')) || 1;
            const productId = this.getAttribute('data-product-id');
            
            let newValue = currentValue;
            if (currentValue > max) {
                newValue = max;
            } else if (currentValue < min) {
                newValue = min;
            }
            
            if (newValue !== currentValue) {
                try {
                    // Update UI first
                    this.value = newValue;
                    updateCartTotals();
                    
                    // Then update server
                    const result = await updateCart(productId, newValue);
                    showFlashMessage('success', result.message);
                } catch (error) {
                    console.error('Error:', error);
                    // Revert changes on error
                    this.value = currentValue;
                    updateCartTotals();
                    showFlashMessage('error', error.message || 'Lỗi khi cập nhật giỏ hàng');
                }
            }
        });
    });
    
    // Initial update of cart totals
    updateCartTotals();
});
</script>

<?php include 'includes/footer.php'; ?>