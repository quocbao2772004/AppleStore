import json
import unittest

from tgdd_scraper import category_of, money, parse_detail, parse_listing, repair_text


class ScraperParsingTests(unittest.TestCase):
    def test_price_formats_and_unknown_price(self):
        self.assertEqual(money("39.490.000₫"), 39490000)
        self.assertEqual(money("39490000.0"), 39490000)
        self.assertIsNone(money("0"))

    def test_product_detail_preserves_specs_images_and_location(self):
        product = {
            "@type": "Product", "sku": "12345", "name": "Laptop mẫu",
            "url": "https://www.thegioididong.com/laptop/laptop-mau",
            "image": {"contentUrl": "https://cdn.tgdd.vn/main.jpg"},
            "brand": {"name": "Asus"},
            "additionalProperty": [{"name": "RAM", "value": "16 GB"}],
            "offers": {"price": "21000000.0", "availability": "https://schema.org/InStock"},
            "review": [{"author": {"name": "Khách hàng"}, "reviewRating": {"ratingValue": 4},
                        "reviewBody": "Pin tốt", "datePublished": "2026-09-01"}],
        }
        html = f"""
          <script type="application/ld+json">{json.dumps(product)}</script>
          <div class="box04__txt">Giá tại Hà Nội</div>
          <div class="box-specifi"><h3>Bộ nhớ RAM, Ổ cứng</h3>
            <ul class="text-specifi"><li><aside><strong>RAM:</strong></aside><aside>16 GB</aside></li></ul>
          </div>
          <div class="gallery-img"><div class="slider-img">
            <img data-src="https://cdn.tgdd.vn/side.jpg" alt="Mặt bên" />
          </div></div>
        """
        row = parse_detail(html, product["url"])
        self.assertEqual(row["price_vnd"], 21000000)
        self.assertEqual(row["price_location"], "Hà Nội")
        self.assertIn(("Bộ nhớ RAM, Ổ cứng", "RAM", "16 GB", 0), row["specs"])
        self.assertEqual(len(row["images"]), 2)
        self.assertEqual(row["image_alt"]["https://cdn.tgdd.vn/side.jpg"], "Mặt bên")
        self.assertEqual(row["reviews"][0]["body"], "Pin tốt")

    def test_listing_filters_out_other_categories(self):
        html = """
          <ul class="listproduct">
            <li data-id="123" data-productcode="abc"><a class="main-contain"
              href="/dtdd/phone-1" data-name="Điện thoại A" data-brand="A">
              <div class="item-img"><img class="thumb" src="https://cdn.tgdd.vn/phone-1.jpg" alt="Điện thoại A"></div>
              <strong class="price">1.990.000₫</strong></a></li>
            <li data-id="456"><a class="main-contain" href="/laptop/laptop-1"
              data-name="Laptop B"></a></li>
          </ul>
        """
        rows = parse_listing(html, "dtdd")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_product_id"], 123)
        self.assertEqual(rows[0]["price_vnd"], 1990000)
        self.assertEqual(rows[0]["thumbnail_url"], "https://cdn.tgdd.vn/phone-1.jpg")
        self.assertEqual(rows[0]["thumbnail_alt"], "Điện thoại A")
        self.assertEqual(category_of(rows[0]["url"]), "phone")

    def test_detail_without_json_ld_keeps_gallery_image(self):
        html = """
          <div class="box02__right" data-id="99" data-name="Tai nghe mẫu"
               data-img="https://cdn.tgdd.vn/thumb.jpg"></div>
          <h1>Tai nghe mẫu</h1>
          <div class="box-price-present">890.000₫</div>
          <div class="gallery-img"><div class="slider-img">
            <img src="https://cdn.tgdd.vn/front.jpg" alt="Mặt trước" />
          </div></div>
        """
        row = parse_detail(html, "https://www.thegioididong.com/tai-nghe/tai-nghe-mau", 99)
        self.assertEqual(row["source_product_id"], 99)
        self.assertEqual(row["price_vnd"], 890000)
        self.assertEqual(row["images"][0], "https://cdn.tgdd.vn/front.jpg")
        self.assertIn("https://cdn.tgdd.vn/thumb.jpg", row["images"])

    def test_repairs_mojibake_seen_on_source(self):
        self.assertEqual(repair_text("Ä\x90iá»\x87n thoáº¡i"), "Điện thoại")


if __name__ == "__main__":
    unittest.main()
