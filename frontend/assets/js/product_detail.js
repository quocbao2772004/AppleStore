const urlParams = new URLSearchParams(window.location.search);
const productId = urlParams.get('id');

let userEmail = '';
let cartItems = [];
let total = 0;

fetch(`../../backend/views/product_detail.php?id=${productId}`)
    .then(response => {
        if (!response.ok) throw new Error(response.statusText);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const product = data.product;
            userEmail = data.user_email;

            document.getElementById('product-title').textContent = `${product.name} - Apple Store`;
            document.getElementById('product-image').src = product.image;
            document.getElementById('product-image').alt = product.name;
            document.getElementById('product-name').textContent = product.name;
            document.getElementById('product-price').textContent = product.price;
            document.getElementById('product-id').value = product.id;

            cartItems = [{
                id: product.id,
                name: product.name,
                price: parseFloat(product.price.replace(/[^0-9]/g, '')),
                quantity: 1,
                image: product.image
            }];
        } else {
            document.body.innerHTML = `<p>${data.error}</p>`;
        }
    })
    .catch(error => {
        document.body.innerHTML = `<p>Lỗi: ${error.message}</p>`;
    });

document.getElementById('buy-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const isBuyNow = e.submitter.name === 'buy_now';

    const quantity = parseInt(formData.get('quantity'));
    cartItems[0].quantity = quantity;
    total = cartItems[0].price * quantity;

    if (isBuyNow) {
        const priceText = document.getElementById('product-price').textContent;
        const price = parseFloat(priceText.replace(/[^0-9]/g, ''));
        const amount = price * quantity;
        formData.append('amount', amount);

        fetch('http://localhost:4090/generate-qr', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            return response.json();
        })
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
        })
        .catch(error => {
            const modalQrCode = document.getElementById('modal-qr-code');
            modalQrCode.innerHTML = `<p class="error-message">Lỗi kết nối: ${error.message}</p>`;
            document.getElementById('qrModal').style.display = 'block';
        });
    } else {
        formData.append('add_to_cart', 'true'); // Thêm flag để backend biết là thêm vào giỏ
        fetch(`../../backend/views/product_detail.php?id=${productId}`, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.success && data.redirect) {
                window.location.href = data.redirect;
            } else {
                alert(data.error || 'Lỗi không xác định khi thêm vào giỏ hàng.');
            }
        })
        .catch(error => {
            alert('Lỗi kết nối tới server: ' + error.message);
        });
    }
});

document.getElementById('confirm-btn').addEventListener('click', function() {
    const modal = document.getElementById('qrModal');
    const orderId = modal.dataset.orderId;

    if (!orderId) {
        alert('Không tìm thấy mã đơn hàng!');
        return;
    }

    fetch(`http://localhost:4090/check-payment/${orderId}`)
    .then(response => {
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('Thanh toán đã được xác nhận!');
            modal.style.display = 'none';

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
                    alert('Email đã được gửi thành công!');
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

document.querySelector('.close').addEventListener('click', function() {
    document.getElementById('qrModal').style.display = 'none';
});

document.getElementById('cancel-btn').addEventListener('click', function() {
    document.getElementById('qrModal').style.display = 'none';
});