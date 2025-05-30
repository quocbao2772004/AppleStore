// JavaScript cho Trang Web Công Khai

document.addEventListener('DOMContentLoaded', function() {
    // Kích hoạt tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Tự động ẩn thông báo sau 5 giây
    setTimeout(function() {
      var alerts = document.querySelectorAll('.alert');
      alerts.forEach(function(alert) {
        var bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      });
    }, 5000);
    
    // Nút tăng/giảm số lượng
    var quantityInputs = document.querySelectorAll('.quantity-input');
    quantityInputs.forEach(function(input) {
      var decrementBtn = input.previousElementSibling;
      var incrementBtn = input.nextElementSibling;
      
      if (decrementBtn && decrementBtn.classList.contains('btn-decrement')) {
        decrementBtn.addEventListener('click', function() {
          var currentValue = parseInt(input.value);
          if (currentValue > parseInt(input.min)) {
            input.value = currentValue - 1;
            // Kích hoạt sự kiện thay đổi
            var event = new Event('change', { bubbles: true });
            input.dispatchEvent(event);
          }
        });
      }
      
      if (incrementBtn && incrementBtn.classList.contains('btn-increment')) {
        incrementBtn.addEventListener('click', function() {
          var currentValue = parseInt(input.value);
          if (currentValue < parseInt(input.max)) {
            input.value = currentValue + 1;
            // Kích hoạt sự kiện thay đổi
            var event = new Event('change', { bubbles: true });
            input.dispatchEvent(event);
          }
        });
      }
    });
    
    // Cập nhật số lượng giỏ hàng
    var cartUpdateForms = document.querySelectorAll('.cart-update-form');
    cartUpdateForms.forEach(function(form) {
      var quantityInput = form.querySelector('.quantity-input');
      if (quantityInput) {
        quantityInput.addEventListener('change', function() {
          form.submit();
        });
      }
    });
    
    // Thư viện ảnh sản phẩm
    var mainImage = document.querySelector('#main-product-image');
    var thumbnails = document.querySelectorAll('.product-thumbnail');
    
    if (mainImage && thumbnails.length > 0) {
      thumbnails.forEach(function(thumbnail) {
        thumbnail.addEventListener('click', function() {
          mainImage.src = this.dataset.image;
          thumbnails.forEach(function(thumb) {
            thumb.classList.remove('active');
          });
          this.classList.add('active');
        });
      });
    }
  });