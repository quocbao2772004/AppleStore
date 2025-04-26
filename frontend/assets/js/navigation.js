document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const sectionId = this.getAttribute('href').substring(1);

        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });

        document.getElementById(sectionId).classList.add('active');

        document.querySelectorAll('.nav-link').forEach(nav => {
            nav.classList.remove('active');
        });
        this.classList.add('active');

        if (sectionId === 'products') {
            fetchProducts();
        } else if (sectionId === 'orders') {
            fetchOrders();
        } else if (sectionId === 'users') {
            fetchUsers();
        }
    });
});