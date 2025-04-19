function fetchUsers() {
    fetch('../../backend/admin/fetch_user_admin.php')
        .then(response => response.json())
        .then(data => {
            const tbody = document.querySelector('#user-table tbody');
            tbody.innerHTML = '';
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="empty-message">Không có người dùng nào.</td></tr>';
                return;
            }
            data.forEach(user => {
                const row = `
                    <tr>
                        <td>${user.id}</td>
                        <td>${user.email}</td>
                        <td>${user.created_at}</td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        })
        .catch(error => {
            const tbody = document.querySelector('#user-table tbody');
            tbody.innerHTML = `<tr><td colspan="3" class="error-message">Lỗi khi tải người dùng: ${error.message}</td></tr>`;
        });
}