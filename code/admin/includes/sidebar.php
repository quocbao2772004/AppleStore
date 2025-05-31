    <nav id="sidebarMenu" class="col-md-3 col-lg-2 d-md-block bg-light sidebar collapse">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link <?php echo $currentPage === 'index.php' ? 'active' : ''; ?>" href="/admin/index.php">
                    <i class="fas fa-tachometer-alt"></i> Quản trị
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo strpos($currentPage, 'products') !== false ? 'active' : ''; ?>" href="/admin/products/index.php">
                    <i class="fas fa-box"></i> Sản phẩm
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo strpos($currentPage, 'categories') !== false ? 'active' : ''; ?>" href="/admin/categories/index.php">
                    <i class="fas fa-folder"></i> Danh mục
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo strpos($currentPage, 'orders') !== false ? 'active' : ''; ?>" href="/admin/orders/index.php">
                    <i class="fas fa-shopping-cart"></i> Đơn hàng
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo strpos($currentPage, 'users') !== false ? 'active' : ''; ?>" href="/admin/users/index.php">
                    <i class="fas fa-users"></i> Người dùng
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo strpos($currentPage, 'reviews') !== false ? 'active' : ''; ?>" href="/admin/reviews/index.php">
                    <i class="fas fa-star"></i> Đánh giá
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo $currentPage === 'statistics.php' ? 'active' : ''; ?>" href="/admin/statistics.php">
                    <i class="fas fa-chart-line"></i> Thống kê
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo strpos($_SERVER['PHP_SELF'], '/admin/assistant/') !== false ? 'active' : ''; ?>" href="/admin/assistant/index.php">
                    <i class="fas fa-robot me-2"></i>
                    Trợ lý Ảo
                </a>
            </li>
        </ul>
        
        <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
            <span>Hệ thống</span>
        </h6>
        <ul class="nav flex-column mb-2">
            <li class="nav-item">
                <a class="nav-link <?php echo $currentPage === 'profile.php' ? 'active' : ''; ?>" href="/admin/profile.php">
                    <i class="fas fa-user-cog"></i> Trang cá nhân
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link" href="/" target="_blank">
                    <i class="fas fa-external-link-alt"></i> Xem cửa hàng
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link" href="/logout.php">
                    <i class="fas fa-sign-out-alt"></i> Đăng xuất
                </a>
            </li>
        </ul>
    </div>
</nav>