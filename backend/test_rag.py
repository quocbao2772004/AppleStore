"""Tests for document chunking and the upload parser. No network and no Qdrant."""
import unittest

from rag.documents import _clean, brand_key
from rag.embed import public_error
from rag.textutil import chunk_text
from rag.upload import parse_multipart


class ChunkTests(unittest.TestCase):
    def test_long_text_overlaps_and_stays_near_the_chunk_size(self):
        paragraph = "Bảo hành pin 12 tháng. " * 200
        parts = chunk_text(paragraph + "\n\n" + paragraph)
        self.assertGreater(len(parts), 1)
        self.assertLess(len(parts[0]), 1800)
        self.assertIn("12 tháng", parts[0])
        self.assertTrue(parts[0][-40:] in parts[1] or parts[1].startswith(parts[0][-40:].strip()[:20]))

    def test_short_noise_is_dropped_when_a_real_paragraph_exists(self):
        parts = chunk_text("Ok\n\n" + ("Thân máy được bảo hành 12 tháng tại Việt Nam. " * 6))
        self.assertTrue(all(len(part) >= 80 for part in parts))
        self.assertIn("12 tháng", parts[0])


class UploadParserTests(unittest.TestCase):
    def test_multipart_keeps_text_bytes_and_fields(self):
        body = (
            b"--bound\r\n"
            b'Content-Disposition: form-data; name="title"\r\n\r\n'
            b"Bao hanh OPPO\r\n"
            b"--bound\r\n"
            b'Content-Disposition: form-data; name="file"; filename="oppo.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"Pin 12 thang\r\n"
            b"--bound--\r\n"
        )
        fields, files = parse_multipart(body, 'multipart/form-data; boundary=bound')
        self.assertEqual(fields["title"], ["Bao hanh OPPO"])
        self.assertEqual(files["file"]["filename"], "oppo.txt")
        self.assertEqual(files["file"]["data"], b"Pin 12 thang")


class RetrievalGuardTests(unittest.TestCase):
    def test_a_brand_with_no_terms_is_not_answered_from_another_brand(self):
        from rag.search import gap_brand, indexed_brand

        self.assertEqual(gap_brand("Tai nghe Philips bảo hành bao lâu"), "philips")
        self.assertEqual(indexed_brand("iPhone được bảo hành mấy năm"), "apple")
        self.assertEqual(gap_brand("iPhone được bảo hành mấy năm"), "")

    def test_a_duration_table_keeps_the_number_on_the_product(self):
        from rag.textutil import _html_text

        html = """<table><tr><td>STT</td><td>Sản phẩm</td><td>Thời hạn bảo hành</td></tr>
        <tr><td>1</td><td>Điện thoại di động</td><td>12 tháng</td></tr></table>
        <p>.detail-page { font-family: sans-serif !important; }</p>
        <p>Thân máy được bảo hành theo bảng trên.</p>"""
        text = _html_text(html)
        self.assertIn("Điện thoại di động", text)
        self.assertIn("12 tháng", text)
        self.assertNotIn("!important", text)
        self.assertIn("Thời hạn bảo hành: 12 tháng", text)

    def test_a_title_row_does_not_steal_the_column_names(self):
        from rag.textutil import _html_text

        html = """<table>
        <tr><td>Trong Thời Gian Bảo Hành</td></tr>
        <tr><th>Thân Thiết Bị</th><th>Pin Tích Hợp Theo Thiết Bị</th><th>Phụ Kiện Theo Thiết Bị</th></tr>
        <tr><td>12 tháng</td><td>12 tháng</td><td>6 tháng</td></tr>
        </table>"""
        text = _html_text(html)
        self.assertIn("Pin Tích Hợp Theo Thiết Bị: 12 tháng", text)
        self.assertIn("Phụ Kiện Theo Thiết Bị: 6 tháng", text)

    def test_json_noise_is_left_out_of_the_chunks(self):
        text = 'window.pageDsl={"cmps":["x"],"linkTarget":"a"}\n\n' + ("Thân máy được bảo hành 12 tháng. " * 8)
        parts = chunk_text(text)
        self.assertTrue(parts)
        self.assertTrue(all("pageDsl" not in part for part in parts))
        self.assertIn("12 tháng", parts[0])


class DocumentMetaTests(unittest.TestCase):
    def test_brand_alias_maps_iphone_to_apple(self):
        self.assertEqual(brand_key("iPhone"), "apple")
        self.assertEqual(brand_key("OPPO"), "oppo")

    def test_return_type_is_not_warranty(self):
        cleaned = _clean("Đổi trả JBL", "JBL", "return", "en", "https://example.com/returns", "Cửa hàng Mỹ")
        self.assertEqual(cleaned["doc_type"], "return")
        self.assertNotEqual(cleaned["doc_type"], "warranty")

    def test_errors_do_not_keep_a_broker_url_or_a_key(self):
        text = public_error("failed amqp://guest:guest@127.0.0.1:5672/ sk-secretvalue")
        self.assertNotIn("guest:guest", text)
        self.assertNotIn("sk-secretvalue", text)


if __name__ == "__main__":
    unittest.main()
