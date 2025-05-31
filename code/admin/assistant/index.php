<?php
require_once '../../includes/functions.php';
require_once '../../includes/auth.php';
require_once '../../config/database.php';

// Kiểm tra người dùng đã đăng nhập và là admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../../login.php');
}

// Lấy thông tin admin
$user_id = $_SESSION['user_id'];
try {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE id = ? AND role = 'admin'");
    $stmt->execute([$user_id]);
    $admin = $stmt->fetch();

    if (!$admin) {
        setFlashMessage('error', 'Không tìm thấy thông tin admin');
        redirect('../../index.php');
    }
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi khi lấy thông tin admin: ' . $e->getMessage());
    redirect('../../index.php');
}

// Tiêu đề trang
$pageTitle = 'Trợ Lý Admin';

// Thêm header
include '../includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Thanh bên -->
        <?php include '../includes/sidebar.php'; ?>
        
        <!-- Nội dung chính -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4 py-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Trợ Lý Ảo</h1>
            </div>
            
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">
                        <i class="fas fa-robot me-2"></i> Trợ Lý Admin
                    </h5>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i> Hãy hỏi tôi bất cứ điều gì về cửa hàng, sản phẩm, đơn hàng hoặc cách sử dụng trang quản trị. Cuộc trò chuyện sẽ không được lưu sau khi tải lại trang.
                    </div>
                    
                    <!-- Khung chat -->
                    <div class="chat-container mb-3" id="chatContainer">
                        <div class="chat-messages" id="chatMessages">
                            <div class="message assistant">
                                <div class="message-content">
                                    <p>Mình là Virtual Octopus, trợ lý của Octopus Store. Bạn cần mình giúp gì hôm nay?</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Ô nhập chat -->
                    <form id="chatForm" class="chat-input-form">
                        <div class="input-group">
                            <input type="text" id="userInput" class="form-control" placeholder="Gõ câu hỏi của bạn..." required>
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-paper-plane"></i> Gửi
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- Câu hỏi nhanh -->
            <div class="card mt-4">
                <div class="card-header bg-light">
                    <h5 class="mb-0">Câu hỏi nhanh</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-4 mb-2">
                            <button class="btn btn-outline-secondary w-100 text-start quick-question" data-question="Làm sao để thêm sản phẩm mới?">
                                <i class="fas fa-question-circle me-2"></i> Làm sao để thêm sản phẩm mới?
                            </button>
                        </div>
                        <div class="col-md-4 mb-2">
                            <button class="btn btn-outline-secondary w-100 text-start quick-question" data-question="Xem đơn hàng gần đây thế nào?">
                                <i class="fas fa-question-circle me-2"></i> Xem đơn hàng gần đây thế nào?
                            </button>
                        </div>
                        <div class="col-md-4 mb-2">
                            <button class="btn btn-outline-secondary w-100 text-start quick-question" data-question="Cập nhật tồn kho sản phẩm ra sao?">
                                <i class="fas fa-question-circle me-2"></i> Cập nhật tồn kho sản phẩm ra sao?
                            </button>
                        </div>
                        <div class="col-md-4 mb-2">
                            <button class="btn btn-outline-secondary w-100 text-start quick-question" data-question="Thêm danh mục mới như thế nào?">
                                <i class="fas fa-question-circle me-2"></i> Thêm danh mục mới như thế nào?
                            </button>
                        </div>
                        <div class="col-md-4 mb-2">
                            <button class="btn btn-outline-secondary w-100 text-start quick-question" data-question="Xử lý hoàn tiền thế nào?">
                                <i class="fas fa-question-circle me-2"></i> Xử lý hoàn tiền thế nào?
                            </button>
                        </div>
                        <div class="col-md-4 mb-2">
                            <button class="btn btn-outline-secondary w-100 text-start quick-question" data-question="Xem thống kê bán hàng ra sao?">
                                <i class="fas fa-question-circle me-2"></i> Xem thống kê bán hàng ra sao?
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<style>
.chat-container {
    height: 400px;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background-color: #f8f9fa;
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 15px;
}

.message {
    display: flex;
    margin-bottom: 15px;
}

.message.user {
    justify-content: flex-end;
}

