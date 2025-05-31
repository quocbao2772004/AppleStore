use product_management;
update users
set role = 'admin'
where email = 'k100iltqbao@gmail.com';
SELECT 
    u.id,
    u.name,
    u.email,
    COUNT(o.id) AS total_orders,
    SUM(o.total_price) AS total_spent
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name, u.email
ORDER BY total_spent DESC
LIMIT 10;


SELECT p.name, p.price, p.description
FROM products p 
join categories c on p.category_id = c.id
WHERE LOWER(p.name) LIKE '%iphone%' and c.name = 'iphone' and p.price < 20000000;

SELECT p.name,p.price, p.description   
FROM products p 
join categories c on p.category_id = c.id 
WHERE LOWER(p.name) LIKE '%macbook%' and c.name = 'macbook';

select p.id, p.name, p.description 
from products p
join categories c on p.category_id = c.id
where LOWER(p.name) like '%iPhone 16 pro max%' and c.name = 'case';

select name, price from products
where name like '%iphone 14 plus - 128gb%';

select p.name, p.price, p.description 
from products p
join categories c 
on p.category_id = c.id 
where p.name like '%iphone%' and c.name = "iphone";
 
select * from orders;
select * from users;
select * from reviews;

SELECT u.id, u.name, u.email, p.name AS product_name, v.rating, v.comment 
FROM users u 
JOIN reviews v ON u.id = v.user_id 
JOIN products p ON p.id = v.product_id
where v.rating>=4;

SELECT 
    u.id,
    u.name,
    u.email,
    SUM(o.total_price) AS total_spent
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name, u.email
ORDER BY total_spent DESC
LIMIT 5;

SELECT id, name, stock
FROM products
ORDER BY stock DESC
LIMIT 5;


SELECT 
    u.id AS user_id,
    u.name AS user_name,
    u.email,
    p.id AS product_id,
    p.name AS product_name,
    o.quantity,
    o.total_price,
    o.created_at
FROM orders o
JOIN users u ON o.user_id = u.id
JOIN products p ON o.product_id = p.id
WHERE DATE(o.created_at) = '2025-05-09';

SELECT 
    p.id AS product_id,
    p.name AS product_name,
    SUM(o.quantity) AS total_quantity_sold,
    SUM(o.quantity * p.price) AS total_revenue
FROM orders o
JOIN products p ON o.product_id = p.id
WHERE DATE(o.created_at) = '2025-05-09'
GROUP BY p.id, p.name
ORDER BY total_revenue DESC;

SELECT NOW() AS current_datetime;
SELECT p.id AS product_id, p.name AS product_name, p.price AS product_price, SUM(o.quantity) AS total_quantity_sold, SUM(o.quantity * p.price) AS total_revenue_for_product FROM orders o JOIN products p ON o.product_id = p.id WHERE DATE(o.created_at) = '2025-05-09' GROUP BY p.id, p.name, p.price ORDER BY total_quantity_sold DESC;
select * from orders;


DELIMITER //

CREATE TRIGGER trg_reduce_stock_after_order
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    UPDATE products
    SET stock = stock - NEW.quantity
    WHERE id = NEW.product_id;
END;
//

DELIMITER ;
select * from users;
select * from products;
select * from orders;

INSERT INTO orders (
    user_id, total_price, status, payment_method, 
    shipping_phone, shipping_name, notes, 
    product_id, quantity, created_at, shipping_address, order_group_id
)
VALUES (
    7, 28790000, 'pending', 'cash_on_delivery', 
    '0123456789', 'Charlie Brown', 'Giao hàng trước 17h chiều nay',
    121, 1, NOW(), '123 Đường ABC, Quận 1, TP.HCM', 0
);
























