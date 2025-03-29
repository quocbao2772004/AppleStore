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
        const response = await fetch('http://localhost:4090/ask', {
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