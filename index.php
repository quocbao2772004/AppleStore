<?php
require_once 'includes/functions.php';
require_once 'config/database.php';

// Get featured products
try {
    $stmt = $pdo->query("SELECT p.*, c.name as category_name 
                         FROM products p 
                         LEFT JOIN categories c ON p.category_id = c.id 
                         ORDER BY p.id DESC 
                         LIMIT 8");
    $featuredProducts = $stmt->fetchAll();
} catch (PDOException $e) {
    $featuredProducts = [];
}

// Get categories
try {
    $stmt = $pdo->query("SELECT * FROM categories ORDER BY name ASC");
    $categories = $stmt->fetchAll();
} catch (PDOException $e) {
    $categories = [];
}

// Page title
$pageTitle = 'Home';

// Include header
include 'includes/header.php';
?>

<!-- Octopus -->
<section class="hero bg-dark text-white py-5">
    <div class="container">
        <div class="row align-items-center">
            <div class="col-md-6">
                <h1 class="display-4 fw-bold">Chào mừng đến với Octopus Store</h1>
                <p class="lead">Khám phá các sản phẩm mới với giá cực kỳ ưu đãi</p>
                <a href="products.php" class="btn btn-light btn-lg">Khám phá ngay!</a>
            </div>
            <div class="col-md-6">
                <svg xmlns="http://www.w3.org/2000/svg" height="2081pt" preserveAspectRatio="xMidYMid meet" viewBox="0 0 2475 2081" width="100%" height="auto" style="max-height: 300px;">
                    <path d="m8480 20792c-39-21-79-76-169-237l-62-110-175-850-174-850-213-213c-253-255-214-230-867-554-598-297-820-420-1150-636-274-179-457-326-683-550-282-279-433-508-535-812-32-98-36-118-46-305-15-264-13-909 3-1110 53-681 100-956 212-1235 154-386 389-673 776-947 145-103 242-186 314-268 58-66 109-139 109-155 0-19-119-157-211-245-421-404-1130-844-1859-1154-738-314-1136-315-1630-2-265 167-496 416-620 666-90 181-112 266-117 456-10 306 52 578 197 866 86 171 174 294 309 436 172 179 398 331 591 397 166 56 401 75 624 50l88-10 83-73 83-72 1-200c1-285-24-449-99-655-85-229-115-521-75-700 65-284 157-379 340-350 196 31 363 120 482 257 251 289 374 682 399 1273 16 376-64 689-250 975-188 289-494 540-803 659-217 84-391 111-670 103-268-7-468-46-704-137-425-164-868-513-1186-935-351-465-620-1070-732-1645-117-600-58-1319 150-1843 274-689 838-1186 1592-1406 377-110 767-149 1307-131 701 23 973 71 1279 224 51 26 571 348 1155 714l1061 667 60 3 59 4-35-44c-215-264-435-555-507-669-141-224-199-520-173-882 30-412 117-685 329-1032 106-175 198-315 306-465 93-131 105-146 353-457 232-291 523-681 572-766 96-170 153-342 172-527 19-183-10-338-92-503-61-121-113-193-203-282-114-112-212-160-367-179l-45-5-12 277c-24 556-59 835-142 1124-142 495-422 877-768 1048-469 231-1318 143-2021-209-310-156-551-329-792-570-215-216-384-450-509-706-147-302-210-581-210-928 0-537 155-892 571-1307 552-550 1357-868 2296-906 179-8 264 1 439 46 61 16 156 32 211 36l100 7 8-69c21-198 84-511 117-576 25-51 75-99 143-138 70-40 121-91 136-137 6-21 9-67 7-107-8-118-55-203-205-368-130-143-188-251-199-374l-6-70 98 8c127 9 232 37 342 89 117 55 210 87 311 104 105 19 340 20 364 2 9-6 36-40 60-75l42-63 177-84c542-259 982-374 1488-392 430-15 822 66 1215 252 516 242 979 640 1343 1152 185 260 321 533 405 813 50 165 65 254 71 430 4 85 11 226 16 313 5 97 6 249 0 395-21 552-72 795-410 1957-352 1211-396 1422-407 1942-16 780 122 1424 392 1828 126 188 251 307 400 381 142 69 306 101 470 91 246-16 396-112 502-322 28-55 62-132 77-171 42-111 87-301 92-389 21-345 36-761 40-1095 6-475 16-567 100-920 192-806 550-1533 1027-2085 123-143 356-370 483-471 258-206 530-347 835-433 97-27 122-30 354-37 323-11 868-8 1110 6 105 6 309 22 455 35 472 43 598 49 1025 49 531 1 661-11 891-85 169-54 286-122 386-225 103-107 137-167 169-302 29-119 23-350-11-457-86-270-310-474-605-550-168-44-344-38-513 17-110 35-160 63-195 110-56 76-59 138-17 362 56 298 40 398-84 521s-232 161-431 152c-308-14-423-123-480-451-20-116-20-347 0-462 44-251 168-483 369-692 232-240 513-400 855-486 490-124 1016-58 1375 172 319 204 596 571 735 975 83 240 114 444 114 737-1 324-42 583-130 805-164 418-555 753-1093 940-288 99-590 164-1011 215-915 111-1453 217-1880 371-642 230-995 487-1304 949-306 458-473 917-525 1439-13 129-13 633 0 763 16 167 66 280 140 318 41 21 110 27 110 10 0-5 5-10 11-10s66-51 133-113c474-441 939-784 1482-1094 518-296 1305-683 1959-963 199-86 218-101 231-188 10-67-10-198-44-286-17-44-59-116-100-173-77-109-96-142-123-220-64-186-34-456 60-545 50-47 104-61 211-56 117 6 182 38 275 133 101 104 169 204 291 430 113 211 148 267 184 300 22 20 40 20 1144 25 1225 6 1162 3 1396 66 245 66 547 225 770 403 424 341 716 834 807 1366 23 135 23 479-1 658-54 416-181 773-385 1077-267 397-595 654-1011 790-240 79-461 111-764 111-553 0-901-111-1268-403-273-217-537-609-717-1063-63-160-232-673-286-870-54-198-62-217-97-229-51-18-116 11-198 89-96 91-159 141-535 430-521 400-661 517-978 815l-197 185 38 7c20 4 98 19 172 34 488 93 1141 300 1655 524 138 60 502 241 620 308 374 212 677 436 953 706 222 216 357 421 437 659 72 216 68 109 75 1762 6 1325 9 1500 23 1585 54 303 140 492 302 656 97 98 169 141 273 163 76 16 202 14 282-5l69-15 243-222c323-294 445-414 533-522 290-357 409-694 431-1217 7-169-2-240-40-323-33-73-77-111-291-253-387-256-436-306-466-479-15-86-5-241 20-323 35-112 83-158 193-186 89-23 342-15 450 14 172 47 323 137 468 282 352 350 560 1013 511 1624-62 762-403 1547-891 2050-330 340-711 561-1105 641-305 62-734 46-1054-40-288-77-514-208-726-420-418-417-675-963-824-1745-70-369-101-793-121-1670-12-492-16-525-85-677-119-260-374-472-720-595-289-103-596-152-965-153-245 0-323 13-538 86-350 121-516 258-588 484-14 44-28 116-31 161-5 75-4 83 21 120 51 78 207 200 840 654 374 270 558 423 787 657 156 159 222 240 336 410 232 349 337 666 363 1108 27 435-62 811-254 1079-103 143-483 555-754 815-157 150-175 172-200 231-23 55-27 79-26 150 3 186 61 363 170 510 65 89 261 288 364 369 101 81 269 198 438 305 152 98 200 139 236 207 25 44 29 64 29 123-1 115-36 176-127 223-43 22-72 26-240 39-744 54-1250-207-1547-797-204-408-259-1002-128-1394 42-125 178-397 299-600 249-414 314-562 340-775 35-293-33-567-205-815-65-94-325-352-453-449-483-367-1167-637-1877-742-133-20-529-25-598-8l-37 9 72 55c102 77 257 235 295 300 60 101 77 190 77 400 0 346-34 411-385 721-86 76-146 136-142 143 4 6 16 25 28 41 12 17 37 58 55 92 17 34 52 85 76 113s44 62 44 75c0 20 5 22 41 21 52-1 69 21 69 87 0 70-22 107-66 107-39 0-59-36-59-106v-64h-358-358l18 23c433 535 764 1000 893 1257 89 177 162 402 196 605 23 134 22 418 0 579-44 310-147 577-324 842-228 340-514 583-932 793-397 198-799 307-1270 342-587 43-1213-130-1757-488-522-342-897-850-1003-1354-91-439-24-916 194-1365 120-246 343-627 548-930 85-127 88-134 88-188v-56h-390-390v-46c0-41 9-59 95-186 52-78 95-149 95-159 0-11-45-56-112-112-244-203-393-403-443-592-58-223-27-507 73-661 56-85 170-203 291-300 67-54 110-96 118-117 13-30 12-33-9-51-41-34-148-77-418-169l-265-90-185-8c-477-19-644-21-865-10-695 37-1126 124-1483 301-275 137-459 291-624 522-211 295-301 620-302 1088-1 200 2 235 22 313 61 243 150 389 380 620 203 206 452 384 992 712 318 193 481 305 710 489 368 296 641 668 739 1006 50 172 63 266 68 506 7 297-12 492-122 1214-19 124-37 266-41 315l-7 90-61 60c-80 80-187 155-228 161-21 3-45-2-68-14zm-1626-10488c26-25 21-100-9-129-29-30-75-33-98-7-26 28-33 97-13 127 13 20 24 25 61 25 26 0 50-6 59-16zm2170-951c23-386 106-889 221-1338 169-664 360-1185 795-2170 95-214 219-502 277-640 58-137 134-320 170-405 194-456 312-887 343-1252 13-150 6-278-30-568-150-1181-565-1833-1291-2030-161-44-238-52-506-57-145-3-263-8-263-12 0-3-13-21-28-39l-28-34-223 57c-523 132-724 236-809 417-16 34-47 130-67 213-21 82-61 224-90 315-64 198-227 901-259 1115l-15 100 42 42c32 31 145 95 472 266 426 222 554 294 690 390 269 191 430 368 549 605 118 235 166 486 166 869 0 398-61 667-220 978-127 247-264 463-482 763-219 301-408 592-492 760-98 195-147 399-150 617 0 90 4 160 13 195 66 266 362 554 792 771 151 76 402 189 409 184 4-2 10-53 14-112zm13116 88c175-41 305-100 439-202 205-155 324-369 367-660 31-215 6-424-69-577-124-249-325-438-622-582-314-153-567-194-955-156-364 36-554 90-649 185-52 52-7 348 105 696 124 381 308 735 507 971 170 203 308 300 492 348 45 12 302-4 385-23zm-16646-3847c167-57 332-364 481-900 82-295 155-642 155-738 0-108-47-184-143-232-107-55-366-92-702-101-472-12-782 33-963 138-84 50-188 158-223 233-58 125-75 313-44 502 50 312 246 609 549 836 169 126 408 231 586 257 41 6 86 13 100 15 65 9 160 5 204-10z" transform="matrix(.1 0 0 -.1 0 2081)" vector-effect="non-scaling-stroke" fill="#000000" stroke="none" stroke-width="2"/>
                </svg>
            </div>
        </div>
    </div>
</section>

<!-- Categories Section -->
<section class="py-5 bg-light">
    <div class="container">
        <h2 class="text-center mb-4">Khám phá tất cả sản phẩm </h2>
        <div class="row">
            <?php foreach ($categories as $category): ?>
            <div class="col-md-3 col-sm-6 mb-4">
                <a href="products.php?category=<?php echo $category['id']; ?>" class="text-decoration-none">
                    <div class="card h-100 shadow-sm">
                        <div class="card-body text-center">                                                                                                                                              
                            <i class="fas fa-folder fa-3x mb-3 text-green"></i>
                            <h5 class="card-title text-dark"><?php echo ucfirst(strtolower(htmlspecialchars($category['name']))); ?>
                            </h5>
                        </div>
                    </div>
                </a>
            </div>
            <?php endforeach; ?>
            <?php if (empty($categories)): ?>
            <div class="col-12 text-center">
                <p>No categories found</p>
            </div>
            <?php endif; ?>
        </div>
    </div>
</section>

<!-- Featured Products Section -->
<section class="py-5">
    <div class="container">
        <h2 class="text-center mb-4">Tai nghe thời thượng</h2>
        <div class="row">
            <?php foreach ($featuredProducts as $product): ?>
            <div class="col-md-3 col-sm-6 mb-4">
                <div class="card h-100 shadow-sm">
                    <div class="product-img-container" style="height: 200px; overflow: hidden;">
                        <?php if (!empty($product['image'])): ?>
                            <img src="uploads/products/<?php echo $product['image']; ?>" class="card-img-top" alt="<?php echo htmlspecialchars($product['name']); ?>" style="width: 100%; height: 100%; object-fit: contain;">
                        <?php else: ?>
                            <img src="assets/images/no-image.jpg" class="card-img-top" alt="No Image" style="width: 100%; height: 100%; object-fit: contain;">
                        <?php endif; ?>
                    </div>
                    <div class="card-body">
                        <h5 class="card-title"><?php echo htmlspecialchars($product['name']); ?></h5>
                        <p class="card-text text-muted">
                            <?php echo ucfirst(strtolower(htmlspecialchars($product['category_name'] ?? 'Uncategorized'))); ?>
                        </p>

                        <p class="card-text fw-bold"><?php echo number_format($product['price'], 0) . " VNĐ"; ?></p>
                        <div class="d-flex justify-content-between">
                            <a href="product-detail.php?slug=<?php echo $product['slug']; ?>" class="btn btn-outline-primary">Xem chi tiết</a>
                            <form action="cart.php" method="POST">
                                <input type="hidden" name="product_id" value="<?php echo $product['id']; ?>">
                                <input type="hidden" name="action" value="add_to_cart">
                                <input type="hidden" name="quantity" value="1">
                                <button type="submit" class="btn btn-primary" <?php echo ($product['stock'] <= 0) ? 'disabled' : ''; ?>>
                                    <i class="fas fa-cart-plus"></i>
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <?php endforeach; ?>
            <?php if (empty($featuredProducts)): ?>
            <div class="col-12 text-center">
                <p>No products found</p>
            </div>
            <?php endif; ?>
        </div>
        <div class="text-center mt-4">
            <a href="products.php" class="btn btn-primary">Xem tất cả sản phẩm </a>
        </div>
    </div>
</section>

<!-- Features Section -->
<section class="py-5 bg-light">
    <div class="container">
        <div class="row text-center">
            <div class="col-md-4 mb-4">
                <div class="card h-100 border-0 bg-transparent">
                    <div class="card-body">
                        <i class="fas fa-truck fa-3x text-primary mb-3"></i>
                        <h4>Giao hàng miễn phí tận nơi</h4>
                        <p>Với hóa đơn trên 1.000.000 VNĐ</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4 mb-4">
                <div class="card h-100 border-0 bg-transparent">
                    <div class="card-body">
                        <i class="fas fa-undo fa-3x text-primary mb-3"></i>
                        <h4>Bảo hành dễ dàng</h4>
                        <p>Sửa chữa sản phẩm tối đa 30 ngày</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4 mb-4">
                <div class="card h-100 border-0 bg-transparent">
                    <div class="card-body">
                        <i class="fas fa-lock fa-3x text-primary mb-3"></i>
                        <h4>Thông tin bảo mật</h4>
                        <p>Thông tin tài khoản được mã hóa nhiều lớp</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>

<?php include 'includes/footer.php'; ?>