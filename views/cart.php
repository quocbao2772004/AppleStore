<?php
session_start();
include '../config/fetch_product.php';

// Kiểm tra xem người dùng đã đăng nhập chưa
if (!isset($_SESSION['user_id']) || !isset($_SESSION['user_email'])) {
    header("Location: login.php");
    exit();
}
$user_id = $_SESSION['user_id'];
$user_email = $_SESSION['user_email'];

// Lấy tất cả sản phẩm trong giỏ hàng của người dùng từ bảng cart_items
$query = "
    SELECT c.product_id, c.quantity, p.name, p.price, p.image
    FROM cart_items c
    JOIN products p ON c.product_id = p.id
    WHERE c.user_id = :user_id
";
$stmt = $pdo->prepare($query);
$stmt->bindParam(':user_id', $user_id, PDO::PARAM_INT);
$stmt->execute();
$cart_items_db = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Xử lý dữ liệu giỏ hàng
$cart_items = [];
$total = 0;

if ($cart_items_db) {
    foreach ($cart_items_db as $item) {
        $price = (int) str_replace(['VND', '.'], '', $item['price']);
        $subtotal = $price * $item['quantity'];
        $total += $subtotal;

        $cart_items[] = [
            'id' => $item['product_id'],
            'name' => $item['name'],
            'price' => $price,
            'quantity' => $item['quantity'],
            'image' => $item['image']
        ];
    }
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giỏ hàng - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
    <style>
        footer {
            position: fixed;
            bottom: 0;
            width: 100%;
        }
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
        .error-message {
            color: #ff4d4d;
            text-align: center;
            margin-top: 10px;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <?php include '../includes/header.php'; ?>

    <section class="cart-page">
        <div class="cart-header">
            <h1>Giỏ hàng của bạn</h1>
            <p>
                <?php echo count($cart_items) > 0 ? "Bạn có " . count($cart_items) . " sản phẩm trong giỏ." : "Giỏ hàng của bạn đang trống."; ?>
            </p>
        </div>

        <?php if (count($cart_items) > 0): ?>
            <div class="cart-content">
                <div class="cart-items">
                    <?php
                    foreach ($cart_items as $item) {
                        $subtotal = $item['price'] * $item['quantity'];
                        echo '<div class="cart-item">';
                        echo '<img src="' . htmlspecialchars($item['image']) . '" alt="' . htmlspecialchars($item['name']) . '">';
                        echo '<div class="item-details">';
                        echo '<h3>' . htmlspecialchars($item['name']) . '</h3>';
                        echo '<p class="price">' . number_format($item['price'], 0, ',', '.') . ' VNĐ</p>';
                        echo '<div class="quantity">';
                        echo '<button class="qty-btn minus" data-id="' . $item['id'] . '">-</button>';
                        echo '<input type="number" value="' . $item['quantity'] . '" min="1" data-id="' . $item['id'] . '">';
                        echo '<button class="qty-btn plus" data-id="' . $item['id'] . '">+</button>';
                        echo '</div>';
                        echo '</div>';
                        echo '<div class="item-subtotal">' . number_format($subtotal, 0, ',', '.') . ' VNĐ</div>';
                        echo '<a href="remove_from_cart.php?id=' . $item['id'] . '" class="remove-btn">Xóa</a>';
                        echo '</div>';
                    }
                    ?>
                </div>

                <div class="cart-summary">
                    <h3>Tóm tắt đơn hàng</h3>
                    <div class="summary-details">
                        <p>Tổng tiền hàng: <span><?php echo number_format($total, 0, ',', '.') . ' VNĐ'; ?></span></p>
                        <p>Phí vận chuyển: <span>Miễn phí</span></p>
                        <p class="total">Tổng cộng: <span><?php echo number_format($total, 0, ',', '.') . ' VNĐ'; ?></span></p>
                    </div>
                    <button id="checkout-btn" class="checkout-btn">Thanh toán</button>
                </div>
            </div>
        <?php else: ?>
            <div class="empty-cart">
                <p>Chưa có sản phẩm nào trong giỏ hàng.</p>
                <a href="products.php" class="continue-shopping">Tiếp tục mua sắm</a>
            </div>
        <?php endif; ?>
    </section>

    <!-- Modal hiển thị QR -->
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

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

    <script>
        // Xử lý tăng/giảm số lượng
        document.querySelectorAll('.qty-btn').forEach(button => {
            button.addEventListener('click', function() {
                const productId = this.getAttribute('data-id');
                const input = this.parentElement.querySelector('input');
                let quantity = parseInt(input.value);

                if (this.classList.contains('minus') && quantity > 1) {
                    quantity--;
                } else if (this.classList.contains('plus')) {
                    quantity++;
                }

                input.value = quantity;

                fetch('update_cart.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `product_id=${productId}&quantity=${quantity}`
                }).then(response => response.json())
                  .then(data => {
                      if (data.success) {
                          location.reload();
                      }
                  });
            });
        });

        // Xử lý nút "Thanh toán"
        // Xử lý nút "Thanh toán"
        document.getElementById('checkout-btn').addEventListener('click', function(e) {
            e.preventDefault();

            const totalAmount = <?php echo $total; ?>;
            const productIds = <?php echo json_encode(array_column($cart_items, 'id'), JSON_NUMERIC_CHECK); ?>;
            const quantities = <?php echo json_encode(array_column($cart_items, 'quantity'), JSON_NUMERIC_CHECK); ?>;

    // Tạo mảng các object chứa product_id và quantity
        const items = productIds.map((id, index) => ({
            product_id: id,
            quantity: quantities[index]
        }));
        
        const formData = new FormData();
        formData.append('items', JSON.stringify(items)); // Gửi dưới dạng JSON
        formData.append('amount', totalAmount);

        // Debug FormData
        let debugString = '';
        for (let [key, value] of formData.entries()) {
            debugString += `${key}: ${typeof value}- ${value}\n`;
        }
        console.log('FormData content:\n', debugString);

        fetch('http://localhost:4008/generate-qr', {
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
                modal.dataset.orderId = data.order_id;
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
    });

        // Xử lý nút "Xác nhận" và gửi email
        document.getElementById('confirm-btn').addEventListener('click', function() {
            const modal = document.getElementById('qrModal');
            const orderId = modal.dataset.orderId;
            alert(orderId);           
            if (!orderId) {
                alert('Không tìm thấy mã đơn hàng!');
                return;
            }                                                                                                                                                                                                                               

            fetch(`http://localhost:4008/check-payment/${orderId}`)
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
                    emailFormData.append('cart_items', JSON.stringify(<?php echo json_encode($cart_items); ?>));
                    emailFormData.append('total', <?php echo $total; ?>);
                    console.log("cartitem = ",$cart_items);
                    // Debug FormData
                    let debugString = '';
                    for (let [key, value] of emailFormData.entries()) {
                        debugString += `${key}: ${typeof value} - ${value}\n`;
                    }
                    console.log(debugString);

                    console.log('FormData content:\n', debugString);
                    

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
                            alert('Email đã được gửi thành công!');
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
            document.getElementById('qrModal').style.display = '                                                                                                                                            none';
        });

        document.getElementById('cancel-btn').addEventListener('click', function() {
            document.getElementById('qrModal').style.display = 'none';
        });
    </script>
</body>
</html>