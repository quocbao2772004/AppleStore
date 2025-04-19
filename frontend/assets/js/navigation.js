document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const sectionId = this.getAttribute('href').substring(1);

        // Ẩn tất cả section
        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });

        // Hiển thị section được chọn
        document.getElementById(sectionId).classList.add('active');

        // Cập nhật trạng thái active cho nav-link
        document.querySelectorAll('.nav-link').forEach(nav => {
            nav.classList.remove('active');
        });
        this.classList.add('active');

        // Tải dữ liệu tương ứng
        if (sectionId === 'products') {
            fetchProducts();
        } else if (sectionId === 'orders') {
            fetchOrders();
        } else if (sectionId === 'users') {
            fetchUsers();
        }
    });
});