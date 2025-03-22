<?php
session_start();

// Kiểm tra xem người dùng đã đăng nhập chưa
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
    <link rel="stylesheet" type="text/css" href="../assets/css/chatbot.css" />
    <style>
        body {
            margin: 0;
            background: linear-gradient(135deg, #f5f5f7, #e5e5ea); /* Nền gradient nhẹ */
            font-family: 'SF Pro Display', sans-serif;
        }
        footer {
            position: fixed;
            bottom: 0;
            width: 100%;
            background-color: #333;
            color: white;
            text-align: center;
            padding: 10px 0;
        }
        .chatbot-section {
            padding: 40px 20px;
            min-height: calc(100vh - 120px);
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .chatbot-wrapper {
            display: flex;
            gap: 20px;
            max-width: 1200px;
            width: 100%;
            align-items: stretch;
        }
        .chatbot-container {
            flex: 2;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.08);
            overflow: hidden;
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        .chatbot-header {
            background: linear-gradient(135deg, #007aff, #005bb5);
            color: white;
            padding: 20px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }
        .chatbot-header h2 {
            font-family: 'SF Pro Display', sans-serif;
            font-size: 22px;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
        }
        .chatbot-header .chatbot-icon {
            width: 24px;
            height: 24px;
        }
        .chatbot-header .close-btn {
            color: white;
            text-decoration: none;
            font-size: 28px;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .chatbot-header .close-btn:hover {
            transform: rotate(90deg);
        }
        .chatbox {
            height: 500px;
            overflow-y: auto;
            padding: 30px;
            background: transparent;
            display: flex; /* Sử dụng flex để căn chỉnh tin nhắn */
            flex-direction: column; /* Tin nhắn xếp theo cột */
            gap: 15px; /* Khoảng cách giữa các tin nhắn */
        }
        .message {
            margin: 0; /* Bỏ margin mặc định, dùng gap của flex thay thế */
            padding: 12px 20px;
            border-radius: 18px;
            max-width: 70%;
            font-family: 'SF Pro Display', sans-serif;
            font-size: 15px;
            line-height: 1.5;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05);
            transition: transform 0.3s ease;
            align-self: flex-start; /* Mặc định bên trái (cho bot) */
            display: inline-block; /* Ôm sát nội dung */
            white-space: pre-wrap; /* Giữ định dạng xuống dòng */
        }
        .message.bot {
            background: #e5e5ea;
            align-self: flex-start;
        }
        .message.user {
            background: linear-gradient(135deg, #007aff, #005bb5);
            color: white;
            align-self: flex-end; /* Đẩy sang bên phải */
        }
        .message:hover {
            transform: translateY(-3px);
        }
        .welcome-message {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #007aff, #005bb5);
            color: white;
            border-radius: 18px;
            font-size: 15px;
            line-height: 1.5;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05);
            align-self: center; /* Căn giữa */
            max-width: 80%;
        }
        .welcome-message button {
            padding: 8px 15px;
            font-size: 14px;
            background-color: #fff;
            color: #007aff;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            margin-left: 10px;
            transition: background-color 0.3s;
        }
        .welcome-message button:hover {
            background-color: #e5e5ea;
        }
        .chat-input {
            display: flex;
            padding: 15px 20px;
            background: rgba(255, 255, 255, 0.9);
            border-top: 1px solid rgba(229, 229, 234, 0.5);
        }
        .chat-input input {
            flex: 1;
            padding: 12px 20px;
            border: 1px solid #e5e5ea;
            border-radius: 20px 0 0 20px;
            outline: none;
            font-family: 'SF Pro Display', sans-serif;
            font-size: 15px;
            background: #f9f9f9;
            transition: all 0.3s ease;
        }
        .chat-input input:focus {
            border-color: #007aff;
            background: #fff;
            box-shadow: 0 0 10px rgba(0, 122, 255, 0.1);
        }
        .chat-input button {
            padding: 12px 25px;
            border: none;
            background: linear-gradient(135deg, #007aff, #005bb5);
            color: white;
            border-radius: 0 20px 20px 0;
            cursor: pointer;
            font-family: 'SF Pro Display', sans-serif;
            font-size: 15px;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: all 0.3s ease;
        }
        .chat-input button:hover {
            background: linear-gradient(135deg, #005bb5, #003f87);
            box-shadow: 0 5px 15px rgba(0, 122, 255, 0.3);
        }
        .chatbot-tips {
            flex: 1;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.08);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .chatbot-tips h3 {
            font-family: 'SF Pro Display', sans-serif;
            font-size: 18px;
            margin: 0;
            color: #000;
            background: linear-gradient(135deg, #007aff, #005bb5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .chatbot-tips p {
            font-family: 'SF Pro Display', sans-serif;
            font-size: 14px;
            color: #6e6e73;
            margin: 0;
        }
        .chatbot-tips .tip-btn {
            padding: 8px 15px;
            background: linear-gradient(135deg, #007aff, #005bb5);
            color: white;
            border-radius: 15px;
            text-decoration: none;
            font-family: 'SF Pro Display', sans-serif;
            font-size: 14px;
            transition: all 0.3s ease;
            text-align: center;
            cursor: pointer;
        }
        .chatbot-tips .tip-btn:hover {
            background: linear-gradient(135deg, #005bb5, #003f87);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 122, 255, 0.3);
        }
        @media (max-width: 768px) {
            .chatbot-wrapper {
                flex-direction: column;
            }
            .chatbot-container, .chatbot-tips {
                width: 100%;
            }
            .chatbox {
                height: 400px; /* Tăng chiều cao trên mobile */
            }
        }

        /* CSS cho modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-content {
            background: white;
            border-radius: 20px;
            width: 90%;
            max-width: 600px;
            padding: 30px;
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.2);
            position: relative;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { transform: translateY(-50px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        .modal-content h3 {
            font-family: 'SF Pro Display', sans-serif;
            font-size: 24px;
            margin: 0 0 20px;
            color: #000;
            background: linear-gradient(135deg, #007aff, #005bb5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .modal-content .close-modal {
            position: absolute;
            top: 15px;
            right: 15px;
            font-size: 28px;
            color: #6e6e73;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .modal-content .close-modal:hover {
            transform: rotate(90deg);
            color: #007aff;
        }
        .modal-content ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .modal-content ul li {
            font-family: 'SF Pro Display', sans-serif;
            font-size: 15px;
            color: #333;
            margin-bottom: 15px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }
        .modal-content ul li::before {
            content: '✨';
            font-size: 16px;
        }
        .modal-content p {
            font-family: 'SF Pro Display', sans-serif;
            font-size: 14px;
            color: #6e6e73;
            margin: 15px 0 0;
        }

        /* CSS cho tin nhắn chứa mã QR */
        .message.qr-message {
            background: #e5e5ea;
            align-self: flex-start;
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding: 20px;
        }
        .message.qr-message img {
            max-width: 200px;
            border-radius: 10px;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
        }
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
                    <input type="text" id="user-input" placeholder="Nhập tin nhắn (Ví dụ: Tôi muốn mua iPhone 16 Pro Max 256GB)">
                    <button onclick="sendMessage()">Gửi <span>➤</span></button>
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

    <script>
        // Hàm gửi tin nhắn
        async function sendMessage() {
            const userInput = document.getElementById('user-input');
            const chatbox = document.getElementById('chatbox');
            const query = userInput.value.trim();

            // Kiểm tra nếu input rỗng thì không làm gì
            if (!query) return;

            // Thêm câu hỏi của người dùng vào chatbox
            const userMessage = document.createElement('div');
            userMessage.className = 'message user';
            userMessage.textContent = query;
            chatbox.appendChild(userMessage);

            // Xóa input sau khi gửi
            userInput.value = '';

            // Cuộn xuống tin nhắn mới nhất
            chatbox.scrollTop = chatbox.scrollHeight;

            try {
                // Gửi request POST đến FastAPI
                const response = await fetch('http://localhost:5002/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: query }),
                });

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }

                const data = await response.json();
                const botReply = data.response;
                const isPurchase = data.is_purchase;
                const qrCode = data.qr_code;

                // Thêm câu trả lời của bot vào chatbox
                const botMessage = document.createElement('div');
                if (isPurchase && qrCode) {
                    // Nếu là yêu cầu mua hàng, hiển thị mã QR
                    botMessage.className = 'message qr-message';
                    botMessage.innerHTML = `
                        <span>${botReply}</span>
                        <img src="${qrCode}" alt="Mã QR thanh toán" />
                    `;
                } else {
                    // Nếu không phải mua hàng, hiển thị tin nhắn bình thường
                    botMessage.className = 'message bot';
                    botMessage.textContent = botReply;
                }
                chatbox.appendChild(botMessage);

                // Cuộn xuống tin nhắn mới nhất
                chatbox.scrollTop = chatbox.scrollHeight;
            } catch (error) {
                console.error('Error:', error);
                const errorMessage = document.createElement('div');
                errorMessage.className = 'message bot';
                errorMessage.textContent = 'Đã có lỗi xảy ra. Vui lòng thử lại sau!';
                chatbox.appendChild(errorMessage);

                // Cuộn xuống tin nhắn mới nhất
                chatbox.scrollTop = chatbox.scrollHeight;
            }
        }

        // Gửi tin nhắn khi nhấn Enter
        document.getElementById('user-input').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Hàm bắt đầu chat
        function startChat() {
            const chatbox = document.getElementById('chatbox');
            const welcomeMsg = document.querySelector('.welcome-message');
            const botMessage = document.createElement('div');
            botMessage.className = 'message bot';
            botMessage.textContent = 'Xin chào bạn, mình là Apple Intelligence, mình có thể giúp gì cho bạn không?';
            chatbox.replaceChild(botMessage, welcomeMsg); // Thay thế welcome message bằng tin nhắn bot
            chatbox.scrollTop = chatbox.scrollHeight;
        }

        // Hàm hiển thị modal mẹo
        function showTipsModal() {
            const modal = document.getElementById('tipsModal');
            modal.style.display = 'flex';
        }

        // Hàm đóng modal
        function closeTipsModal() {
            const modal = document.getElementById('tipsModal');
            modal.style.display = 'none';
        }

        // Đóng modal khi nhấn ra ngoài nội dung
        window.onclick = function(event) {
            const modal = document.getElementById('tipsModal');
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        };
    </script>
</body>
</html>