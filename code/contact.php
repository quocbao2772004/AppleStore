<?php
require_once 'includes/functions.php';
require_once 'config/database.php';

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Get form data
    $name = clean($_POST['name']);
    $email = clean($_POST['email']);
    $subject = clean($_POST['content']);
    $message = clean($_POST['message']);
    
    // Validate input
    $errors = [];
    
    if (empty($name)) {
        $errors[] = 'Name is required';
    }
    
    if (empty($email)) {
        $errors[] = 'Email is required';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $errors[] = 'Invalid email format';
    }
    
    if (empty($subject)) {
        $errors[] = 'Subject is required';
    }
    
    if (empty($message)) {
        $errors[] = 'Message is required';
    }
    
    // If no errors, process the form
    if (empty($errors)) {

        
        // For demonstration purposes, just show a success message
        setFlashMessage('success', 'Your message has been sent successfully. We will get back to you soon!');
        redirect('contact.php');
    } else {
        // Set error message
        setFlashMessage('error', implode('<br>', $errors));
    }
}

// Page title
$pageTitle = 'Contact Us';

// Include header
include 'includes/header.php';
?>

<div class="container py-5">
    <div class="row">
        <div class="col-lg-8 mx-auto">
            <div class="card shadow">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Liên hệ với chúng tôi</h4>
                </div>
                <div class="card-body">
                    <p class="mb-4">Có câu hỏi hoặc phản hồi? Điền vào biểu mẫu bên dưới và chúng tôi sẽ trả lời bạn sớm nhất có thể.</p>
                    
                    <form action="" method="POST" id="contactForm">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="name" class="form-label">Tên của bạn <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="name" name="name" required>
                            </div>
                            <div class="col-md-6">
                                <label for="email" class="form-label">Địa chỉ email <span class="text-danger">*</span></label>
                                <input type="email" class="form-control" id="email" name="email" required>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="content" class="form-label">Chủ đề <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="content" name="content" required>
                        </div>
                        
                        <div class="mb-3">
                            <label for="message" class="form-label">Nội dung <span class="text-danger">*</span></label>
                            <textarea class="form-control" id="message" name="message" rows="5" required></textarea>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary" id="submitBtn">Gửi tin nhắn</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row mt-5">
        <div class="col-md-4 mb-4">
            <div class="card h-100 text-center">
                <div class="card-body">
                    <i class="fas fa-map-marker-alt fa-3x text-primary mb-3"></i>
                    <h5>Địa chỉ của chúng tôi</h5>
                    <p>96A Trần Phú, Mộ Lao, Hà Đông, Hà Nội</p>
                </div>
            </div>
        </div>
        
        <div class="col-md-4 mb-4">
            <div class="card h-100 text-center">
                <div class="card-body">
                    <i class="fas fa-phone fa-3x text-primary mb-3"></i>
                    <h5>Số điện thoại</h5>
                    <p>+84 964 282 369</p>
                    <p>+84 917 947 910</p>
                </div>
            </div>
        </div>
        
        <div class="col-md-4 mb-4">
            <div class="card h-100 text-center">
                <div class="card-body">
                    <i class="fas fa-envelope fa-3x text-primary mb-3"></i>
                    <h5>Địa chỉ email</h5>
                    <p>k100iltqbao@gmail.com</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row mt-5">
        <div class="col-12">
            <div class="card">
                <div class="card-body p-0">
                    <!-- Replace with your Google Maps embed code -->
                    <div class="ratio ratio-16x9">
                    <iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3725.292276418145!2d105.78484157630787!3d20.98091798941795!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3135accdd8a1ad71%3A0xa2f9b16036648187!2zSOG7jWMgdmnhu4duIEPDtG5nIG5naOG7hyBCxrB1IGNow61uaCB2aeG7hW4gdGjDtG5n!5e0!3m2!1svi!2s!4v1746782020472!5m2!1svi!2s" width="600" height="450" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const contactForm = document.getElementById('contactForm');
    const submitBtn = document.getElementById('submitBtn');

    contactForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Disable submit button and show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Đang gửi...';
        
        try {
            const formData = new FormData(contactForm);
            
            const response = await fetch('http://localhost:4070/send-email', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Show success message
                alert(data.message);
                // Reset form
                contactForm.reset();
            } else {
                // Show error message
                alert(data.message || 'Có lỗi xảy ra khi gửi tin nhắn. Vui lòng thử lại sau.');
            }
        } catch (error) {
            // Show error message
            alert('Không thể kết nối đến máy chủ. Vui lòng thử lại sau.');
            console.error('Error:', error);
        } finally {
            // Re-enable submit button and restore original text
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Gửi tin nhắn';
        }
    });
});
</script>

<?php include 'includes/footer.php'; ?>