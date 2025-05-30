use product_management;
select * from users;
select * from products;
select * from categories;
select * from orders;


INSERT INTO categories (name, slug) VALUES
('iphone', 'iphone'),
('macbook', 'macbook'),
('macmini', 'macmini'),
('macstudio', 'macstudio'),
('ipad', 'ipad'),
('case', 'case'),
('watch', 'watch'),
('airpod', 'airpod');
-- DROP PROCEDURE IF EXISTS CreateSlug;




-- Chèn dữ liệu vào products
INSERT INTO products (name, slug, description, price, stock, image, category_id, created_at)
VALUES
('iPhone 15 Pro Max - 256gb', 'iphone-15-pro-max-256gb', 'iPhone 15 Pro Max - 256GB: Chip A17 Pro, màn hình Super Retina XDR 6.7 inch, camera chính 48MP với zoom quang học 5x, hỗ trợ USB-C, hệ điều hành iOS 17, chống nước IP68.', 28790000, 100, '../assets/images/iphone/0028064_iphone-15-pro-max-256gb_240.png', 1, NOW()),
('iPhone 16 Pro Max - 256gb', 'iphone-16-pro-max-256gb', 'iPhone 16 Pro Max - 256GB: Chip A18 Bionic, màn hình Super Retina XDR 6.7 inch, camera chính 48MP với zoom quang học 10x, hỗ trợ MagSafe, hệ điều hành iOS 18, pin 4400mAh.', 30990000, 120, '../assets/images/iphone/0029155_iphone-16-pro-max-256gb_240.png', 1, NOW()),
('iPhone 14 - 128gb', 'iphone-14-128gb', 'iPhone 14 - 128GB: Chip A15 Bionic, màn hình Super Retina XDR 6.1 inch, camera kép 12MP, hỗ trợ 5G, hệ điều hành iOS 16, thiết kế notch.', 12990000, 10, '../assets/images/iphone/0009181_iphone-14-128gb_240.png', 1, NOW()),
('iPhone 14 Plus - 128gb', 'iphone-14-plus-128gb', 'iPhone 14 Plus - 128GB: Chip A15 Bionic, màn hình Super Retina XDR 6.7 inch, camera kép 12MP, pin lâu hơn iPhone 14, hệ điều hành iOS 16, chống nước IP68.', 18990000, 12, '../assets/images/iphone/0009495_iphone-14-plus-128gb_240.png', 1, NOW()),
('iPhone 15 - 128gb', 'iphone-15-128gb', 'iPhone 15 - 128GB: Chip A16 Bionic, màn hình Super Retina XDR 6.1 inch, camera chính 48MP, hỗ trợ USB-C, hệ điều hành iOS 17, thiết kế Dynamic Island.', 15990000, 17, '../assets/images/iphone/0024431_iphone-15-128gb_240.png', 1, NOW()),
('iPhone 16 Plus - 128gb', 'iphone-16-plus-128gb', 'iPhone 16 Plus - 128GB: Chip A18 Bionic, màn hình Super Retina XDR 6.7 inch, camera chính 48MP, hỗ trợ MagSafe, hệ điều hành iOS 18, pin 4500mAh.', 22590000, 40, '../assets/images/iphone/0030772_iphone-16-plus-128gb_240.png', 1, NOW()),
('iPhone 16 - 128gb', 'iphone-16-128gb', 'iPhone 16 - 128GB: Chip A18 Bionic, màn hình Super Retina XDR 6.1 inch, camera chính 48MP, hỗ trợ USB-C, hệ điều hành iOS 18, thiết kế mỏng nhẹ.', 19290000, 50, '../assets/images/iphone/0030771_iphone-16-128gb_240.png', 1, NOW()),
('iPhone 16 Pro - 256gb', 'iphone-16-pro-256gb', 'iPhone 16 Pro - 256GB: Chip A18 Bionic, màn hình Super Retina XDR 6.1 inch, camera chính 48MP với zoom quang học 5x, hỗ trợ ProRAW, hệ điều hành iOS 18.', 25390000, 32, '../assets/images/iphone/0029553_iphone-16-pro-256gb_240.png', 1, NOW()),
('iPhone 13 - 128gb', 'iphone-13-128gb', 'iPhone 13 - 128GB: Chip A15 Bionic, màn hình Super Retina XDR 6.1 inch, camera kép 12MP, hỗ trợ 5G, hệ điều hành iOS 15, chống nước IP68.', 11790000, 57, '../assets/images/iphone/0024430_iphone-13-128gb_240.png', 1, NOW()),
('iPhone 16e - 256gb', 'iphone-16e-256gb', 'iPhone 16e - 256GB: Chip A18 Bionic, màn hình Super Retina XDR 6.1 inch, camera chính 48MP, phiên bản tiết kiệm năng lượng, hệ điều hành iOS 18.', 19690000, 32, '../assets/images/iphone/0034911_iphone-16e-256gb_240.png', 1, NOW()),
('MacBook Air M2 - 16gb ram - 256gb ssd', 'macbook-air-m2-16gb-ram-256gb-ssd', 'MacBook Air M2 - 16GB RAM - 256GB SSD: Chip M2 8-core CPU, 10-core GPU, màn hình Retina 13.6 inch, bàn phím Magic Keyboard, macOS Ventura, pin 18 giờ.', 23890000, 15, '../assets/images/mac/0034123_macbook-air-m2-13-inch-10-core-gpu-16gb-ram-256gb-ssd_240.jpeg', 2, NOW()),
('MacBook Air M3 - 8gb ram - 256gb ssd', 'macbook-air-m3-8gb-ram-256gb-ssd', 'MacBook Air M3 - 8GB RAM - 256GB SSD: Chip M3 8-core CPU, 10-core GPU, màn hình Retina 13.6 inch, hỗ trợ Wi-Fi 6E, macOS Sonoma, trọng lượng 1.24kg.', 26390000, 8, '../assets/images/mac/0034122_macbook-air-m3-13-inch-8gb-ram-256gb-ssd_240.jpeg', 2, NOW()),
('MacBook Pro 14 inch M4 - 16gb ram - 512gb ssd', 'macbook-pro-14-inch-m4-16gb-ram-512gb-ssd', 'MacBook Pro 14 inch M4 - 16GB RAM - 512GB SSD: Chip M4 10-core CPU, 10-core GPU, màn hình Liquid Retina XDR 14.2 inch, cổng Thunderbolt 4, macOS Sequoia.', 38990000, 9, '../assets/images/mac/0034125_macbook-pro-14-inch-m4-2024-16gb-ram-10-core-gpu-10-core-cpu-512gb-ssd_240.jpeg', 2, NOW()),
('MacBook Air 15 inch M4 - 24gb ram - 512gb ssd', 'macbook-air-15-inch-m4-24gb-ram-512gb-ssd', 'MacBook Air 15 inch M4 - 24GB RAM - 512GB SSD: Chip M4 10-core CPU, 10-core GPU, màn hình Retina 15.3 inch, hỗ trợ 2 màn hình ngoài, macOS Sequoia.', 41990000, 12, '../assets/images/mac/0036240_macbook-air-15-inch-m4-10-core-gpu-24gb-ram-512gb-ssd_240.jpeg', 2, NOW()),
('MacBook Pro 16 inch M3 - 36gb ram - 1tb ssd', 'macbook-pro-16-inch-m3-36gb-ram-1tb-ssd', 'MacBook Pro 16 inch M3 - 36GB RAM - 1TB SSD: Chip M3 Max 14-core CPU, 30-core GPU, màn hình Liquid Retina XDR 16.2 inch, pin 22 giờ, macOS Sonoma.', 63490000, 23, '../assets/images/mac/0022693_macbook-pro-16-inch-m3-max-2023-36gb-ram-30-core-gpu-1tb-ssd_240.jpeg', 2, NOW()),
('MacBook Pro 14 inch M3 - 18gb ram - 1tb ssd', 'macbook-pro-14-inch-m3-18gb-ram-1tb-ssd', 'MacBook Pro 14 inch M3 - 18GB RAM - 1TB SSD: Chip M3 Pro 12-core CPU, 18-core GPU, màn hình Liquid Retina XDR 14.2 inch, cổng HDMI, macOS Sonoma.', 26390000, 11, '../assets/images/mac/0022714_macbook-pro-14-inch-m3-pro-2023-18gb-ram-18-core-gpu-1tb-ssd_240.jpeg', 2, NOW()),
('MacBook Pro 16 inch M3 Max - 48gb ram - 1tb ssd', 'macbook-pro-16-inch-m3-max-48gb-ram-1tb-ssd', 'MacBook Pro 16 inch M3 Max - 48GB RAM - 1TB SSD: Chip M3 Max 16-core CPU, 40-core GPU, màn hình Liquid Retina XDR 16.2 inch, hỗ trợ 8K, macOS Sonoma.', 99490000, 21, '../assets/images/mac/0022735_macbook-pro-16-inch-m3-max-2023-48gb-ram-40-core-gpu-1tb-ssd_240.jpeg', 2, NOW()),
('MacBook Air M1 2020 - 8gb ram - 256gb ssd', 'macbook-air-m1-2020-8gb-ram-256gb-ssd', 'MacBook Air M1 2020 - 8GB RAM - 256GB SSD: Chip M1 8-core CPU, 7-core GPU, màn hình Retina 13.3 inch, macOS Big Sur, pin 18 giờ.', 16990000, 12, '../assets/images/mac/0034121_macbook-air-m1-2020-8gb-ram-256gb-ssd_240.jpeg', 2, NOW()),
('Mac Mini M2 - 8gb ram - 256gb ssd', 'mac-mini-m2-8gb-ram-256gb-ssd', 'Mac Mini M2 - 8GB RAM - 256GB SSD: Chip M2 8-core CPU, 10-core GPU, hỗ trợ 2 màn hình 6K, cổng Thunderbolt 4, macOS Ventura.', 14950000, 6, '../assets/images/mac/0011564_mac-mini-m2-10-core-gpu-8gb-ram-256gb-ssd_240.jpeg', 3, NOW()),
('Mac Mini M2 - 8gb ram - 512gb ssd', 'mac-mini-m2-8gb-ram-512gb-ssd', 'Mac Mini M2 - 8GB RAM - 512GB SSD: Chip M2 8-core CPU, 10-core GPU, lưu trữ nhanh hơn, cổng HDMI 2.0, macOS Ventura.', 19690000, 9, '../assets/images/mac/0011572_mac-mini-m2-10-core-gpu-8gb-ram-512gb-ssd_240.jpeg', 3, NOW()),
('Mac Mini M4', 'mac-mini-m4', 'Mac Mini M4: Chip M4 10-core CPU, 10-core GPU, thiết kế nhỏ gọn, hỗ trợ Wi-Fi 6E, macOS Sequoia.', 14990000, 8, '../assets/images/mac/0031669_mac-mini-m4_240.jpeg', 3, NOW()),
('Mac Mini Pro M4', 'mac-mini-pro-m4', 'Mac Mini Pro M4: Chip M4 Pro 12-core CPU, 16-core GPU, hiệu năng cao, cổng Ethernet 10Gb, macOS Sequoia.', 19690000, 13, '../assets/images/mac/0031685_mac-mini-m4-pro_240.jpeg', 3, NOW()),
('Mac Studio M4 Max', 'mac-studio-m4-max', 'Mac Studio M4 Max: Chip M4 Max 12-core CPU, 32-core GPU, hỗ trợ 4 màn hình 6K, cổng Thunderbolt 4, macOS Sequoia.', 57990000, 14, '../assets/images/mac/0036285_mac-studio-m4-max_240.jpeg', 4, NOW()),
('Mac Studio M3 Ultra', 'mac-studio-m3-ultra', 'Mac Studio M3 Ultra: Chip M3 Ultra 24-core CPU, 60-core GPU, hiệu năng vượt trội, hỗ trợ 8K, macOS Sonoma.', 99999000, 4, '../assets/images/mac/0036294_mac-studio-m3-ultra_240.jpeg', 4, NOW()),
('Mac Studio M2 Max', 'mac-studio-m2-max', 'Mac Studio M2 Max: Chip M2 Max 12-core CPU, 30-core GPU, cổng HDMI 2.1, macOS Ventura.', 55990000, 8, '../assets/images/mac/0018096_mac-studio-m2-max_240.jpeg', 4, NOW()),
('Mac Studio M2 Ultra', 'mac-studio-m2-ultra', 'Mac Studio M2 Ultra: Chip M2 Ultra 24-core CPU, 60-core GPU, hiệu năng chuyên nghiệp, macOS Ventura.', 99999000, 9, '../assets/images/mac/0018085_mac-studio-m2-ultra_240.jpeg', 4, NOW()),
('Mac Studio M1 Ultra', 'mac-studio-m1-ultra', 'Mac Studio M1 Ultra: Chip M1 Ultra 20-core CPU, 48-core GPU, hỗ trợ 4 màn hình 6K, macOS Monterey.', 99000000, 20, '../assets/images/mac/0000806_mac-studio-m1-ultra_240.png', 4, NOW()),
('Mac Studio M1 Max', 'mac-studio-m1-max', 'Mac Studio M1 Max: Chip M1 Max 10-core CPU, 24-core GPU, thiết kế nhỏ gọn, macOS Monterey.', 49990000, 13, '../assets/images/mac/0010612_mac-studio-m1-max_240.webp', 4, NOW()),
('iPad Mini 6', 'ipad-mini-6', 'iPad Mini 6: Chip A15 Bionic, màn hình Liquid Retina 8.3 inch, hỗ trợ Apple Pencil 2, iPadOS 15, cổng USB-C.', 10590000, 4, '../assets/images/ipad/0000593_ipad-mini-6_240.png', 5, NOW()),
('iPad Gen 9', 'ipad-gen-9', 'iPad Gen 9: Chip A13 Bionic, màn hình Retina 10.2 inch, hỗ trợ Apple Pencil 1, iPadOS 15, pin 10 giờ.', 6890000, 7, '../assets/images/ipad/0006205_ipad-gen-9-102-inch-wifi-64gb_240.png', 5, NOW()),
('iPad Gen 10', 'ipad-gen-10', 'iPad Gen 10: Chip A14 Bionic, màn hình Liquid Retina 10.9 inch, hỗ trợ Apple Pencil 2, iPadOS 16, thiết kế mới.', 9490000, 8, '../assets/images/ipad/0009725_ipad-gen-10-th-109-inch-wifi-64gb_240.png', 5, NOW()),
('iPad Air M3 11 inch', 'ipad-air-m3-11-inch', 'iPad Air M3 11 inch: Chip M3 8-core CPU, 10-core GPU, màn hình Liquid Retina 11 inch, hỗ trợ Magic Keyboard, iPadOS 17.', 16990000, 3, '../assets/images/ipad/0035054_ipad-air-m3-11-inch-wi-fi_240.png', 5, NOW()),
('iPad Air M3 13 inch', 'ipad-air-m3-13-inch', 'iPad Air M3 13 inch: Chip M3 8-core CPU, 10-core GPU, màn hình Liquid Retina 13 inch, cổng USB-C, iPadOS 17.', 22490000, 6, '../assets/images/ipad/0035136_ipad-air-m3-13-inch-wi-fi_240.png', 5, NOW()),
('Tiger Magnetic Case for Iphone 16 Series', 'tiger-magnetic-case-for-iphone-16-series', 'Tiger Magnetic Case for iPhone 16 Series: Ốp lưng từ tính, tương thích MagSafe, bảo vệ chống sốc, thiết kế mỏng nhẹ.', 10000, 20, '../assets/images/case/0034311_op-lung-tiger-magnetic-phone-case-iphone-16-series_240.jpeg', 6, NOW()),
('Mipow MagSafe for Iphone 16 Plus', 'mipow-magsafe-for-iphone-16-plus', 'Mipow MagSafe for iPhone 16 Plus: Ốp lưng MagSafe cao cấp, chất liệu silicon, hỗ trợ sạc không dây, chống trầy xước.', 390000, 20, '../assets/images/case/0034314_op-lung-mipow-magsafe-case-for-iphone-16-iphone-16-plus_240.jpeg', 6, NOW()),
('Apple Watch Series 7 GPS', 'apple-watch-series-7-gps', 'Apple Watch Series 7 GPS: Chip S7, màn hình Retina Always-On 41mm/45mm, cảm biến SpO2, watchOS 8, chống nước 50m.', 7990000, 20, '../assets/images/watch/0001025_apple-watch-series-7-nhom-gps_240.png', 7, NOW()),
('Apple Watch SE 2023 GPS', 'apple-watch-se-2023-gps', 'Apple Watch SE 2023 GPS: Chip S8, màn hình Retina 40mm/44mm, theo dõi nhịp tim, watchOS 9, pin 18 giờ.', 5890000, 20, '../assets/images/watch/0022276_apple-watch-se-2023-gps-sport-loop_240.jpeg', 7, NOW()),
('Apple Watch SE 2023 GPS + Cellular Sport', 'apple-watch-se-2023-gps-cellular-sport', 'Apple Watch SE 2023 GPS + Cellular Sport: Chip S8, màn hình Retina 40mm/44mm, kết nối Cellular, watchOS 9.', 7390000, 20, '../assets/images/watch/0022328_apple-watch-se-2023-gps-cellular-sport-band-size-sm_240.png', 7, NOW()),
('Apple Watch Series 10 Allumium GPS', 'apple-watch-series-10-allumium-gps', 'Apple Watch Series 10 Aluminum GPS: Chip S10, màn hình Retina Always-On 42mm/46mm, cảm biến nhiệt độ, watchOS 10.', 10690000, 20, '../assets/images/watch/0029160_apple-watch-series-10-nhom-gps-42mm-sport-band_240.jpeg', 7, NOW()),
('Apple Watch Series 10 Allumium GPS + Cellular Sport', 'apple-watch-series-10-allumium-gps-cellular-sport', 'Apple Watch Series 10 Aluminum GPS + Cellular Sport: Chip S10, màn hình Retina Always-On 42mm/46mm, kết nối Cellular, watchOS 10.', 13190000, 20, '../assets/images/watch/0029215_apple-watch-series-10-nhom-gps-42mm-sport-loop_240.jpeg', 7, NOW()),
('Apple Watch Ultra 2 GPS + Cellular Sport', 'apple-watch-ultra-2-gps-cellular-sport', 'Apple Watch Ultra 2 GPS + Cellular Sport: Chip S9, màn hình Retina Always-On 49mm, vỏ titanium, watchOS 10, pin 36 giờ.', 22990000, 20, '../assets/images/watch/0030238_apple-watch-ultra-2-gps-cellular-49mm-ocean-2024_240.png', 7, NOW()),
('Apple Watch SE 2024 GPS', 'apple-watch-se-2024-gps', 'Apple Watch SE 2024 GPS: Chip S9, màn hình Retina 40mm/44mm, theo dõi giấc ngủ, watchOS 10, giá trị cao.', 5890000, 20, '../assets/images/watch/0030516_apple-watch-se-gps-2024-sport-loop_240.jpeg', 7, NOW()),
('Apple Watch Series 10 Titanium 42mm', 'apple-watch-series-10-titanium-42mm', 'Apple Watch Series 10 Titanium 42mm: Chip S10, màn hình Retina Always-On 42mm, vỏ titanium, watchOS 10.', 19690000, 20, '../assets/images/watch/0030917_apple-watch-series-10-titanium-gps-cellular-42mm-sport-band_240.png', 7, NOW()),
('Apple Watch Series 10 Titanium 46mm', 'apple-watch-series-10-titanium-46mm', 'Apple Watch Series 10 Titanium 46mm: Chip S10, màn hình Retina Always-On 46mm, vỏ titanium, watchOS 10.', 21690000, 20, '../assets/images/watch/0030973_apple-watch-series-10-titanium-gps-cellular-46mm-sport-band_240.png', 7, NOW()),
('Apple Watch Series 10 Allumium GPS + Cellular Sport Milanese', 'apple-watch-series-10-allumium-gps-cellular-sport-milanese', 'Apple Watch Series 10 Aluminum GPS + Cellular Sport Milanese: Chip S10, màn hình Retina Always-On 42mm, dây Milanese, watchOS 10.', 19990000, 20, '../assets/images/watch/0031028_apple-watch-series-10-titanium-gps-cellular-42mm-milanese-loop_240.png', 7, NOW()),
('Clear Case with MagSafe Iphone 14 Pro Max', 'clear-case-with-magsafe-iphone-14-pro-max', 'Clear Case with MagSafe iPhone 14 Pro Max: Ốp lưng trong suốt, hỗ trợ MagSafe, chất liệu polycarbonate, chống ố vàng.', 990000, 20, '../assets/images/case/0001737_iphone-14-pro-max-clear-case-with-magsafe_240.jpeg', 6, NOW()),
('Silicon Case IPhone 14 Plus', 'silicon-case-iphone-14-plus', 'Silicon Case iPhone 14 Plus: Ốp lưng silicon mềm, hỗ trợ MagSafe, bảo vệ toàn diện, nhiều màu sắc.', 690000, 20, '../assets/images/case/0002665_iphone-14-plus-silicone-case-with-magsafe_240.jpeg', 6, NOW()),
('Leather Case Iphone 14', 'leather-case-iphone-14', 'Leather Case iPhone 14: Ốp lưng da cao cấp, hỗ trợ MagSafe, thiết kế tinh tế, chống trầy xước.', 1690000, 20, '../assets/images/case/0002824_iphone-14-leather-case-with-magsafe_240.jpeg', 6, NOW()),
('Silicon Case Iphone 13 Pro Max', 'silicon-case-iphone-13-pro-max', 'Silicon Case iPhone 13 Pro Max: Ốp lưng silicon mềm, hỗ trợ MagSafe, bảo vệ camera, chất liệu chống bám vân tay.', 690000, 20, '../assets/images/case/0002966_op-lung-iphone-13-pro-max-silicone-case-with-magsafe_240.jpeg', 6, NOW()),
('Mipow Premium Case for Iphone 6.9 Inch', 'mipow-premium-case-for-iphone-6-9-inch', 'Mipow Premium Case for iPhone 6.9 Inch: Ốp lưng MagSafe mỏng nhẹ, tương thích iPhone 16 series, chống sốc.', 390000, 20, '../assets/images/case/0034860_op-lung-mipow-premium-slim-magsafe-case-for-iphone-69-inch-2024_240.jpeg', 6, NOW()),
('Hybird Case for Iphone 16 Pro Max', 'hybird-case-for-iphone-16-pro-max', 'Hybrid Case for iPhone 16 Pro Max: Ốp lưng kết hợp cứng-mềm, hỗ trợ HaloLock, bảo vệ tối ưu.', 390000, 20, '../assets/images/case/0036446_op-lung-classic-hybrid-case-halolock-cho-iphone-16-pro-max_240.png', 6, NOW()),
('AirPods Pro 2', 'airpods-pro-2', 'AirPods Pro 2: Chip H2, khử tiếng ồn chủ động, âm thanh không gian, cổng USB-C, pin 6 giờ (30 giờ với hộp sạc).', 4850000, 20, '../assets/images/airpod/0000211_airpods-pro-2_240.png', 8, NOW()),
('AirPods 3 MagSafe', 'airpods-3-magsafe', 'AirPods 3 MagSafe: Chip H1, âm thanh không gian, hỗ trợ MagSafe, pin 6 giờ (30 giờ với hộp sạc), chống nước IPX4.', 5490000, 20, '../assets/images/airpod/0000230_tai-nghe-apple-airpods-3-sac-khong-day-magsafe_240.png', 8, NOW()),
('AirPods 3 Lightning', 'airpods-3-lightning', 'AirPods 3 Lightning: Chip H1, âm thanh không gian, cổng Lightning, pin 6 giờ (30 giờ với hộp sạc), thiết kế mới.', 5490000, 20, '../assets/images/airpod/0006057_tai-nghe-apple-airpods-3-sac-co-day-lightning_240.jpeg', 8, NOW()),
('AirPods Max', 'airpods-max', 'AirPods Max: Chip H1, khử tiếng ồn chủ động, âm thanh Hi-Fi, vỏ nhôm, pin 20 giờ, thiết kế over-ear.', 12590000, 20, '../assets/images/airpod/0012005_airpods-max_240.webp', 8, NOW()),
('AirPods Pro 2021', 'airpods-pro-2021', 'AirPods Pro 2021: Chip H1, khử tiếng ồn chủ động, âm thanh không gian, pin 6 giờ (24 giờ với hộp sạc).', 4850000, 20, '../assets/images/airpod/0012020_airpods-pro-2021_240.webp', 8, NOW()),
('AirPods 2', 'airpods-2', 'AirPods 2: Chip H1, thiết kế cổ điển, pin 5 giờ (24 giờ với hộp sạc), kết nối nhanh với iPhone.', 4390000, 20, '../assets/images/airpod/0015613_airpods-2_240.jpeg', 8, NOW()),
('AirPods Pro 2 USB C', 'airpods-pro-2-usb-c', 'AirPods Pro 2 USB-C: Chip H2, khử tiếng ồn cải tiến, cổng USB-C, âm thanh không gian, pin 6 giờ (30 giờ với hộp sạc).', 5690000, 20, '../assets/images/airpod/0022022_airpods-pro-2-usb-c-2023_240.jpeg', 8, NOW()),
('AirPods 4', 'airpods-4', 'AirPods 4: Chip H2, thiết kế mới, âm thanh không gian, pin 5 giờ (25 giờ với hộp sạc), chống nước IPX4.', 3390000, 20, '../assets/images/airpod/0029778_airpods-4_240.jpeg', 8, NOW()),
('AirPods Max 2024', 'airpods-max-2024', 'AirPods Max 2024: Chip H2, khử tiếng ồn chủ động, cổng USB-C, âm thanh Hi-Fi, pin 20 giờ, nhiều màu sắc.', 12490000, 20, '../assets/images/airpod/0029786_airpods-max-cong-usb-c-2024_240.jpeg', 8, NOW());
INSERT INTO orders (user_id, total_price, status, payment_method, shipping_phone, shipping_name, notes, product_id, quantity)
VALUES
    (1, 19290000, 'pending', 'cash_on_delivery', '0123456789', 'Charlie Brown', 'Giao hàng trước 17h chiều nay', 127, 1),
    (1, 38580000, 'pending', 'bank_transfer', '0123456789', 'Charlie Brown', 'Kiểm tra kỹ sản phẩm trước khi giao', 127, 2),
    (7, 19290000, 'pending', 'cash_on_delivery', '0912345678', 'Tran Thi B', 'Giao hàng trong giờ hành chính', 127, 1),
    (3, 57870000, 'pending', 'bank_transfer', '0987654321', 'Le Quoc Bao', 'Gọi trước 30 phút khi đến giao hàng', 127, 3),
    (7, 28790000, 'pending', 'cash_on_delivery', '0912345678', 'Tran Thi B', 'Đóng gói cẩn thận, hàng dễ vỡ', 121, 1),
    (3, 23890000, 'pending', 'bank_transfer', '0987654321', 'Le Quoc Bao', 'Yêu cầu giao vào buổi sáng sớm', 131, 1);
    
