document.getElementById('add-product-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);

    fetch('../../backend/admin/add_product.php', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.text().then(text => {
            try {
                const data = JSON.parse(text);
                return data;
            } catch (error) {
                console.error('Response không phải JSON:', text);
                throw new Error('Response không phải JSON: ' + text);
            }
        });
    })
    .then(data => {
        if (data.success) {
            alert('Thêm sản phẩm thành công!');
            fetchProducts();
            this.reset();
        } else {
            alert('Lỗi: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Lỗi khi thêm sản phẩm:', error);
        alert('Lỗi khi thêm sản phẩm: ' + error.message);
    });
});

function editProduct(id) {
    fetch(`../../backend/admin/fetch_product_admin.php?id=${id}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.text().then(text => {
                try {
                    const data = JSON.parse(text);
                    return data;
                } catch (error) {
                    console.error('Response không phải JSON:', text);
                    throw new Error('Response không phải JSON: ' + text);
                }
            });
        })
        .then(data => {
            if (data.success === false) {
                throw new Error(data.message || 'Lỗi từ server');
            }
            document.getElementById('edit-product-id').value = data.id;
            document.getElementById('edit-product-name').value = data.name;
            document.getElementById('edit-product-price').value = data.price;
            document.getElementById('edit-product-image').value = data.image;
            document.getElementById('edit-product-category').value = data.category;
            document.getElementById('edit-product-quantity').value = data.quantity;
            document.getElementById('edit-product-modal').style.display = 'flex';
        })
        .catch(error => {
            console.error('Lỗi fetchProduct:', error);
            alert('Lỗi khi tải thông tin sản phẩm: ' + error.message);
        });
}

function deleteProduct(id) {
    if (confirm('Bạn có chắc muốn xóa sản phẩm này?')) {
        fetch(`../../backend/admin/delete_product.php?id=${id}`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.text().then(text => {
                try {
                    const data = JSON.parse(text);
                    return data;
                } catch (error) {
                    console.error('Response không phải JSON:', text);
                    throw new Error('Response không phải JSON: ' + text);
                }
            });
        })
        .then(data => {
            if (data.success) {
                alert('Xóa sản phẩm thành công!');
                fetchProducts();
            } else {
                alert('Lỗi: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Lỗi khi xóa sản phẩm:', error);
            alert('Lỗi khi xóa sản phẩm: ' + error.message);
        });
    }
}

document.getElementById('edit-product-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);

    fetch('../../backend/admin/update_product.php', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Cập nhật sản phẩm thành công!');
            fetchProducts();
            document.getElementById('edit-product-modal').style.display = 'none';
        } else {
            alert('Lỗi: ' + data.message);
        }
    })
    .catch(error => {
        alert('Lỗi khi cập nhật sản phẩm: ' + error.message);
    });
});

document.querySelector('.close-btn').addEventListener('click', () => {
    document.getElementById('edit-product-modal').style.display = 'none';
});

document.querySelector('.cancel-btn').addEventListener('click', () => {
    document.getElementById('edit-product-modal').style.display = 'none';
});

window.addEventListener('click', (e) => {
    const modal = document.getElementById('edit-product-modal');
    if (e.target === modal) {
        modal.style.display = 'none';
    }
});