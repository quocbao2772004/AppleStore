function fetchOrders() {
    fetch('../../backend/admin/fetch_order_admin.php')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const tbody = document.querySelector('#order-table tbody');
            tbody.innerHTML = '';

            if (!Array.isArray(data)) {
                tbody.innerHTML = `<tr><td colspan="5" class="error-message">Dữ liệu không hợp lệ: ${JSON.stringify(data)}</td></tr>`;
                return;
            }

            if (data.length > 0 && data[0].error) {
                tbody.innerHTML = `<tr><td colspan="5" class="error-message">${data[0].message}</td></tr>`;
                return;
            }

            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-message">Không có đơn hàng nào.</td></tr>';
                return;
            }

            data.forEach(order => {
                const row = `
                    <tr>
                        <td>${order.id}</td>
                        <td>${order.user_email}</td>
                        <td>${order.total}</td>
                        <td>${order.status}</td>
                        <td>${order.created_at}</td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        })
        .catch(error => {
            console.error('Lỗi fetchOrders:', error);
            const tbody = document.querySelector('#order-table tbody');
            tbody.innerHTML = `<tr><td colspan="5" class="error-message">Lỗi khi tải đơn hàng: ${error.message}</td></tr>`;
        });
}