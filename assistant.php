<?php
require_once 'includes/functions.php';
require_once 'config/database.php';

// Get user ID from session if user is logged in
$userId = isset($_SESSION['user_id']) ? $_SESSION['user_id'] : null;

// Generate session ID for chat
if (!isset($_SESSION['chat_session_id'])) {
    $_SESSION['chat_session_id'] = uniqid('session_', true);
}

// Page title
$pageTitle = 'Trợ lý ảo';

// Include header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <div class="col-lg-8 mx-auto">
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                    <h1 class="h4 mb-0">
                        <i class="fas fa-robot me-2"></i> Trợ lý mua sắm ảo
                    </h1>
                    <button id="clearHistoryBtn" class="btn btn-light btn-sm">
                        <i class="fas fa-trash me-1"></i> Xóa lịch sử
                    </button>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i> Hãy hỏi tôi bất cứ điều gì về sản phẩm, đơn hàng, vận chuyển, đổi trả hoặc bất kỳ câu hỏi nào khác bạn có thể có.
                    </div>
                    
                    <!-- Chat Container -->
                    <div class="chat-container mb-3" id="chatContainer">
                        <div class="chat-messages" id="chatMessages">
                            <div class="message assistant">
                                <div class="message-avatar">
                                    <i class="fas fa-robot"></i>
                                </div>
                                <div class="message-content">
                                    <p>Xin chào! Tôi là trợ lý mua sắm ảo của bạn. Tôi có thể giúp gì cho bạn hôm nay?</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Chat Input -->
                    <form id="chatForm" class="chat-input-form" enctype="multipart/form-data">
                        <div class="input-group">
                            <input type="text" id="userInput" class="form-control" placeholder="Nhập câu hỏi của bạn tại đây..." required>
                            <button type="submit" class="btn btn-primary">
                                <i class="fas fa-paper-plane"></i> Gửi
                            </button>
                            <input type="file" id="imageInput" accept="image/*" style="display:none">
                            <button type="button" class="btn btn-secondary" id="sendImageBtn" title="Gửi ảnh"><i class="fas fa-image"></i></button>
                        </div>
                        <div id="imagePreviewContainer" style="margin-top:8px; display:none; position:relative; max-width:120px;"></div>
                    </form>
                </div>
            </div>
            
            <!-- Popular Questions -->
            <div class="card mt-4 shadow-sm">
                <div class="card-header bg-light">
                    <h5 class="mb-0">Câu hỏi phổ biến</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6 mb-2">
                            <button class="btn btn-outline-primary w-100 text-start quick-question" data-question="Làm thế nào để theo dõi đơn hàng của tôi?">
                                <i class="fas fa-truck me-2"></i> Làm thế nào để theo dõi đơn hàng của tôi?
                            </button>
                        </div>
                        <div class="col-md-6 mb-2">
                            <button class="btn btn-outline-primary w-100 text-start quick-question" data-question="Chính sách đổi trả của bạn là gì?">
                                <i class="fas fa-undo me-2"></i> Chính sách đổi trả của bạn là gì?
                            </button>
                        </div>
                        <div class="col-md-6 mb-2">
                            <button class="btn btn-outline-primary w-100 text-start quick-question" data-question="Bạn có vận chuyển quốc tế không?">
                                <i class="fas fa-globe me-2"></i> Bạn có vận chuyển quốc tế không?
                            </button>
                        </div>
                        <div class="col-md-6 mb-2">
                            <button class="btn btn-outline-primary w-100 text-start quick-question" data-question="Làm thế nào để đặt lại mật khẩu?">
                                <i class="fas fa-lock me-2"></i> Làm thế nào để đặt lại mật khẩu?
                            </button>
                        </div>
                        <div class="col-md-6 mb-2">
                            <button class="btn btn-outline-primary w-100 text-start quick-question" data-question="Bạn chấp nhận những phương thức thanh toán nào?">
                                <i class="fas fa-credit-card me-2"></i> Bạn chấp nhận những phương thức thanh toán nào?
                            </button>
                        </div>
                        <div class="col-md-6 mb-2">
                            <button class="btn btn-outline-primary w-100 text-start quick-question" data-question="Làm thế nào để liên hệ với bộ phận hỗ trợ khách hàng?">
                                <i class="fas fa-headset me-2"></i> Làm thế nào để liên hệ với bộ phận hỗ trợ khách hàng?
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Help Categories -->
            <div class="card mt-4 shadow-sm">
                <div class="card-header bg-light">
                    <h5 class="mb-0">Danh mục trợ giúp</h5>
                </div>
                <div class="card-body">
                    <div class="row text-center">
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="orders">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-shopping-bag"></i>
                                </div>
                                <h6>Đơn hàng</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="shipping">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-truck"></i>
                                </div>
                                <h6>Vận chuyển</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="returns">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-undo"></i>
                                </div>
                                <h6>Đổi trả</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="account">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-user"></i>
                                </div>
                                <h6>Tài khoản</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="payment">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-credit-card"></i>
                                </div>
                                <h6>Thanh toán</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="products">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-box"></i>
                                </div>
                                <h6>Sản phẩm</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="warranty">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-shield-alt"></i>
                                </div>
                                <h6>Bảo hành</h6>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-4">
                            <div class="help-category" data-category="contact">
                                <div class="icon-circle mb-2">
                                    <i class="fas fa-headset"></i>
                                </div>
                                <h6>Liên hệ</h6>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
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
    align-items: flex-start;
}

