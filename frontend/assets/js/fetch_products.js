function fetchProducts() {
    fetch('../../backend/admin/fetch_products_admin.php')
        .then(response => response.json())
        .then(data => {
            const productTableBody = document.querySelector('#product-table tbody');
            productTableBody.innerHTML = '';

            if (data.length === 0) {
                productTableBody.innerHTML = '<tr><td colspan="7" class="empty-message">Không có sản phẩm nào!</td></tr>';
                return;
            }

            data.forEach(product => {
                let priceFormatted = product.price;
                if (!priceFormatted.includes('VND')) {
                    let priceNum = priceFormatted.replace(/\sVND/g, '');
                    priceNum = priceNum.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
                    priceFormatted = priceNum + ' VND';
                }

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${product.id}</td>
                    <td><img src="${product.image}" alt="${product.name}"></td>
                    <td>${product.name}</td>
                    <td>${priceFormatted}</td>
                    <td>${product.category}</td>
                    <td>${product.quantity}</td>
                    <td>
                        <button class="action-btn edit-btn" onclick="editProduct(${product.id})">
                            <i class="fas fa-edit"></i> Sửa
                        </button>
                        <button class="action-btn delete" onclick="deleteProduct(${product.id})">
                            <i class="fas fa-trash-alt"></i> Xóa
                        </button>
                    </td>
                `;
                productTableBody.appendChild(row);
            });
        })
        .catch(error => {
            document.querySelector('#product-table tbody').innerHTML = '<tr><td colspan="7" class="error-message">Lỗi khi tải sản phẩm!</td></tr>';
        });
}

document.addEventListener('DOMContentLoaded', fetchProducts);