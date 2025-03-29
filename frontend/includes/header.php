<header>
        <div class="logo">Apple Store</div>
        <?php 
 
        if (isset($_SESSION['user_id'])) {
            include '../includes/navbar2.php'; 
        } else {
            include '../includes/navbar.php'; 
        }
        ?>
    </header>