.message.user {
    flex-direction: row-reverse;
}

.message-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background-color: #e9ecef;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 10px;
    flex-shrink: 0;
}

.message.user .message-avatar {
    margin-right: 0;
    margin-left: 10px;
    background-color: #007bff;
    color: white;
}

.message-content {
    max-width: 80%;
    padding: 10px 15px;
    border-radius: 18px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.message.assistant .message-content {
    background-color: #f1f0f0;
    color: #333;
    border-top-left-radius: 5px;
}

.message.user .message-content {
    background-color: #007bff;
    color: white;
    border-top-right-radius: 5px;
}

.message-content p {
    margin-bottom: 0;
    flex: 1;
    line-height: 1.5;
}

.chat-input-form {
    margin-top: 10px;
}

.typing-indicator {
    display: flex;
    padding: 10px 15px;
    background-color: #f1f0f0;
    border-radius: 18px;
    border-top-left-radius: 5px;
    margin-bottom: 15px;
    width: fit-content;
    align-items: center;
}

.typing-indicator .message-avatar {
    margin-right: 10px;
}

.typing-indicator .dots {
    display: flex;
    align-items: center;
}

.typing-indicator .dots span {
    height: 8px;
    width: 8px;
    margin: 0 1px;
    background-color: #9E9EA1;
    display: block;
    border-radius: 50%;
    opacity: 0.4;
}

.typing-indicator .dots span:nth-of-type(1) {
    animation: 1s blink infinite 0.3333s;
}

.typing-indicator .dots span:nth-of-type(2) {
    animation: 1s blink infinite 0.6666s;
}

.typing-indicator .dots span:nth-of-type(3) {
    animation: 1s blink infinite 0.9999s;
}

@keyframes blink {
    50% {
        opacity: 1;
    }
}

.help-category {
    cursor: pointer;
    transition: transform 0.2s;
}

.help-category:hover {
    transform: translateY(-5px);
}

.icon-circle {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background-color: #f8f9fa;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto;
    border: 1px solid #e0e0e0;
    font-size: 24px;
    color: #007bff;
    transition: all 0.3s;
}

.help-category:hover .icon-circle {
    background-color: #007bff;
    color: white;
}

/* Markdown styles */
.message-content strong {
    font-weight: bold;
}

.message-content em {
    font-style: italic;
}

.message-content code {
    background-color: rgba(0, 0, 0, 0.1);
    padding: 2px 4px;
    border-radius: 3px;
    font-family: monospace;
}

.message-content pre {
    background-color: rgba(0, 0, 0, 0.1);
    padding: 10px;
    border-radius: 5px;
    overflow-x: auto;
    margin: 10px 0;
}

.message-content pre code {
    background-color: transparent;
    padding: 0;
}

.message-content ul, 
.message-content ol {
    margin: 10px 0;
    padding-left: 20px;
}

.message-content li {
    margin: 5px 0;
}

.message-content h1,
.message-content h2,
.message-content h3 {
    margin: 15px 0 10px 0;
}

.message-content h1 {
    font-size: 1.5em;
}

.message-content h2 {
    font-size: 1.3em;
}

.message-content h3 {
    font-size: 1.1em;
}

.message-content a {
    color: #007bff;
    text-decoration: underline;
}

.message.user .message-content a {
    color: #ffffff;
}
</style>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatMessages = document.getElementById('chatMessages');
    const quickQuestions = document.querySelectorAll('.quick-question');
    const helpCategories = document.querySelectorAll('.help-category');
    const imageInput = document.getElementById('imageInput');
    const sendImageBtn = document.getElementById('sendImageBtn');
    const imagePreviewContainer = document.getElementById('imagePreviewContainer');
    let selectedImageFile = null;
    const API_URL = 'http://localhost:4070/chat';
    
    // Get session ID and user ID from PHP
    const sessionId = '<?php echo $_SESSION['chat_session_id']; ?>';
    const userId = '<?php echo $userId; ?>';
    console.log(userId);
    // Function to convert markdown to HTML
    function markdownToHtml(text) {
        if (!text) return '';
        
        // Replace markdown with HTML
        return text
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Code blocks
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            // Inline code
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // Lists
            .replace(/^\s*[-*+]\s+(.*)$/gm, '<li>$1</li>')
            // Headers
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // Links
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
            // Line breaks
            .replace(/\n/g, '<br>');
    }

    // Function to add a message to the chat
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        
        const avatarIcon = document.createElement('i');
        avatarIcon.className = isUser ? 'fas fa-user' : 'fas fa-robot';
        avatarDiv.appendChild(avatarIcon);
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const messageParagraph = document.createElement('p');
        // Convert markdown to HTML for assistant messages
        messageParagraph.innerHTML = isUser ? content : markdownToHtml(content);
        
        messageContent.appendChild(messageParagraph);
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(messageContent);
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to show typing indicator
    function showTypingIndicator() {
        const indicatorDiv = document.createElement('div');
        indicatorDiv.className = 'typing-indicator';
        indicatorDiv.id = 'typingIndicator';
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        
        const avatarIcon = document.createElement('i');
        avatarIcon.className = 'fas fa-robot';
        avatarDiv.appendChild(avatarIcon);
        
        const dotsDiv = document.createElement('div');
        dotsDiv.className = 'dots';
        
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            dotsDiv.appendChild(dot);
        }
        
        indicatorDiv.appendChild(avatarDiv);
        indicatorDiv.appendChild(dotsDiv);
        
        chatMessages.appendChild(indicatorDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to remove typing indicator
    function removeTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    // Function to send message to API and get response
    async function sendToAssistant(question) {
        try {
            showTypingIndicator();
            
            // Sample responses based on question keywords (hardcoded answers)
            let answer;
            const lowerQuestion = question.toLowerCase();
            let isHardcoded = false;
            
            if (lowerQuestion.includes('theo dõi') && lowerQuestion.includes('đơn hàng')) {
                answer = "Bạn có thể theo dõi đơn hàng bằng cách đăng nhập vào tài khoản và truy cập 'Đơn hàng của tôi'. Nhấp vào đơn hàng cụ thể bạn muốn theo dõi và bạn sẽ thấy trạng thái hiện tại của nó. Chúng tôi cũng gửi thông tin theo dõi qua email khi đơn hàng của bạn được gửi đi.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('đổi trả') || lowerQuestion.includes('hoàn tiền')) {
                answer = "Chính sách đổi trả của chúng tôi cho phép bạn trả lại các mặt hàng trong vòng 30 ngày kể từ ngày giao hàng để được hoàn tiền đầy đủ. Các mặt hàng phải còn nguyên trạng với nhãn mác đính kèm. Để bắt đầu đổi trả, hãy vào 'Đơn hàng của tôi' trong tài khoản của bạn và chọn 'Trả lại mặt hàng' cho sản phẩm bạn muốn trả lại.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('quốc tế') && lowerQuestion.includes('vận chuyển')) {
                answer = "Có, chúng tôi cung cấp dịch vụ vận chuyển quốc tế đến hơn 100 quốc gia. Chi phí vận chuyển và thời gian giao hàng khác nhau tùy theo địa điểm. Bạn có thể xem chi phí vận chuyển chính xác trong quá trình thanh toán sau khi nhập địa chỉ của bạn. Xin lưu ý rằng đơn hàng quốc tế có thể phải chịu phí hải quan.";
                isHardcoded = true;
            } else if ((lowerQuestion.includes('đặt lại') || lowerQuestion.includes('quên')) && lowerQuestion.includes('mật khẩu')) {
                answer = "Để đặt lại mật khẩu, hãy nhấp vào liên kết 'Quên mật khẩu' trên trang đăng nhập. Nhập địa chỉ email của bạn và chúng tôi sẽ gửi cho bạn một liên kết để đặt lại mật khẩu. Liên kết có hiệu lực trong 24 giờ.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('thanh toán')) {
                answer = "Chúng tôi chấp nhận nhiều phương thức thanh toán bao gồm thẻ tín dụng/ghi nợ (Visa, Mastercard, American Express), PayPal và chuyển khoản ngân hàng. Tất cả các khoản thanh toán được xử lý an toàn thông qua hệ thống thanh toán được mã hóa của chúng tôi.";
                isHardcoded = true;
            } else if ((lowerQuestion.includes('liên hệ') && lowerQuestion.includes('hỗ trợ')) || lowerQuestion.includes('chăm sóc khách hàng')) {
                answer = "Bạn có thể liên hệ với đội ngũ hỗ trợ khách hàng của chúng tôi qua nhiều kênh: Gửi email cho chúng tôi tại k100iltqbao@gmail.com, gọi cho chúng tôi theo số 0917947917 (Thứ Hai đến Chủ nhật, 9 giờ sáng đến 6 giờ chiều ), hoặc sử dụng biểu mẫu liên hệ trên trang Liên hệ của chúng tôi. Chúng tôi thường phản hồi trong vòng 24 giờ.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('vận chuyển') && (lowerQuestion.includes('thời gian') || lowerQuestion.includes('bao lâu'))) {
                answer = "Vận chuyển tiêu chuẩn thường mất 3-5 ngày làm việc trong nội địa. Vận chuyển nhanh mất 1-2 ngày làm việc. Vận chuyển quốc tế có thể mất 7-14 ngày làm việc tùy thuộc vào quốc gia đến và thời gian xử lý hải quan.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('hủy') && lowerQuestion.includes('đơn hàng')) {
                answer = "Bạn có thể hủy đơn hàng nếu nó chưa được gửi đi. Vào 'Đơn hàng của tôi' trong tài khoản của bạn, chọn đơn hàng bạn muốn hủy và nhấp vào nút 'Hủy đơn hàng'. Nếu đơn hàng đã được gửi đi, bạn sẽ cần trả lại theo chính sách đổi trả của chúng tôi.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('bảo hành')) {
                answer = "Hầu hết các sản phẩm của chúng tôi đều có bảo hành tiêu chuẩn 1 năm của nhà sản xuất, bao gồm các lỗi về vật liệu và tay nghề. Một số sản phẩm có tùy chọn bảo hành mở rộng. Bạn có thể tìm thấy thông tin bảo hành cụ thể trên trang sản phẩm hoặc trong tài liệu đi kèm với sản phẩm của bạn.";
                isHardcoded = true;
            } else if (lowerQuestion.includes('giảm giá') || lowerQuestion.includes('mã')) {
                answer = "Để sử dụng mã giảm giá, thêm sản phẩm vào giỏ hàng, tiến hành thanh toán và nhập mã của bạn vào trường 'Mã giảm giá' trước khi hoàn tất mua hàng. Bạn có thể tìm thấy các chương trình khuyến mãi hiện tại trên trang chủ của chúng tôi, thông qua bản tin hoặc trên các kênh mạng xã hội của chúng tôi.";
                isHardcoded = true;
            }

            if (isHardcoded) {
                removeTypingIndicator();
                addMessage(answer);
                return;
            }

            // Nếu không phải câu hỏi fix cứng, trả về thông báo mặc định
            removeTypingIndicator();
            addMessage("Xin lỗi, tôi không thể trả lời câu hỏi này. Vui lòng thử lại sau hoặc liên hệ hỗ trợ.");
            
        } catch (error) {
            console.error('Error:', error);
            removeTypingIndicator();
            addMessage("Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại sau hoặc liên hệ với đội ngũ hỗ trợ khách hàng của chúng tôi để được hỗ trợ.");
        }
    }
    
    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const question = userInput.value.trim();
        if (question === '' && !selectedImageFile) return;
        // Hiển thị text và/hoặc ảnh user gửi lên chat
        if (question !== '') {
            addMessage(question, true);
        }
        if (selectedImageFile) {
            // Hiển thị ảnh user gửi lên chat với overlay click
            const reader = new FileReader();
            reader.onload = function(e) {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message user';
                const avatarDiv = document.createElement('div');
                avatarDiv.className = 'message-avatar';
                const avatarIcon = document.createElement('i');
                avatarIcon.className = 'fas fa-user';
                avatarDiv.appendChild(avatarIcon);
                const messageContent = document.createElement('div');
                messageContent.className = 'message-content';
                const imgWrapper = document.createElement('div');
                imgWrapper.style.position = 'relative';
                imgWrapper.style.display = 'inline-block';
                const img = document.createElement('img');
                img.src = e.target.result;
                img.alt = 'Ảnh bạn gửi';
                img.style.maxWidth = '120px';
                img.style.borderRadius = '8px';
                img.style.cursor = 'pointer';
                // Overlay
                const overlay = document.createElement('div');
                overlay.style.position = 'absolute';
                overlay.style.top = '0';
                overlay.style.left = '0';
                overlay.style.width = '100%';
                overlay.style.height = '100%';
                overlay.style.background = 'rgba(0,0,0,0.5)';
                overlay.style.color = '#fff';
                overlay.style.display = 'flex';
                overlay.style.alignItems = 'center';
                overlay.style.justifyContent = 'center';
                overlay.style.opacity = '0';
                overlay.style.borderRadius = '8px';
                overlay.style.transition = 'opacity 0.2s';
                overlay.innerText = 'Đã gửi ảnh';
                imgWrapper.appendChild(img);
                imgWrapper.appendChild(overlay);
                img.addEventListener('click', function() {
                    overlay.style.opacity = overlay.style.opacity === '1' ? '0' : '1';
                });
                messageContent.appendChild(imgWrapper);
                messageDiv.appendChild(avatarDiv);
                messageDiv.appendChild(messageContent);
                chatMessages.appendChild(messageDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            };
            reader.readAsDataURL(selectedImageFile);
        }
        // Gửi cả text và ảnh (nếu có) trong 1 request
        sendTextAndImageToAssistant(question, selectedImageFile);
        selectedImageFile = null;
        imageInput.value = '';
        imagePreviewContainer.style.display = 'none';
        imagePreviewContainer.innerHTML = '';
        userInput.value = '';
    });
    
    // Handle quick questions
    quickQuestions.forEach(button => {
        button.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            
            // Add user message to chat
            addMessage(question, true);
            
            // Send to assistant and get response
            sendToAssistant(question);
            
            // Focus on input field
            userInput.focus();
        });
    });
    
    // Handle help categories
    helpCategories.forEach(category => {
        category.addEventListener('click', function() {
            const categoryName = this.getAttribute('data-category');
            let question;
            
            switch(categoryName) {
                case 'orders':
                    question = "Cho tôi biết về việc theo dõi đơn hàng";
                    break;
                case 'shipping':
                    question = "Các tùy chọn và thời gian vận chuyển của bạn là gì?";
                    break;
                case 'returns':
                    question = "Chính sách đổi trả của bạn là gì?";
                    break;
                case 'account':
                    question = "Làm thế nào để quản lý cài đặt tài khoản của tôi?";
                    break;
                case 'payment':
                    question = "Bạn chấp nhận những phương thức thanh toán nào?";
                    break;
                case 'products':
                    question = "Làm thế nào để tìm thông tin sản phẩm?";
                    break;
                case 'warranty':
                    question = "Sản phẩm của bạn có bảo hành gì?";
                    break;
                case 'contact':
                    question = "Làm thế nào để liên hệ với bộ phận hỗ trợ khách hàng?";
                    break;
                default:
                    question = "Cho tôi biết về " + categoryName;
            }
            
            // Add user message to chat
            addMessage(question, true);
            
            // Send to assistant and get response
            sendToAssistant(question);
            
            // Scroll to chat container
            document.getElementById('chatContainer').scrollIntoView({ behavior: 'smooth' });
        });
    });
    
    // Preview ảnh trước khi gửi
    sendImageBtn.addEventListener('click', function() {
        imageInput.click();
    });
    imageInput.addEventListener('change', function() {
        if (imageInput.files && imageInput.files[0]) {
            selectedImageFile = imageInput.files[0];
            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreviewContainer.innerHTML = `<div style='position:relative; display:inline-block;'>
                    <img src='${e.target.result}' alt='Ảnh preview' style='max-width:120px; border-radius:8px;'/>
                    <button type='button' id='removeImageBtn' style='position:absolute;top:2px;right:2px;background:#222;color:#fff;border:none;border-radius:50%;width:20px;height:20px;line-height:18px;font-size:14px;cursor:pointer;'>×</button>
                </div>`;
                imagePreviewContainer.style.display = 'block';
                document.getElementById('removeImageBtn').onclick = function() {
                    selectedImageFile = null;
                    imageInput.value = '';
                    imagePreviewContainer.style.display = 'none';
                    imagePreviewContainer.innerHTML = '';
                };
            };
            reader.readAsDataURL(selectedImageFile);
        }
    });
    
    // Hàm gửi cả text và ảnh lên API
    async function sendTextAndImageToAssistant(question, imageFile) {
        try {
            showTypingIndicator();
            const formData = new FormData();
            
            // Only append user_id if it exists
            if (userId) {
                formData.append('user_id', userId);
            }
            formData.append('session_id', sessionId);
            
            if (question) formData.append('query', question);
            if (imageFile) formData.append('image', imageFile);
            
            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                throw new Error('Không thể kết nối tới trợ lý AI.');
            }
            const data = await response.json();
            removeTypingIndicator();
            if (data && data.response) {
                addMessage(data.response);
            } else {
                addMessage('Xin lỗi, tôi không thể trả lời câu hỏi này. Vui lòng thử lại sau hoặc liên hệ hỗ trợ.');
            }
        } catch (error) {
            console.error('Error:', error);
            removeTypingIndicator();
            addMessage("Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại sau hoặc liên hệ với đội ngũ hỗ trợ khách hàng của chúng tôi để được hỗ trợ.");
        }
    }
    
    // Function to load chat history
    async function loadChatHistory() {
        try {
            const response = await fetch('controllers/data/history.json');
            if (!response.ok) {
                throw new Error('Không thể tải lịch sử chat');
            }
            const data = await response.json();
            
            // Clear existing messages except the welcome message
            const welcomeMessage = chatMessages.querySelector('.message.assistant');
            chatMessages.innerHTML = '';
            if (welcomeMessage) {
                chatMessages.appendChild(welcomeMessage);
            }

            // Check if user has history
            if (data[userId] && data[userId][sessionId]) {
                const userHistory = data[userId][sessionId];
                userHistory.forEach(item => {
                    if (item.query) {
                        addMessage(item.query, true);
                    }
                    if (item.response) {
                        addMessage(item.response);
                    }
                });
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }

    // Function to clear chat history
    async function clearChatHistory() {
        if (!confirm('Bạn có chắc chắn muốn xóa lịch sử chat?')) {
            return;
        }

        try {
            const response = await fetch('controllers/clear_history.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    session_id: sessionId
                })
            });

            if (!response.ok) {
                throw new Error('Không thể xóa lịch sử chat');
            }

            // Clear messages except welcome message
            const welcomeMessage = chatMessages.querySelector('.message.assistant');
            chatMessages.innerHTML = '';
            if (welcomeMessage) {
                chatMessages.appendChild(welcomeMessage);
            }

            alert('Đã xóa lịch sử chat thành công!');
        } catch (error) {
            console.error('Error clearing chat history:', error);
            alert('Có lỗi xảy ra khi xóa lịch sử chat');
        }
    }

    // Add event listener for clear history button
    document.getElementById('clearHistoryBtn').addEventListener('click', clearChatHistory);

    // Load chat history when page loads
    loadChatHistory();

    // Focus on input field when page loads
    userInput.focus();
});
</script>

<?php include 'includes/footer.php'; ?>