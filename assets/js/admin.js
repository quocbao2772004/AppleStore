// JavaScript cho Trang Quản Trị

document.addEventListener('DOMContentLoaded', function() {
    // Kích hoạt tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Kích hoạt popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
      return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Tự động ẩn thông báo sau 5 giây
    setTimeout(function() {
      var alerts = document.querySelectorAll('.alert');
      alerts.forEach(function(alert) {
        var bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      });
    }, 5000);
    
    // Xác nhận trước khi xóa
    var deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(function(button) {
      button.addEventListener('click', function(e) {
        if (!confirm('Bạn có chắc chắn muốn xóa mục này? Hành động này không thể hoàn tác.')) {
          e.preventDefault();
        }
      });
    });
    
    // Xem trước hình ảnh cho input file
    var imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    imageInputs.forEach(function(input) {
      input.addEventListener('change', function(e) {
        var preview = document.querySelector('#' + this.id + '-preview');
        if (preview) {
          if (this.files && this.files[0]) {
            var reader = new FileReader();
            reader.onload = function(e) {
              preview.src = e.target.result;
              preview.style.display = 'block';
            }
            reader.readAsDataURL(this.files[0]);
          } else {
            preview.src = '';
            preview.style.display = 'none';
          }
        }
      });
    });
  });