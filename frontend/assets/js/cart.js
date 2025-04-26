fetch('../../backend/views/cart.php')
    .then(response => response.json())
    .then(data => {
        const cartItems = data.cart_items;
        const total = data.total;
        const userEmail = data.user_email;

        const cartCount = document.getElementById('cart-count');
        const cartContent = document.getElementById('cart-content');
        const cartItemsDiv = document.getElementById('cart-items');
        const emptyCart = document.getElementById('empty-cart');
        const subtotalSpan = document.getElementById('subtotal');
        const totalSpan = document.getElementById('total');

        if (cartItems.length > 0) {
            cartCount.textContent = `Bạn có ${cartItems.length} sản phẩm trong giỏ.`;
            cartContent.style.display = 'flex';
            emptyCart.style.display = 'none';

            cartItems.forEach(item => {
                const subtotal = item.price * item.quantity;
                const itemDiv = document.createElement('div');
                itemDiv.className = 'cart-item';
                itemDiv.innerHTML = `
                    <img src="${item.image}" alt="${item.name}">
                    <div class="item-details">
                        <h3>${item.name}</h3>
                        <p class="price">${item.price.toLocaleString('vi-VN')} VNĐ</p>
                        <div class="quantity">
                            <button class="qty-btn minus" data-id="${item.id}">-</button>
                            <input type="number" value="${item.quantity}" min="1" data-id="${item.id}">
                            <button class="qty-btn plus" data-id="${item.id}">+</button>
                        </div>
                    </div>
                    <div class="item-subtotal">${subtotal.toLocaleString('vi-VN')} VNĐ</div>
                    <a href="../../backend/views/remove_from_cart.php?id=${item.id}" class="remove-btn">Xóa</a>
                `;
                cartItemsDiv.appendChild(itemDiv);
            });

            subtotalSpan.textContent = `${total.toLocaleString('vi-VN')} VNĐ`;
            totalSpan.textContent = `${total.toLocaleString('vi-VN')} VNĐ`;
        } else {
            cartCount.textContent = 'Giỏ hàng của bạn đang trống.';
            cartContent.style.display = 'none';
            emptyCart.style.display = 'block';
        }

        // Xử lý nút tăng/giảm số lượng
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
               
                fetch('../../../backend/views/update_cart.php', {
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

        // Xử lý nút thanh toán
        document.getElementById('checkout-btn').addEventListener('click', function(e) {
            e.preventDefault();
        
            const productIds = cartItems.map(item => item.id);
            const quantities = cartItems.map(item => item.quantity);
        
            const items = productIds.map((id, index) => ({
                product_id: id,
                quantity: quantities[index]
            }));
        
            const formData = new FormData();
            formData.append('items', JSON.stringify(items));
            formData.append('amount', total);
        
            fetch('http://localhost:4090/generate-qr-cart', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                const modal = document.getElementById('qrModal');
                const modalQrCode = document.getElementById('modal-qr-code');
                modalQrCode.innerHTML = '';
                if (data.success) {
                    modalQrCode.innerHTML = `<img src="${data.qr_code}" alt="QR Code">`;
                    modal.style.display = 'block';
                    modal.dataset.orderId = data.order_id;
                } else {
                    modalQrCode.innerHTML = `<p class="error-message">${data.message}</p>`;
                    modal.style.display = 'block';
                }
            });
        });
        
        document.getElementById('confirm-btn').addEventListener('click', function() {
            const modal = document.getElementById('qrModal');
            const orderId = modal.dataset.orderId;
        
            if (!orderId) {
                alert('Không tìm thấy mã đơn hàng!');
                return;
            }
        
            // Thêm user_email vào yêu cầu
            fetch(`http://localhost:4090/check-payment/${orderId}?user_email=${encodeURIComponent(userEmail)}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('Thanh toán đã được xác nhận! Đơn hàng đã được lưu.');
                    modal.style.display = 'none';
        
                    // Gửi email thông báo
                    const emailFormData = new FormData();
                    emailFormData.append('email_receiver', userEmail);
                    emailFormData.append('cart_items', JSON.stringify(cartItems));
                    emailFormData.append('total', total);
        
                    fetch('http://localhost:4090/send-email-notification', {
                        method: 'POST',
                        body: emailFormData
                    })
                    .then(response => {
                        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                        return response.json();
                    })
                    .then(emailData => {
                        if (emailData.success) {
                            alert('Email xác nhận đã được gửi thành công!');
                            // Xóa giỏ hàng
                            fetch('../../backend/views/clear_cart.php', {
                                method: 'POST'
                            }).then(() => location.reload());
                        } else {
                            alert('Gửi email thất bại: ' + emailData.message);
                        }
                    })
                    .catch(error => {
                        alert('Lỗi khi gửi email: ' + error.message);
                    });
                } else {
                    alert('Chưa nhận được thanh toán phù hợp: ' + data.message);
                }
            })
            .catch(error => {
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
    });