<?php
session_start();
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thông tin cá nhân</title>
    <link rel="stylesheet" type="text/css" href="../assets/css/applestyle.css" />
    <style>
        .personal-info .container {
            max-width: 600px;
            margin: 20px auto;
            padding: 20px;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .personal-info h2, .personal-info h3 {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        .personal-info .info-item {
            background-color: #f9f9f9;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            font-size: 14px;
        }
        .personal-info .info-item label {
            font-weight: bold;
            display: inline-block;
            width: 150px;
        }
        .personal-info .edit-form {
            display: none;
            margin-top: 20px;
        }
        .personal-info .edit-form input, .personal-info .edit-form select {
            margin: 5px 0;
            padding: 8px;
            width: 100%;
            max-width: 400px;
            border: 1px solid #d2d2d7;
            border-radius: 10px;
            background-color: #fafafa;
            color: #1d1d1f;
            outline: none;
            transition: border-color 0.3s ease;
        }
        .personal-info .edit-form input:focus,
        .personal-info .edit-form select:focus {
            border-color: #0071e3;
        }
        .personal-info .btn {
            padding: 8px 20px;
            margin: 5px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
        }
        .personal-info .btn-edit, .personal-info .btn-save {
            background-color: #0071e3;
            color: #fff;
        }
        .personal-info .btn-cancel {
            background-color: #dc3545;
            color: #fff;
        }
        .personal-info .text-center {
            text-align: center;
        }
    </style>
</head>
<body class="bg-gray-100">
    <?php
        // Kết nối database
        $conn = new mysqli("localhost", "root", "root", "apple_store");
        if ($conn->connect_error) {
            die("Kết nối thất bại: " . $conn->connect_error);
        }

        $user = null;
        $shipping = null;

        // Lấy thông tin người dùng từ database
        $email = isset($_SESSION['user_email']) ? $_SESSION['user_email'] : null;
        if ($email) {
            $sql_user = "SELECT * FROM users WHERE email = ?";
            $stmt_user = $conn->prepare($sql_user);
            $stmt_user->bind_param("s", $email);
            $stmt_user->execute();
            $result_user = $stmt_user->get_result();
            if ($result_user->num_rows > 0) {
                $user = $result_user->fetch_assoc();
            }

            // Lấy thông tin giao hàng
            if ($user) {
                $sql_shipping = "SELECT * FROM shipping_info WHERE user_id = ?";
                $stmt_shipping = $conn->prepare($sql_shipping);
                $stmt_shipping->bind_param("i", $user['id']);
                $stmt_shipping->execute();
                $result_shipping = $stmt_shipping->get_result();
                if ($result_shipping->num_rows > 0) {
                    $shipping = $result_shipping->fetch_assoc();
                }
            }
        }

        // Xử lý cập nhật thông tin
        if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST["save"]) && $user) {
            $name = $_POST["name"];
            $age = $_POST["age"];
            $phone = $_POST["phone"];
            $address = $_POST["address"];
            $city = $_POST["city"];
            $district = $_POST["district"];
            $postal_code = $_POST["postal_code"];
            $shipping_method = $_POST["shipping_method"];

            // Cập nhật thông tin người dùng
            $update_user_sql = "UPDATE users SET fullname = ?, phone = ? WHERE email = ?";
            $update_user_stmt = $conn->prepare($update_user_sql);
            $update_user_stmt->bind_param("sss", $name, $phone, $email);
            $update_user_stmt->execute();
            $update_user_stmt->close();

            // Cập nhật hoặc thêm thông tin giao hàng
            if ($shipping) {
                $update_shipping_sql = "UPDATE shipping_info SET address = ?, city = ?, district = ?, postal_code = ?, shipping_method = ? WHERE user_id = ?";
                $update_shipping_stmt = $conn->prepare($update_shipping_sql);
                $update_shipping_stmt->bind_param("sssssi", $address, $city, $district, $postal_code, $shipping_method, $user['id']);
                $update_shipping_stmt->execute();
                $update_shipping_stmt->close();
            } else {
                $insert_shipping_sql = "INSERT INTO shipping_info (user_id, address, city, district, postal_code, shipping_method) VALUES (?, ?, ?, ?, ?, ?)";
                $insert_shipping_stmt = $conn->prepare($insert_shipping_sql);
                $insert_shipping_stmt->bind_param("isssss", $user['id'], $address, $city, $district, $postal_code, $shipping_method);
                $insert_shipping_stmt->execute();
                $insert_shipping_stmt->close();
            }

            // Cập nhật lại thông tin
            $stmt_user->execute();
            $result_user = $stmt_user->get_result();
            $user = $result_user->fetch_assoc();
            $stmt_shipping->execute();
            $result_shipping = $stmt_shipping->get_result();
            $shipping = $result_shipping->fetch_assoc();
        }

        $stmt_user->close();
        $stmt_shipping->close();
        $conn->close();
    ?>

    <?php include '../includes/header.php'; ?>

    <div class="personal-info">
        <div class="container">
            <h2>Thông tin cá nhân</h2>
            <?php if ($user): ?>
            <div id="info-display" class="space-y-4">
                <div class="info-item">
                    <label>Tên:</label>
                    <span id="display-name"><?php echo htmlspecialchars($user['fullname'] ?? ''); ?></span>
                </div>
                <div class="info-item">
                    <label>Tuổi:</label>
                    <span id="display-age"><?php echo htmlspecialchars($user['age'] ?? ''); ?></span>
                </div>
                <div class="info-item">
                    <label>Số điện thoại:</label>
                    <span id="display-phone"><?php echo htmlspecialchars($user['phone'] ?? ''); ?></span>
                </div>
                <h3>Thông tin giao hàng</h3>
                <?php if ($shipping): ?>
                <div class="info-item">
                    <label>Địa chỉ:</label>
                    <span id="display-address"><?php echo htmlspecialchars($shipping['address'] ?? ''); ?></span>
                </div>
                <div class="info-item">
                    <label>Thành phố:</label>
                    <span id="display-city"><?php echo htmlspecialchars($shipping['city'] ?? ''); ?></span>
                </div>
                <div class="info-item">
                    <label>Quận/Huyện:</label>
                    <span id="display-district"><?php echo htmlspecialchars($shipping['district'] ?? ''); ?></span>
                </div>
                <div class="info-item">
                    <label>Mã bưu điện:</label>
                    <span id="display-postal-code"><?php echo htmlspecialchars($shipping['postal_code'] ?? ''); ?></span>
                </div>
                <div class="info-item">
                    <label>Phương thức giao hàng:</label>
                    <span id="display-shipping-method"><?php echo htmlspecialchars($shipping['shipping_method'] ?? ''); ?></span>
                </div>
                <?php endif; ?>
                <div class="text-center">
                    <button class="btn btn-edit" onclick="showEditForm()">Sửa</button>
                </div>
            </div>

            <div id="edit-form" class="edit-form">
                <form method="POST">
                    <div class="info-item">
                        <label>Tên:</label>
                        <input type="text" name="name" value="<?php echo htmlspecialchars($user['fullname'] ?? ''); ?>">
                    </div>
                    <div class="info-item">
                        <label>Tuổi:</label>
                        <input type="number" name="age" value="<?php echo htmlspecialchars($user['age'] ?? ''); ?>">
                    </div>
                    <div class="info-item">
                        <label>Số điện thoại:</label>
                        <input type="text" name="phone" value="<?php echo htmlspecialchars($user['phone'] ?? ''); ?>">
                    </div>
                    <h3>Thông tin giao hàng</h3>
                    <div class="info-item">
                        <label>Địa chỉ:</label>
                        <input type="text" name="address" value="<?php echo htmlspecialchars($shipping['address'] ?? ''); ?>">
                    </div>
                    <div class="info-item">
                        <label>Thành phố:</label>
                        <input type="text" name="city" value="<?php echo htmlspecialchars($shipping['city'] ?? ''); ?>">
                    </div>
                    <div class="info-item">
                        <label>Quận/Huyện:</label>
                        <input type="text" name="district" value="<?php echo htmlspecialchars($shipping['district'] ?? ''); ?>">
                    </div>
                    <div class="info-item">
                        <label>Mã bưu điện:</label>
                        <input type="text" name="postal_code" value="<?php echo htmlspecialchars($shipping['postal_code'] ?? ''); ?>">
                    </div>
                    <div class="info-item">
                        <label>Phương thức giao hàng:</label>
                        <select name="shipping_method">
                            <option value="standard" <?php echo ($shipping['shipping_method'] ?? 'standard') === 'standard' ? 'selected' : ''; ?>>Standard</option>
                            <option value="express" <?php echo ($shipping['shipping_method'] ?? 'standard') === 'express' ? 'selected' : ''; ?>>Express</option>
                        </select>
                    </div>
                    <div class="text-center">
                        <button type="submit" name="save" class="btn btn-save">Lưu</button>
                        <button type="button" class="btn btn-cancel" onclick="hideEditForm()">Hủy</button>
                    </div>
                </form>
            </div>
            <?php endif; ?>
        </div>
    </div>

    <script>
        function showEditForm() {
            document.getElementById('info-display').style.display = 'none';
            document.getElementById('edit-form').style.display = 'block';
        }

        function hideEditForm() {
            document.getElementById('info-display').style.display = 'block';
            document.getElementById('edit-form').style.display = 'none';
        }
    </script>
</body>
</html>