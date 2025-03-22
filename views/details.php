<?php
session_start();
include '../config/fetch_product.php'; // Giả sử file này chứa kết nối $pdo

// Kết nối cơ sở dữ liệu (nếu fetch_product.php chưa có)
if (!isset($pdo)) {
    $host = 'localhost';
    $dbname = 'apple_store';
    $username = 'root';
    $password = '';
    try {
        $pdo = new PDO("mysql:host=$host;dbname=$dbname", $username, $password);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    } catch (PDOException $e) {
        die("Kết nối thất bại: " . $e->getMessage());
    }
}

// Kiểm tra đăng nhập
if (!isset($_SESSION['user_id']) || !isset($_SESSION['user_email'])) {
    die("Vui lòng đăng nhập để thêm sản phẩm vào giỏ hàng.");
}
$user_id = $_SESSION['user_id'];
$user_email = $_SESSION['user_email'];

// Lấy ID sản phẩm từ URL
$product_id = isset($_GET['id']) ? (int)$_GET['id'] : 0;

// Xử lý khi nhấn "Thêm vào giỏ"
if (isset($_POST['add_to_cart']) && isset($_POST['product_id'])) {
    $quantity = isset($_POST['quantity']) ? (int)$_POST['quantity'] : 1;
    $capacity = isset($_POST['capacity']) ? $_POST['capacity'] : '128GB';

    try {
        $query = "SELECT * FROM products WHERE id = :id";
        $stmt = $pdo->prepare($query);
        $stmt->bindParam(':id', $product_id, PDO::PARAM_INT);
        $stmt->execute();
        $product = $stmt->fetch(PDO::FETCH_ASSOC);

        if ($product) {
            $check_query = "SELECT id, quantity FROM cart_items WHERE user_id = :user_id AND product_id = :product_id";
            $check_stmt = $pdo->prepare($check_query);
            $check_stmt->execute(['user_id' => $user_id, 'product_id' => $product_id]);
            $cart_item = $check_stmt->fetch(PDO::FETCH_ASSOC);

            if ($cart_item) {
                $new_quantity = $cart_item['quantity'] + $quantity;
                $update_query = "UPDATE cart_items SET quantity = :quantity WHERE id = :id";
                $update_stmt = $pdo->prepare($update_query);
                $update_stmt->execute(['quantity' => $new_quantity, 'id' => $cart_item['id']]);
            } else {
                $insert_query = "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (:user_id, :product_id, :quantity)";
                $insert_stmt = $pdo->prepare($insert_query);
                $insert_stmt->execute(['user_id' => $user_id, 'product_id' => $product_id, 'quantity' => $quantity]);
            }
            header("Location: cart.php");
            exit;
        } else {
            echo '<p>Sản phẩm không tồn tại.</p>';
        }
    } catch (PDOException $e) {
        echo '<p>Lỗi: ' . $e->getMessage() . '</p>';
    }
}

// Lấy thông tin sản phẩm để hiển thị
try {
    $query = "SELECT * FROM products WHERE id = :id";
    $stmt = $pdo->prepare($query);
    $stmt->bindParam(':id', $product_id, PDO::PARAM_INT);
    $stmt->execute();
    $product = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$product) {
        die("Sản phẩm không tồn tại.");
    }
} catch (PDOException $e) {
    echo '<p>Lỗi: ' . $e->getMessage() . '</p>';
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($product['name']); ?> - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css?v=1" />
    <style>
        .main-image {
            position: relative;
            width: 100%;
            text-align: center;
            padding: 20px 0;
        }
        .main-image img {
            width: auto;
            height: auto;
            max-width: 100%;
            max-height: 400px;
            object-fit: contain;
            display: block;
            margin: 0 auto;
            image-rendering: -webkit-optimize-contrast;
            image-rendering: crisp-edges;
        }
        .qr-code {
            text-align: center;
            margin-top: 20px;
        }
        .error-message {
            color: #ff4d4d;
            text-align: center;
            margin-top: 10px;
            font-size: 16px;
        }
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            z-index: 1000;
            transition: opacity 0.3s ease-in-out;
        }
        .modal-content {
            background-color: #fff;
            margin: 5% auto;
            padding: 40px;
            border-radius: 12px;
            width: 90%;
            max-width: 700px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            text-align: center;
            position: relative;
        }
        .modal-content h2 {
            font-size: 28px;
            font-weight: 500;
            color: #333;
            margin-bottom: 30px;
        }
        .modal-content img {
            max-width: 350px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background-color: #f9f9f9;
        }
        .close {
            position: absolute;
            top: 15px;
            right: 20px;
            color: #666;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            transition: color 0.2s ease;
        }
        .close:hover,
        .close:focus {
            color: #000;
        }
        .modal-footer {
            margin-top: 25px;
            font-size: 16px;
            color: #666;
        }
        .modal-actions {
            margin-top: 30px;
            display: flex;
            justify-content: center;
            gap: 20px;
        }
        .modal-actions button {
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }
        .modal-actions .confirm-btn {
            background-color: #007bff;
            color: white;
        }
        .modal-actions .confirm-btn:hover {
            background-color: #0056b3;
        }
        .modal-actions .cancel-btn {
            background-color: #f44336;
            color: white;
        }
        .modal-actions .cancel-btn:hover {
            background-color: #c62828;
        }
    </style>
