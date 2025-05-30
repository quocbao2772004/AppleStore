<?php
require_once '../includes/functions.php';
require_once '../includes/auth.php';
require_once '../config/database.php';

// Check if user is logged in and is admin
if (!isLoggedIn() || !isAdmin()) {
    setFlashMessage('error', 'Bạn không có quyền truy cập trang này');
    redirect('../index.php');
}

// Get current user data
$user_id = $_SESSION['user_id'];
$user = getCurrentUser();

if (!$user) {
    setFlashMessage('error', 'Không tìm thấy người dùng');
    redirect('index.php');
}

// Thống kê dữ liệu
try {
    // 10 sản phẩm được order nhiều nhất
    $sql_ordered = "
        SELECT p.id, p.name, COALESCE(SUM(o.quantity), 0) as total_ordered
        FROM products p
        LEFT JOIN orders o ON p.id = o.product_id
        GROUP BY p.id, p.name
        ORDER BY total_ordered DESC
        LIMIT 10
    ";
    $stmt_ordered = $pdo->prepare($sql_ordered);
    $stmt_ordered->execute();
    $most_ordered = $stmt_ordered->fetchAll(PDO::FETCH_ASSOC);

    // 10 sản phẩm tồn kho nhiều nhất
    $sql_stock = "
        SELECT id, name, stock
        FROM products
        ORDER BY stock DESC
        LIMIT 10
    ";
    $stmt_stock = $pdo->prepare($sql_stock);
    $stmt_stock->execute();
    $most_stock = $stmt_stock->fetchAll(PDO::FETCH_ASSOC);

    // Dữ liệu cho biểu đồ (top 10 order và tồn kho)
    $sql_chart = "
        SELECT p.id, p.name, p.stock, COALESCE(SUM(o.quantity), 0) as total_ordered
        FROM products p
        LEFT JOIN orders o ON p.id = o.product_id
        GROUP BY p.id, p.name, p.stock
        ORDER BY total_ordered DESC, stock DESC
        LIMIT 10
    ";
    $stmt_chart = $pdo->prepare($sql_chart);
    $stmt_chart->execute();
    $chart_data = $stmt_chart->fetchAll(PDO::FETCH_ASSOC);

    $labels = array_column($chart_data, 'name');
    $ordered_data = array_column($chart_data, 'total_ordered');
    $stock_data = array_column($chart_data, 'stock');
} catch (PDOException $e) {
    setFlashMessage('error', 'Lỗi truy vấn dữ liệu: ' . $e->getMessage());
}

// Page title
$pageTitle = 'Thống Kê - Admin';

// Include header
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <!-- Sidebar -->
        <?php include 'includes/sidebar.php'; ?>
        
        <!-- Main content -->
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">Thống Kê Sản Phẩm</h1>
            </div>
            
            <div class="row">
                <!-- 10 sản phẩm được order nhiều nhất -->
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">10 Sản Phẩm Được Order Nhiều Nhất</h5>
                        </div>
                        <div class="card-body">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th>Tên Sản Phẩm</th>
                                        <th>Số Lượng Order</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($most_ordered as $item): ?>
                                        <tr>
                                            <td><?php echo htmlspecialchars($item['name']); ?></td>
                                            <td><?php echo $item['total_ordered']; ?></td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- 10 sản phẩm tồn kho nhiều nhất -->
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">10 Sản Phẩm Tồn Kho Nhiều Nhất</h5>
                        </div>
                        <div class="card-body">
                            <table class="table table-bordered">
                                <thead>
                                    <tr>
                                        <th>Tên Sản Phẩm</th>
                                        <th>Số Lượng Tồn Kho</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($most_stock as $item): ?>
                                        <tr>
                                            <td><?php echo htmlspecialchars($item['name']); ?></td>
                                            <td><?php echo $item['stock']; ?></td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Biểu đồ -->
                <div class="col-12 mb-4">
                    <div class="card">
                        <div class="card-header bg-primary text-white">
                            <h5 class="mb-0">Biểu Đồ Thống Kê Top 10 Sản Phẩm</h5>
                        </div>
                        <div class="card-body">
                            <div class="chart-container" style="position: relative; height:500px;">
                                <canvas id="inventoryChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<?php include 'includes/footer.php'; ?>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script>
    const ctx = document.getElementById('inventoryChart').getContext('2d');
    const inventoryChart = new Chart(ctx, {
        type: 'bar', 
        data: {
            labels: <?php echo json_encode($labels); ?>,
            datasets: [
                {
                    label: 'Số Lượng Order',
                    data: <?php echo json_encode($ordered_data); ?>,
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.8
                },
                {
                    label: 'Số Lượng Tồn Kho',
                    data: <?php echo json_encode($stock_data); ?>,
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.8
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'x', // Giữ trục X là tên sản phẩm
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Tên Sản Phẩm',
                        font: { size: 14 }
                    },
                    ticks: {
                        font: { size: 12 },
                        maxRotation: 45,
                        minRotation: 45 // Xoay nhãn nếu tên sản phẩm dài
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Số Lượng',
                        font: { size: 14 }
                    },
                    ticks: {
                        font: { size: 12 }
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { size: 14 },
                        boxWidth: 20
                    }
                },
                title: {
                    display: true,
                    text: 'Thống Kê Top 10 Sản Phẩm (Order và Tồn Kho)',
                    font: { size: 16, weight: 'bold' }
                },
                tooltip: {
                    bodyFont: { size: 12 },
                    titleFont: { size: 14 }
                }
            }
        }
    });
</script>
<style>
    .chart-container {
        position: relative;
        height: 500px;
        width: 100%;
        margin: 0 auto;
    }
    .card-header {
        font-size: 1.1rem;
    }
    table {
        font-size: 0.95rem;
    }
</style>