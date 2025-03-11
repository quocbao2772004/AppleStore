<?php include 'config.php'?>
<?php

$category = isset($_GET['category']) ? $_GET['category'] : '';
$sort = isset($_GET['sort']) ? $_GET['sort'] : '';

$query = "SELECT * FROM products WHERE 1"; 

if (!empty($category)) {
    $query .= " AND category = :category";
}

if ($sort === "price-asc") {
    $query .= " ORDER BY price ASC";
} elseif ($sort === "price-desc") {
    $query .= " ORDER BY price DESC";
} elseif ($sort === "name-asc") {
    $query .= " ORDER BY name ASC";
}

$stmt = $pdo->prepare($query);

if (!empty($category)) {
    $stmt->bindParam(':category', $category, PDO::PARAM_STR);
}

$stmt->execute();
$products = $stmt->fetchAll(PDO::FETCH_ASSOC);
?>