</head>
<body>
    <?php include '../includes/header.php'; ?>

    <section class="product-detail-page">
        <div class="container">
            <div class="product-gallery">
                <div class="main-image">
                    <img src="<?php echo htmlspecialchars($product['image']); ?>" alt="<?php echo htmlspecialchars($product['name']); ?>">
                </div>
            </div>
            <div class="product-info">
                <h1><?php echo htmlspecialchars($product['name']); ?></h1>
                <div class="rating">
                    ★★★★★ <span>(Đánh giá | 100)</span>
                </div>
                <div class="price">
                    <span class="current-price"><?php echo htmlspecialchars($product['price']); ?></span>
                    
                </div>
                <div class="options">
                    <div class="option">
                        <label>Dung lượng:</label>
                        <select name="capacity">
                            <option>128GB</option>
                            <option>256GB</option>
                            <option>512GB</option>
                        </select>
                    </div>
                    <div class="option">
                        <label>Màu sắc:</label>
                        <div class="color-options">
                            <span class="color black"></span>
                            <span class="color silver"></span>
                        </div>
                    </div>
                </div>
                <div class="shipping-info">
                    <p><strong>Ưu đãi:</strong> (Ưu đãi đến ngày 25/03/2025)</p>
                    <ul>
                        <li><span class="check">✔</span> Giảm ngay 400.000đ khi thanh toán qua ZaloPay/SL co hạn</li>
                        <li><span class="check">✔</span> Tặng ngay Sony mua kèm giảm 15% (đến 1.000.000đ)</li>
                        <li><span class="check">✔</span> Mua combo với Non Apple giảm 200.000đ</li>
                        <li><span class="error">✖</span> Ưu đãi không áp dụng cho đơn hàng đã hoàn thành</li>
                    </ul>
                </div>
                <div class="actions">
                    <form id="buy-form" method="POST" action="">
                        <input type="hidden" name="product_id" value="<?php echo $product_id; ?>">
                        <input type="number" name="quantity" value="1" min="1" style="width: 60px; padding: 5px; margin-right: 10px;">
                        <button type="submit" name="buy_now" class="buy-btn">MUA NGAY</button>
                        <button type="submit" name="add_to_cart" class="cart-btn">Thêm vào giỏ</button>
                    </form>
                </div>
                <div class="payment-options">
                    <p>Trả góp 0% qua thẻ Visa, Mastercard, JCB, Amex</p>
                    <p>Thử đổi mới</p>
                </div>
                <div class="additional-info">
                    <p><strong>Bảo hành:</strong> 12 tháng, 1 đổi 1 trong 30 ngày nếu lỗi do NSX</p>
                </div>
            </div>
        </div>

        <div class="product-promo-image">
            <img src="https://shopdunk.com/images/uploaded/gi%C3%A1%20iphone%2016/iPhone_16e_Non-AI_Feb25_Product_Page_L__VN-VI.jpg" alt="iPhone 16e Non-AI Promo">
        </div>
    </section>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

    <!-- Modal -->
    <div id="qrModal" class="modal">
        <div class="modal-content">
            <span class="close">×</span>
            <h2>Thanh Toán Đơn Hàng</h2>
            <div id="modal-qr-code"></div>
            <div class="modal-footer">
                <p>Quét mã QR bằng ứng dụng MB Bank để thanh toán</p>
            </div>
            <div class="modal-actions">
                <button class="confirm-btn" id="confirm-btn">Xác nhận</button>
                <button class="cancel-btn" id="cancel-btn">Hủy</button>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('buy-form').addEventListener('submit', function(e) {
            if (e.submitter && e.submitter.name === 'buy_now') {
                e.preventDefault();

                const formData = new FormData(this);
                const priceText = '<?php echo htmlspecialchars($product['price']); ?>';
                const price = parseFloat(priceText.replace(/[^0-9]/g, ''));
                const quantity = parseInt(formData.get('quantity'));
                const productId = parseInt(formData.get('product_id'));
                const amount = price * quantity;

                formData.append('amount', amount);

                fetch('http://localhost:4001/generate-qr', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        response.text().then(text => console.log('Server response:', text));
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const modal = document.getElementById('qrModal');
                    const modalQrCode = document.getElementById('modal-qr-code');
                    modalQrCode.innerHTML = '';
                    if (data.success) {
                        modalQrCode.innerHTML = '<img src="' + data.qr_code + '" alt="QR Code">';
                        modal.style.display = 'block';
                        modal.dataset.orderId = data.order_id; // Lưu order_id
                    } else {
                        modalQrCode.innerHTML = '<p class="error-message">' + data.message + '</p>';
                        modal.style.display = 'block';
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    const modalQrCode = document.getElementById('modal-qr-code');
                    modalQrCode.innerHTML = '<p class="error-message">Lỗi kết nối: ' + error.message + '</p>';
                    document.getElementById('qrModal').style.display = 'block';
                });
            }
        });

        // Xử lý nút "Xác nhận"
        document.getElementById('confirm-btn').addEventListener('click', function() {
            const modal = document.getElementById('qrModal');
            const orderId = modal.dataset.orderId;

            if (!orderId) {
                alert('Không tìm thấy mã đơn hàng!');
                return;
            }

            fetch(`http://localhost:4001/check-payment/${orderId}`)
            .then(response => {
                if (!response.ok) {
                    response.text().then(text => console.log('Server response:', text));
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('Thanh toán đã được xác nhận!');
                    modal.style.display = 'none';

                    // Gửi email xác nhận qua FastAPI
                    const emailFormData = new FormData();
                    emailFormData.append('email_receiver', '<?php echo $user_email; ?>');
                    const cartItems = [{
                        'id': <?php echo $product_id; ?>,
                        'name': '<?php echo htmlspecialchars($product['name']); ?>',
                        'price': <?php echo (int)str_replace(['VND', '.', ','], '', $product['price']); ?>,
                        'quantity': parseInt(document.querySelector('input[name="quantity"]').value),
                        'image': '<?php echo htmlspecialchars($product['image']); ?>'
                    }];
                    const total = <?php echo (int)str_replace(['VND', '.', ','], '', $product['price']); ?> * parseInt(document.querySelector('input[name="quantity"]').value);
                    emailFormData.append('cart_items', JSON.stringify(cartItems));
                    emailFormData.append('total', total);

                    // Debug dữ liệu gửi đi
                    let debugString = '';
                    for (let [key, value] of emailFormData.entries()) {
                        debugString += `${key}: ${value}\n`;
                    }
                    console.log('FormData content:\n', debugString);
                    alert('Dữ liệu gửi đi:\n' + debugString);

                    fetch('http://localhost:4010/send-email', {
                        method: 'POST',
                        body: emailFormData
                    })
                    .then(response => {
                        if (!response.ok) {
                            return response.text().then(text => {
                                throw new Error(`HTTP error! Status: ${response.status}, Response: ${text}`);
                            });
                        }
                        return response.json();
                    })
                    .then(emailData => {
                        if (emailData.success) {
                            console.log('Email sent successfully:', emailData.message);
                            alert('Email xác nhận đã được gửi thành công!');
                        } else {
                            console.error('Email sending failed:', emailData.message);
                            alert('Gửi email thất bại: ' + emailData.message);
                        }
                    })
                    .catch(error => {
                        console.error('Email error:', error);
                        alert('Lỗi khi gửi email: ' + error.message);
                    });

                } else {
                    alert('Chưa nhận được thanh toán phù hợp: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Check payment error:', error);
                alert('Lỗi khi kiểm tra thanh toán: ' + error.message);
            });
        });

        // Đóng modal
        document.querySelector('.close').addEventListener('click', function() {
            document.getElementById('qrModal').style.display = 'none';
        });

        document.getElementById('cancel-btn').addEventListener('click', function() {
            document.getElementById('qrModal').style.display = 'none';
        });
    </script>
</body>
</html>