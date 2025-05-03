<?php
session_start();


if (!isset($_SESSION['user_id'])) {
    header("Location: login.php");
    exit();
}
?>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trợ lý ảo - Apple Store</title>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
    <!-- <link rel="stylesheet" type="text/css" href="../assets/css/chatbot.css" /> -->
    <link rel="stylesheet" type="text/css" href="../assets/css/chatbott.css" />
    <style>
        
    </style>
</head>
<body>
    <?php include '../includes/header.php'; ?>

    <section class="chatbot-section">
        <div class="chatbot-wrapper">
            <div class="chatbot-container">
                <div class="chatbot-header">
                    <h2>
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" class="bi bi-robot chatbot-icon" viewBox="0 0 16 16">
                            <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.6 26.6 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.93.93 0 0 1-.765.935c-.845.147-2.34.346-4.235.346s-3.39-.2-4.235-.346A.93.93 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a25 25 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25 25 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135"/>
                            <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 1 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5"/>
                        </svg>
                        Trợ lý ảo Apple Store
                    </h2>
                    <a href="../index.php" class="close-btn">×</a>
                </div>
                <div class="chatbox" id="chatbox">
                    <div class="welcome-message">
                        Xin chào! Tôi là trợ lý ảo của Apple Store. Bạn cần giúp gì hôm nay?
                        <button onclick="startChat()">xin chào</button>
                    </div>
                </div>
                <div class="chat-input">
                <div class="chat-input">
                    <input type="text" id="user-input" placeholder="Nhập tin nhắn (Ví dụ: Tôi muốn mua iPhone 16 Pro Max 256GB)">
                    <label for="image-upload" class="image-upload-btn">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" class="bi bi-image" viewBox="0 0 16 16">
                            <path d="M6.002 5.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z"/>
                            <path d="M2.002 1a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V3a2 2 0 0 0-2-2h-12zm12 1a1 1 0 0 1 1 1v6.5l-3.777-1.947a.5.5 0 0 0-.577.093l-3.71 3.71-2.66-1.772a.5.5 0 0 0-.63.062L1.002 12V3a1 1 0 0 1 1-1h12z"/>
                        </svg>
                    </label>
                    <input type="file" id="image-upload" accept="image/*" style="display: none;">
                    <button onclick="sendMessage()">Gửi <span>➤</span></button>
                </div>
                </div>
            </div>
            <div class="chatbot-tips">
                <h3>Tổng quan trợ lý ảo</h3>
                <p>Trợ lý ảo Apple Store giúp bạn tìm kiếm sản phẩm, giải đáp thắc mắc và hỗ trợ mua sắm nhanh chóng.</p>
                <div class="tip-btn" onclick="showTipsModal()">Mẹo trợ lý ảo</div>
            </div>
        </div>
    </section>

    <!-- Modal hiển thị mẹo -->
    <div class="modal" id="tipsModal">
        <div class="modal-content">
            <span class="close-modal" onclick="closeTipsModal()">×</span>
            <h3>Mẹo sử dụng trợ lý ảo Apple Store</h3>
            <ul>
                <li>Đặt câu hỏi cụ thể để nhận câu trả lời chính xác. Ví dụ: "Giá iPhone 16 Pro Max là bao nhiêu?" thay vì chỉ hỏi "Giá iPhone".</li>
                <li>Hỏi về sản phẩm tốt nhất bằng cách sử dụng từ khóa như "dùng tốt" hoặc "tốt nhất". Mình sẽ dựa vào đánh giá trung bình để trả lời!</li>
                <li>Mình có thể giúp bạn kiểm tra giá, thông tin sản phẩm, hoặc thậm chí cung cấp thông tin liên hệ của cửa hàng. Chỉ cần hỏi nhé!</li>
                <li>Nếu không tìm thấy sản phẩm, mình sẽ gợi ý bạn liên hệ qua email hoặc số điện thoại của Apple Store để được hỗ trợ thêm.</li>
                <li>Thử hỏi về các mẹo mua sắm! Ví dụ: "Mẹo mua iPhone giá tốt?" – Mình sẽ chia sẻ kinh nghiệm hữu ích cho bạn.</li>
            </ul>
            <p>Chúc bạn có trải nghiệm tuyệt vời với Apple Store! 🎉</p>
        </div>
    </div>

    <footer>
        <p>© 2025 Apple Store - Mọi quyền được bảo lưu.</p>
    </footer>

    <script src = "../assets/js/chatbot.js"></script>
</body>
</html>