.message-content {
    max-width: 80%;
    padding: 10px 15px;
    border-radius: 10px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message.assistant .message-content {
    background-color: #f1f0f0;
    color: #333;
}

.message.user .message-content {
    background-color: #007bff;
    color: white;
}

.message-content p {
    margin-bottom: 0;
}

.chat-input-form {
    margin-top: 10px;
}

.typing-indicator {
    display: flex;
    padding: 10px 15px;
    background-color: #f1f0f0;
    border-radius: 10px;
    margin-bottom: 15px;
    width: fit-content;
}

.typing-indicator span {
    height: 8px;
    width: 8px;
    margin: 0 1px;
    background-color: #9E9EA1;
    display: block;
    border-radius: 50%;
    opacity: 0.4;
}

.typing-indicator span:nth-of-type(1) {
    animation: 1s blink infinite 0.3333s;
}

.typing-indicator span:nth-of-type(2) {
    animation: 1s blink infinite 0.6666s;
}

.typing-indicator span:nth-of-type(3) {
    animation: 1s blink infinite 0.9999s;
}

@keyframes blink {
    50% {
        opacity: 1;
    }
}
</style>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatMessages = document.getElementById('chatMessages');
    const quickQuestions = document.querySelectorAll('.quick-question');
    
    // URL endpoint FastAPI
    const API_URL = 'http://localhost:4070/chatadmin';
    
    // Câu trả lời cho câu hỏi nhanh
    const quickAnswers = {
        "Làm sao để thêm sản phẩm mới?": "Để thêm sản phẩm mới, bạn vào mục Sản phẩm > Thêm mới. Điền thông tin như tên, mô tả, giá, số lượng tồn kho, chọn danh mục và tải ảnh sản phẩm lên. Sau đó nhấn Lưu.",
        "Xem đơn hàng gần đây thế nào?": "Bạn vào mục Đơn hàng trong thanh sidebar. Các đơn hàng gần đây sẽ hiển thị ở đầu danh sách. Nhấn vào đơn hàng để xem chi tiết.",
        "Cập nhật tồn kho sản phẩm ra sao?": "Để cập nhật tồn kho, bạn vào Sản phẩm > Tất cả sản phẩm, tìm sản phẩm cần chỉnh, nhấn Sửa. Cập nhật số lượng trong mục Tồn kho và nhấn Lưu.",
        "Thêm danh mục mới như thế nào?": "Để thêm danh mục mới, bạn vào Danh mục > Thêm mới. Nhập tên danh mục, mô tả (nếu có), chọn danh mục cha nếu cần, rồi nhấn Lưu.",
        "Xử lý hoàn tiền thế nào?": "Để xử lý hoàn tiền, bạn vào Đơn hàng, tìm đơn hàng cần hoàn, nhấn Xem. Ở cuối trang chi tiết đơn hàng, có nút Hoàn tiền. Làm theo hướng dẫn để hoàn tất.",
        "Xem thống kê bán hàng ra sao?": "Bạn vào mục Thống kê trong sidebar. Trang này hiển thị tồn kho, sản phẩm bán chạy, biểu đồ doanh thu và nhiều thông tin khác."
    };
    
    // Hàm thêm tin nhắn vào khung chat
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Xử lý markdown đơn giản
        const formattedContent = content
            // Xử lý bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Xử lý italic
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Xử lý danh sách với dấu gạch đầu dòng
            .replace(/- (.*?)(?:\n|$)/g, '<li>$1</li>')
            // Xử lý xuống dòng
            .replace(/\n/g, '<br>');
        
        // Kiểm tra nếu có danh sách, bọc trong <ul>
        let finalContent = formattedContent;
        if (formattedContent.includes('<li>')) {
            finalContent = formattedContent.replace(/(<li>.*?<\/li>)+/g, '<ul>$&</ul>');
        }
        
        messageContent.innerHTML = finalContent;
        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);
        
        // Cuộn xuống dưới cùng
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Hàm hiển thị chỉ báo đang nhập
    function showTypingIndicator() {
        const indicatorDiv = document.createElement('div');
        indicatorDiv.className = 'typing-indicator';
        indicatorDiv.id = 'typingIndicator';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            indicatorDiv.appendChild(dot);
        }
        
        chatMessages.appendChild(indicatorDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Hàm xóa chỉ báo đang nhập
    function removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    // Hàm gửi tin nhắn đến FastAPI và nhận phản hồi
    async function sendToAssistant(question) {
        try {
            showTypingIndicator();
            
            const formData = new FormData();
            formData.append('query', question);
            
            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Không thể kết nối đến server');
            }
            
            const data = await response.json();
            const answer = data.response || 'Có lỗi xảy ra, bạn thử lại nhé!';
            
            removeTypingIndicator();
            addMessage(answer);
            
        } catch (error) {
            removeTypingIndicator();
            addMessage('Mình không thể xử lý yêu cầu, bạn liên lạc qua email k100iltqbao@gmail.com hoặc số 0917947910 nhé!');
        }
    }
    
    // Hàm xử lý câu hỏi
    function handleQuestion(question) {
        // Thêm tin nhắn người dùng vào chat
        addMessage(question, true);
        
        // Kiểm tra nếu là câu hỏi nhanh
        if (quickAnswers[question]) {
            setTimeout(() => {
                addMessage(quickAnswers[question]);
            }, 500); // Giả lập độ trễ nhỏ
        } else {
            // Gửi đến FastAPI cho các câu hỏi khác
            sendToAssistant(question);
        }
    }
    
    // Xử lý khi gửi form
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const question = userInput.value.trim();
        if (question === '') return;
        
        // Xử lý câu hỏi
        handleQuestion(question);
        
        // Xóa nội dung input
        userInput.value = '';
    });
    
    // Xử lý câu hỏi nhanh
    quickQuestions.forEach(button => {
        button.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            handleQuestion(question);
            userInput.focus();
        });
    });
    
    // Focus vào ô input khi tải trang
    userInput.focus();
});
</script>

<?php include '../includes/footer.php'; ?>