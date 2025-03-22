<?php
session_start();
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Liên hệ - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
    <style>
        footer {
            position: fixed;
        }
        .success-message {
            color: green;
            margin-bottom: 15px;
        }
        .error-message {
            color: red;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <?php include '../includes/header.php'; ?>

    <section class="contact-page">
        <div class="contact-header">
            <h1>Liên hệ với chúng tôi</h1>
            <p>Có thắc mắc? Hãy gửi thông tin cho chúng tôi, chúng tôi sẽ hỗ trợ bạn sớm nhất.</p>
        </div>

        <div class="contact-content">
            <div class="contact-form">
                <div id="form-message"></div> <!-- Nơi hiển thị thông báo -->

                <form id="contact-form" method="POST" action="http://127.0.0.1:5000/send-email">
                    <div class="form-group">
                        <label for="name">Họ và tên</label>
                        <input type="text" id="name" name="name" placeholder="Nhập họ và tên" required>
                    </div>
                    <div class="form-group">
                        <label for="email">Email</label>
                        <input type="email" id="email" name="email" placeholder="Nhập email" required>
                    </div>
                    <div class="form-group">
                        <label for="phone">Số điện thoại</label>
                        <input type="tel" id="phone" name="phone" placeholder="Nhập số điện thoại" required>
                    </div>
                    <div class="form-group">
                        <label for="message">Tin nhắn</label>
                        <textarea id="message" name="message" placeholder="Nhập tin nhắn của bạn" rows="5" required></textarea>
                    </div>
                    <button type="submit" class="submit-btn">Gửi tin nhắn</button>
                </form>
            </div>

            <div class="contact-info">
                <h3>Thông tin liên hệ</h3>
                <p><strong>Địa chỉ:</strong> 96A Trần Phú, Hà Đông, Hà Nội</p>
                <p><strong>Email:</strong> k100iltqbao@gmail.com</p>
                <p><strong>Số điện thoại:</strong> 0988888888</p>
                <p><strong>Giờ làm việc:</strong> 9:00 - 18:00, Thứ 2 - Thứ 7</p>
            </div>
        </div>
    </section>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

    <script>
        document.getElementById('contact-form').addEventListener('submit', function(e) {
            e.preventDefault(); // Ngăn form submit mặc định

            const formData = new FormData(this);

            fetch('http://localhost:5000/send-email', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                const messageDiv = document.getElementById('form-message');
                messageDiv.innerHTML = '';
                if (data.success) {
                    messageDiv.innerHTML = '<p class="success-message">' + data.message + '</p>';
                    document.getElementById('contact-form').reset(); // Xóa form sau khi gửi thành công
                } else {
                    messageDiv.innerHTML = '<p class="error-message">' + data.message + '</p>';
                }
            })
            .catch(error => {
                document.getElementById('form-message').innerHTML = '<p class="error-message">Có lỗi xảy ra: ' + error + '</p>';
            });
        });
    </script>
</body>
</html>