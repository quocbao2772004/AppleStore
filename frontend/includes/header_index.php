<header>
        <div class="logo">Apple Store</div>
        <?php 
        if (isset($_SESSION['user_id'])) {
            include 'frontend/includes/navbar_index2.php'; 
        } else {
            include 'frontend/includes/navbar_index.php'; 
        }
        ?>
    </header>