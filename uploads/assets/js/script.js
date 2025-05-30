// Public Site JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Auto-hide alert messages after 5 seconds
    setTimeout(function() {
      var alerts = document.querySelectorAll('.alert');
      alerts.forEach(function(alert) {
        var bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      });
    }, 5000);
    
    // Quantity increment/decrement buttons
    var quantityInputs = document.querySelectorAll('.quantity-input');
    quantityInputs.forEach(function(input) {
      var decrementBtn = input.previousElementSibling;
      var incrementBtn = input.nextElementSibling;
      
      if (decrementBtn && decrementBtn.classList.contains('btn-decrement')) {
        decrementBtn.addEventListener('click', function() {
          var currentValue = parseInt(input.value);
          if (currentValue > parseInt(input.min)) {
            input.value = currentValue - 1;
            // Trigger change event
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
            // Trigger change event
            var event = new Event('change', { bubbles: true });
            input.dispatchEvent(event);
          }
        });
      }
    });
    
    // Cart quantity update
    var cartUpdateForms = document.querySelectorAll('.cart-update-form');
    cartUpdateForms.forEach(function(form) {
      var quantityInput = form.querySelector('.quantity-input');
      if (quantityInput) {
        quantityInput.addEventListener('change', function() {
          form.submit();
        });
      }
    });
    
    // Product image gallery
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