INSERT INTO orders (user_id, total_price, status, payment_method, shipping_phone, shipping_name, notes, product_id, quantity)
VALUES
    (8, 19290000, 'pending', 'cash_on_delivery', '0123456789', 'Grab', 'Giao hàng trước 17h chiều nay', 128, 1),
    (8, 38580000, 'pending', 'bank_transfer', '0123456789', 'Bee', 'Kiểm tra kỹ sản phẩm trước khi giao', 128, 2),
    (8, 19290000, 'pending', 'cash_on_delivery', '0912345678', 'XanhMS', 'Giao hàng trong giờ hành chính', 128, 1),
    (8, 57870000, 'pending', 'bank_transfer', '0987654321', 'Grab', 'Gọi trước 30 phút khi đến giao hàng', 128, 3),
    (8, 28790000, 'pending', 'cash_on_delivery', '0912345678', 'Grab', 'Đóng gói cẩn thận, hàng dễ vỡ', 128, 1),
    (8, 23890000, 'pending', 'bank_transfer', '0987654321', 'Grab', 'Yêu cầu giao vào buổi sáng sớm', 138, 1);

DELIMITER $$

CREATE PROCEDURE CreateSlug(IN input_text VARCHAR(255), OUT output_slug VARCHAR(255))
BEGIN
    SET output_slug = LOWER(REPLACE(input_text, ' ', '-'));
END $$

DELIMITER ;