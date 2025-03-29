document.getElementById('category-filter').addEventListener('change', filterProducts);
document.getElementById('sort-filter').addEventListener('change', filterProducts);

function filterProducts() {
    const category = document.getElementById('category-filter').value;
    const sort = document.getElementById('sort-filter').value;
    const page = 1; // 
    const url = `?page=${page}&category=${encodeURIComponent(category)}&sort=${encodeURIComponent(sort)}`;

    fetch(url)
        .then(response => response.text())
        .then(data => {
            document.open();
            document.write(data);
            document.close();
        })
        .catch(error => console.error('Lỗi:', error));
}