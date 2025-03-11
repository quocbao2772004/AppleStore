<?php
include '../config/config.php';


$items_per_page = 9;


$page = isset($_GET['page']) ? (int)$_GET['page'] : 1;
$offset = ($page - 1) * $items_per_page;


$category = isset($_GET['category']) ? $_GET['category'] : '';
$sort = isset($_GET['sort']) ? $_GET['sort'] : '';

try {
 
    $count_query = "SELECT COUNT(*) FROM products";
    if ($category) {
        $count_query .= " WHERE category = :category";
    }
    $count_stmt = $pdo->prepare($count_query);
    if ($category) {
        $count_stmt->bindParam(':category', $category);
    }
    $count_stmt->execute();
    $total_items = $count_stmt->fetchColumn();
    $total_pages = ceil($total_items / $items_per_page);

    $query = "SELECT * FROM products";
    $conditions = [];

    if ($category) {
        $conditions[] = "category = :category";
    }

    if (!empty($conditions)) {
        $query .= " WHERE " . implode(" AND ", $conditions);
    }

    
    if ($sort) {
        switch ($sort) {
            case 'price-asc':
                $query .= " ORDER BY CONVERT(REPLACE(price, '.', ''), DECIMAL(10,2)) ASC";
                break;
            case 'price-desc':
                $query .= " ORDER BY CONVERT(REPLACE(price, '.', ''), DECIMAL(10,2)) DESC";
                break;
            case 'name-asc':
                $query .= " ORDER BY name ASC";
                break;
        }
    }
    
    $query .= " LIMIT :limit OFFSET :offset";

    $stmt = $pdo->prepare($query);
    if ($category) {
        $stmt->bindParam(':category', $category);
    }
    $stmt->bindValue(':limit', $items_per_page, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $products = $stmt->fetchAll(PDO::FETCH_ASSOC);


    $stmt = $pdo->prepare($query);
    if ($category) {
        $stmt->bindParam(':category', $category);
    }
    $stmt->bindValue(':limit', $items_per_page, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    $products = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    echo '<p>Lỗi: ' . $e->getMessage() . '</p>';
}

function getProductById($id) {
    global $pdo; 
    try {
        $query = "SELECT * FROM products WHERE id = :id LIMIT 1";
        $stmt = $pdo->prepare($query);
        $stmt->bindParam(':id', $id, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetch(PDO::FETCH_ASSOC); 
    } catch (PDOException $e) {
        echo '<p>Lỗi khi lấy sản phẩm: ' . $e->getMessage() . '</p>';
        return false;
    }
}
?>