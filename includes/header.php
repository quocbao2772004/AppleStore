<header>
        <div class="logo">Apple Store</div>
        <?php 
        // Kiểm tra trạng thái đăng nhập để include navbar phù hợp
        if (isset($_SESSION['user_id'])) {
            include '../includes/navbar2.php'; // Navbar cho đã đăng nhập
        } else {
            include '../includes/navbar.php'; // Navbar cho chưa đăng nhập
        }
        ?>
    </header>