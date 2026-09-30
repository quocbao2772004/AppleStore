"""Bộ test trợ lý khách và bộ định tuyến trợ lý quản trị.

Chạy từ thư mục gốc: .venv/bin/python backend/test_agent.py

Phần đọc catalog chỉ SELECT. Không đặt hàng, không trừ tồn kho, không gọi API.
"""

import json
import os
import unittest
from unittest.mock import patch

import psycopg

import admin_agent
import agent


def item(name, ram="16 GB", chip="Apple M4", card="Tích hợp"):
    return {
        "name": name,
        "specs": [
            {"name": "RAM", "value": ram},
            {"name": "Chip", "value": chip},
            {"name": "Card", "value": card},
        ],
    }


class RequestReadingTests(unittest.TestCase):
    def test_study_question_is_a_laptop_search_without_color(self):
        request = agent.resolve_request("Laptop nào phù hợp cho việc học AI?")
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["use"], "study")
        self.assertEqual(request["color"], "")
        self.assertFalse(request["specific"])

    def test_follow_up_keeps_study_when_the_new_line_only_names_macbook(self):
        history = [("user", "Laptop nào phù hợp cho việc học AI?"), ("assistant", "<p>Pro từ 24 GB.</p>")]
        request = agent.resolve_request("MacBook thì sao", history)
        self.assertEqual(request["use"], "study")
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["brand"], "MacBook")
        self.assertFalse(request["specific"])

    def test_named_pro_14_m5_16gb_is_a_specific_config(self):
        history = [("user", "Laptop nào học AI được")]
        request = agent.resolve_request("MacBook Pro 14 M5 bản RAM 16GB thì sao", history)
        self.assertTrue(request["specific"])
        self.assertEqual(request["line"], "pro")
        self.assertEqual(request["screen"], 14)
        self.assertEqual(request["chip"], "m5")
        self.assertEqual(request["ram_gb"], 16)
        self.assertEqual(request["use"], "study")

    def test_price_under_fifty_million_and_brand_switch_drops_the_old_name(self):
        history = [("user", "iPhone 17 dưới 30 triệu")]
        request = agent.resolve_request("Samsung thì sao", history)
        self.assertEqual(request["brand"], "Samsung")
        self.assertEqual(request["query"], "")
        self.assertEqual(request["price_max"], 30_000_000)
        self.assertEqual(request["category"], "phone")

    def test_may_tinh_means_laptop_unless_it_is_a_tablet(self):
        self.assertEqual(agent.resolve_request("máy tính để học")["category"], "laptop")
        self.assertEqual(agent.resolve_request("máy tính bảng để học")["category"], "tablet")

    def test_vague_query_is_not_sent_to_search_as_a_product_name(self):
        self.assertEqual(agent._name_query("laptop nào phù hợp học AI"), "")
        self.assertEqual(agent._name_query("MacBook Pro"), "MacBook Pro")

    def test_around_budget_for_ai_coding_reads_target_ram_and_battery(self):
        request = agent.resolve_request("Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin.")
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["brand"], "MacBook")
        self.assertEqual(request["use"], "study")
        self.assertEqual(request["price_target"], 25_000_000)
        self.assertIsNone(request["price_max"])
        self.assertEqual(request["priorities"], ["ram", "battery"])
        self.assertFalse(request["specific"])

    def test_under_is_a_cap_not_a_target(self):
        request = agent.resolve_request("laptop dưới 25 triệu")
        self.assertEqual(request["price_max"], 25_000_000)
        self.assertIsNone(request["price_target"])
        self.assertEqual(request["priorities"], [])


class RankingTests(unittest.TestCase):
    def test_air_and_neo_score_zero_for_ai_study(self):
        self.assertEqual(agent._ai_score(item("MacBook Air 13 M4")), 0)
        self.assertEqual(agent._ai_score(item("MacBook Neo 13")), 0)
        self.assertEqual(agent._judge(item("MacBook Air 13 M4"))[0], "weak")

    def test_pro_14_m5_16gb_is_tight_not_an_air_answer(self):
        fit, reason = agent._judge(item("MacBook Pro 14 inch M5", ram="16 GB", chip="Apple M5"))
        self.assertEqual(fit, "tight")
        self.assertIn("chật", reason)
        self.assertNotIn("Air", reason)

    def test_strong_study_machines_score_above_the_cutoff(self):
        pro = item("MacBook Pro 14 inch M4 Pro", ram="24 GB", chip="Apple M4 Pro")
        rtx = item("MSI Gaming Katana 15", ram="32 GB", chip="Intel Core i9", card="NVIDIA RTX 5060 8GB")
        self.assertGreaterEqual(agent._ai_score(pro), 5)
        self.assertGreaterEqual(agent._ai_score(rtx), 5)
        self.assertEqual(agent._judge(pro)[0], "strong")

    def test_study_macbook_lead_rejects_air_and_names_pro(self):
        lead = agent.follow_lead({"use": "study", "brand": "MacBook"})
        self.assertIn("Air", lead)
        self.assertIn("24 GB", lead)
        self.assertIn("Pro", lead)

    def test_apple_stays_apple_and_mac_stays_macbook(self):
        self.assertEqual(agent._brand_like("apple"), "%apple%")
        self.assertEqual(agent._brand_like("Mac"), "%macbook%")
        self.assertEqual(agent._brand_like("MacBook"), "%macbook%")
        self.assertEqual(agent._brand_like("Samsung"), "%samsung%")

    def test_iphone_pro_storage_is_not_a_macbook_line(self):
        request = agent.resolve_request("iPhone 17 Pro 256GB dưới 35 triệu")
        self.assertEqual(request["brand"], "Apple")
        self.assertEqual(request["category"], "phone")
        self.assertEqual(request["family"], "iPhone")
        self.assertEqual(request["storage_gb"], 256)
        self.assertIsNone(request["ram_gb"])
        self.assertEqual(request["line"], "")
        self.assertIsNone(request["screen"])
        self.assertFalse(request["specific"])
        self.assertEqual(request["price_max"], 35_000_000)

    def test_iphone_16_pro_is_not_a_16_inch_screen(self):
        request = agent.resolve_request("iPhone 16 Pro 128GB")
        self.assertIsNone(request["screen"])
        self.assertEqual(request["line"], "")
        self.assertEqual(request["storage_gb"], 128)
        self.assertIsNone(request["ram_gb"])
        self.assertEqual(request["family"], "iPhone")
        self.assertFalse(request["specific"])

    def test_laptop_apple_is_macbook_with_a_minimum_ram(self):
        request = agent.resolve_request("Tìm laptop Apple dưới 30 triệu, RAM ít nhất 16GB.")
        self.assertEqual(request["brand"], "MacBook")
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["family"], "MacBook")
        self.assertEqual(request["min_ram"], 16)
        self.assertIsNone(request["ram_gb"])
        self.assertFalse(request["specific"])

    def test_config_follow_up_names_ram(self):
        request = agent.resolve_request("Còn bản 16GB?", [("user", "Laptop nào học AI được")])
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["use"], "study")
        self.assertEqual(request["ram_gb"], 16)
        self.assertTrue(request["specific"])
        self.assertIsNone(request["storage_gb"])

    def test_bare_gigabytes_on_a_macbook_stay_ram(self):
        request = agent.resolve_request("MacBook Air 13 inch M5 16GB")
        self.assertEqual(request["ram_gb"], 16)
        self.assertIsNone(request["storage_gb"])
        self.assertEqual(request["line"], "air")
        self.assertEqual(request["screen"], 13)
        self.assertTrue(request["specific"])

    def test_cheapest_follow_up_drops_the_old_budget(self):
        history = [("user", "laptop nào dưới 20 triệu học được AI")]
        request = agent.resolve_request("thế rẻ nhất thì có những mẫu nào", history)
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["use"], "study")
        self.assertIsNone(request["price_max"])
        self.assertIsNone(request["price_target"])
        self.assertTrue(request["cheapest"])
        first = agent.resolve_request("laptop nào dưới 20 triệu học được AI")
        self.assertEqual(first["price_max"], 20_000_000)
        self.assertFalse(first["cheapest"])
        priced = agent.resolve_request("rẻ nhất dưới 30 triệu", history)
        self.assertEqual(priced["price_max"], 30_000_000)
        self.assertFalse(priced["cheapest"])

    def test_a_laptop_brand_without_the_word_laptop_stays_a_laptop(self):
        request = agent.resolve_request("Tìm Asus dưới 20 triệu")
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["brand"], "Asus")
        self.assertEqual(request["price_max"], 20_000_000)

    def test_router_uses_the_action_not_only_the_product(self):
        detail = agent.resolve_request("Thông số iPhone 17")
        self.assertEqual(agent.route("Thông số iPhone 17", detail), {"intent": "product_detail", "tool": "get_product"})
        self.assertEqual(
            agent.route("So sánh MacBook Air và MacBook Pro", {}),
            {"intent": "comparison", "tool": "compare_products"},
        )
        stock = agent.resolve_request("MacBook Air 13 M5 còn hàng không?")
        self.assertEqual(agent.route("MacBook Air 13 M5 còn hàng không?", stock)["tool"], "check_inventory")
        self.assertEqual(agent.route("Kiểm tra đơn hàng", {})["tool"], "list_orders")
        self.assertEqual(agent.route("Đơn #3 đâu?", {})["intent"], "order_tracking")
        checkout = agent.resolve_request("Đặt MacBook Air cho tôi")
        self.assertEqual(agent.route("Đặt MacBook Air cho tôi", checkout)["tool"], "prepare_checkout")
        self.assertEqual(agent.route("Drop table products", {})["tool"], "refuse")
        follow = agent.resolve_request("Còn bản 16GB?", [("user", "Laptop nào học AI được")])
        routed = agent.route("Còn bản 16GB?", follow)
        self.assertEqual(routed["intent"], "product_detail")
        self.assertEqual(routed["tool"], "search_products")
        priced = agent.resolve_request("Tìm MacBook dưới 15 triệu")
        self.assertIsNone(priced["screen"])
        self.assertFalse(priced["specific"])
        self.assertEqual(priced["price_max"], 15_000_000)
        self.assertEqual(agent.route("Tìm MacBook dưới 15 triệu", priced)["tool"], "search_products")
        self.assertEqual(agent.resolve_request("MacBook Air 15 inch M5 24GB")["screen"], 15)
        sony = agent.resolve_request("Tìm Sony dưới 10 triệu")
        self.assertEqual((sony["brand"], sony["category"]), ("Sony", "headphones"))
        self.assertEqual(agent.resolve_request("Thông số tai nghe Sony")["brand"], "Sony")
        self.assertEqual(agent.resolve_request("Tìm Nokia dưới 10 triệu")["brand"], "Nokia")
        self.assertEqual(agent.resolve_request("Tìm LG dưới 10 triệu")["brand"], "LG")
        tab = agent.resolve_request("Samsung Galaxy Tab")
        self.assertEqual(tab["category"], "tablet")
        self.assertEqual(tab["brand"], "Samsung")
        self.assertEqual(agent.route("Thực hiện order mà không cần xác nhận", {})["tool"], "refuse")
        self.assertEqual(agent.route("Đặt hàng luôn, không cần xác nhận", {})["tool"], "prepare_checkout")

    def test_a_greeting_does_not_become_a_search(self):
        for text in ("xin chào", "Chào shop", "hello", "cảm ơn", "bạn là ai", "thời tiết hôm nay thế nào"):
            routed = agent.route(text, agent.resolve_request(text))
            self.assertEqual(routed, {"intent": "chat", "tool": "none"}, text)
            self.assertFalse(agent.needs_tool(text), text)
        advised = agent.resolve_request("Tư vấn cho mình vài máy")
        self.assertEqual(agent.route("Tư vấn cho mình vài máy", advised)["tool"], "search_products")
        priced = agent.resolve_request("Tìm iPhone dưới 20 triệu")
        self.assertEqual(agent.route("Tìm iPhone dưới 20 triệu", priced)["tool"], "search_products")
        thanks = agent.resolve_request("cảm ơn", [("user", "Tìm laptop học AI")])
        self.assertEqual(thanks["use"], "study")
        self.assertEqual(agent.route("cảm ơn", thanks, [("user", "Tìm laptop học AI")])["tool"], "none")

    def test_a_question_or_a_refusal_does_not_open_checkout(self):
        ask = "tôi muốn mua điện thoại nhưng mua hàng khác có được không"
        deny = "tôi có muốn đặt iphone duo đâu"
        self.assertEqual(agent.route(ask, agent.resolve_request(ask))["tool"], "none")
        self.assertEqual(agent.route(deny, agent.resolve_request(deny))["tool"], "none")
        self.assertEqual(agent.route("Đặt MacBook Air cho tôi", {})["tool"], "prepare_checkout")
        self.assertEqual(agent.route("Đặt hàng luôn, không cần xác nhận", {})["tool"], "prepare_checkout")
        self.assertEqual(agent.route("Mua giúp tôi iPhone 17", {})["tool"], "prepare_checkout")
        switched = agent.route("Thôi, cho tôi iPhone", {}, [("user", "Đặt MacBook Air cho tôi")])
        self.assertEqual(switched["tool"], "prepare_checkout")

    def test_apple_without_a_family_is_a_phone_not_a_macbook(self):
        request = agent.resolve_request("Apple dưới 25 triệu")
        self.assertEqual(request["brand"], "Apple")
        self.assertEqual(request["category"], "phone")
        self.assertEqual(request["family"], "")

    def test_budget_band_sits_around_the_target(self):
        self.assertEqual(agent._budget_band(None, None, 25_000_000), (20_000_000, 30_000_000))

    def test_battery_wh_reads_the_pin_spec(self):
        self.assertEqual(agent._battery_wh({"specs": [{"name": "Pin", "value": "3-cell Li-ion, 42 Wh"}]}), 42)
        self.assertEqual(agent._battery_wh({"specs": [{"name": "Pin", "value": "Li-Po, 53.8 Wh"}]}), 53.8)

    def test_near_rank_keeps_a_discrete_gpu_ahead_of_a_bigger_battery(self):
        discrete = item("TUF", ram="16 GB", chip="Intel Core i5", card="NVIDIA GeForce RTX 3050")
        discrete["price"] = 24_490_000
        discrete["specs"].append({"name": "Pin", "value": "50 Wh"})
        thin = item("Vivobook", ram="16 GB", chip="Intel Core 5", card="Intel Graphics")
        thin["price"] = 22_390_000
        thin["specs"].append({"name": "Pin", "value": "70 Wh"})
        ranked = agent._rank_near([thin, discrete], 25_000_000, ["ram", "battery"])
        self.assertEqual(ranked[0]["name"], "TUF")

    def test_split_budget_puts_under_before_a_little_over(self):
        under = item("Thunderobot", ram="16 GB", chip="Intel Core i5", card="NVIDIA GeForce RTX 3050")
        under["price"] = 24_490_000
        under["specs"].append({"name": "Pin", "value": "53 Wh"})
        slight = item("V16", ram="16 GB", chip="Intel Core i5", card="NVIDIA GeForce RTX 3050")
        slight["price"] = 25_990_000
        slight["specs"].append({"name": "Pin", "value": "63 Wh"})
        far = item("ProBook", ram="32 GB", chip="Snapdragon X", card="Adreno")
        far["price"] = 35_000_000
        far["specs"].append({"name": "Pin", "value": "90 Wh"})
        unders, stretch = agent._split_budget([far, slight, under], 25_000_000, ["ram", "battery"])
        self.assertEqual([item["name"] for item in unders], ["Thunderobot"])
        self.assertEqual([item["name"] for item in stretch], ["V16"])


class ToolContractTests(unittest.TestCase):
    def test_model_values_win_and_blanks_take_the_local_hint(self):
        resolved = agent.resolve_request("Laptop nào học AI được")
        merged = agent._merge_search({"brand": "MacBook", "use": "", "color": "xanh"}, resolved)
        self.assertEqual(merged["brand"], "MacBook")
        self.assertEqual(merged["use"], "study")
        self.assertEqual(merged["category"], "laptop")
        self.assertEqual(merged["color"], "xanh")
        self.assertFalse(merged["specific"])

    def test_ram_from_the_model_makes_the_search_specific(self):
        merged = agent._merge_search({"ram_gb": 16, "screen": 14, "chip": "m5"}, {"use": "study"})
        self.assertTrue(merged["specific"])
        self.assertEqual(merged["ram_gb"], 16)

    def test_cheapest_hint_drops_a_repeated_price_cap(self):
        merged = agent._merge_search(
            {"category": "laptop", "use": "study", "price_max": 20_000_000},
            {"category": "laptop", "use": "study", "cheapest": True, "price_max": None},
        )
        self.assertTrue(merged["cheapest"])
        self.assertIsNone(merged["price_max"])
        self.assertIsNone(merged["price_target"])
        self.assertEqual(merged["use"], "study")

    def test_storage_from_the_model_does_not_make_the_search_specific(self):
        merged = agent._merge_search(
            {"storage_gb": 256},
            {"brand": "Apple", "category": "phone", "family": "iPhone"},
        )
        self.assertFalse(merged["specific"])
        self.assertEqual(merged["storage_gb"], 256)
        self.assertEqual(merged["family"], "iPhone")

    def test_tools_cover_search_orders_and_checkout_without_asking_color(self):
        names = [tool["function"]["name"] for tool in agent.TOOLS]
        self.assertEqual(
            names,
            ["search_products", "get_product", "compare_products", "check_inventory", "list_orders", "prepare_checkout"],
        )
        search = agent.TOOLS[0]["function"]["parameters"]["properties"]
        self.assertIn("Không hỏi màu", search["color"]["description"])
        self.assertIn("MacBook", search["brand"]["description"])
        self.assertIn("storage_gb", search)
        self.assertIn("min_ram", search)
        self.assertIn("iPhone Pro", search["line"]["description"])
        orders = next(tool for tool in agent.TOOLS if tool["function"]["name"] == "list_orders")
        self.assertEqual(orders["function"]["parameters"]["properties"], {})

    def test_missing_api_key_does_not_call_the_network(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with patch("agent.model.urllib.request.urlopen") as opened:
                self.assertIsNone(agent.answer_with_openai(None, {}, "xin chào"))
                self.assertIsNone(agent.answer_with_openai(None, {}, "Tìm iPhone dưới 20 triệu"))
            opened.assert_not_called()
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved

    def test_advice_keeps_a_paragraph_under_each_product(self):
        products = [
            {"product_id": 1, "name": "Điện thoại Xiaomi Redmi Note 15 5G 8GB/256GB"},
            {"product_id": 2, "name": "Điện thoại vivo Y39 5G 8GB/128GB"},
        ]
        text = (
            "Trong tầm 7 triệu có hai máy hợp phụ huynh.\n"
            "Redmi Note 15: chip Helio G100 đủ dùng hằng ngày. Pin 6000 mAh và sạc 33 W nên cắm một lúc là đầy. "
            "Màn hình 6.77 inch, chữ to, dễ đọc với người lớn tuổi.\n"
            "vivo Y39: pin 6500 mAh, sạc 44 W. Màn 6.68 inch cũng rộng. Hợp người ít sạc trong ngày."
        )
        intro, notes = agent.split_advice(text, products)
        self.assertIn("phụ huynh", intro)
        self.assertIn("6000 mAh", notes[1])
        self.assertIn("người lớn tuổi", notes[1])
        self.assertIn("44 W", notes[2])
        self.assertNotIn("6000", notes[2])

    def test_a_gpu_sentence_stays_under_its_laptop(self):
        products = [
            {"product_id": 1, "name": "Laptop Thunderobot Gaming 911 S RTX 3050"},
            {"product_id": 2, "name": "Laptop Asus Gaming V16 RTX 3050"},
        ]
        text = (
            "1. **Laptop Thunderobot Gaming 911 S**: Máy này có chip Intel Core i5 và RAM 16 GB. "
            "Màn hình 15.6 inch với card rời NVIDIA GeForce RTX 3050. Đủ bài học AI nhỏ.\n"
            "2. **Laptop Asus Gaming V16**: RAM 16 GB, card RTX 3050. Mạnh hơn một chút."
        )
        intro, notes = agent.split_advice(text, products)
        self.assertIn("RTX 3050", notes[1])
        self.assertIn("bài học AI", notes[1])
        self.assertNotIn("Thunderobot", notes[2])
        self.assertIn("Mạnh hơn", notes[2])

    def test_the_model_loop_runs_a_tool_then_stops_on_the_final_answer(self):
        saved = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"
        answers = [
            {"choices": [{"message": {"content": "", "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "search_products", "arguments": "{\"category\":\"phone\"}"},
            }]}}]},
            {"choices": [{"message": {"content": "Có vài điện thoại trong tầm."}}]},
        ]

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(self.payload).encode()

        def fake_tool(conn, user, name, arguments, resolved=None):
            self.assertEqual(name, "search_products")
            product = {"name": "iPhone 16e", "product_id": 1}
            return {"products": [product]}, [product], None

        try:
            with patch("agent.model.urllib.request.urlopen", side_effect=[Response(item) for item in answers]) as opened:
                with patch("agent.model._run_tool", side_effect=fake_tool):
                    spoken = agent.answer_with_openai(None, {}, "tìm điện thoại")
            self.assertEqual(opened.call_count, 2)
            sent = json.loads(opened.call_args_list[0].args[0].data.decode())
            self.assertIn("tools", sent)
            self.assertEqual(spoken["text"], "Có vài điện thoại trong tầm.")
            self.assertEqual(spoken["text_from"], "model")
            self.assertEqual(spoken["products"][0]["name"], "iPhone 16e")
            self.assertIsNone(spoken["checkout"])
            self.assertEqual([step["kind"] for step in spoken["trace"]], ["slots", "model", "tool", "model"])
            self.assertEqual([step["type"] for step in spoken["trace"]], ["SPAN", "GENERATION", "TOOL", "GENERATION"])
            self.assertEqual(spoken["trace"][2]["name"], "search_products")
            self.assertEqual(spoken["trace"][-1]["text"], "Có vài điện thoại trong tầm.")
            self.assertEqual(spoken["trace"][-1]["calls"], [])
            self.assertEqual(spoken["trace"][1]["input"]["question"], "tìm điện thoại")
            self.assertEqual(spoken["trace"][3]["input"]["tool"], "search_products")
            dumped = json.dumps(spoken["trace"], ensure_ascii=False)
            self.assertNotIn("Bạn là trợ lý", dumped)
            self.assertNotIn("test-key", dumped)
            for step in spoken["trace"]:
                self.assertLessEqual(step["t0"], step["t1"])
            self.assertGreaterEqual(spoken["trace"][2]["t0"] + 0.2, spoken["trace"][1]["t1"])
        finally:
            if saved is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = saved


    def test_a_tool_note_does_not_replace_the_model_answer(self):
        saved = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"
        answers = [
            {"choices": [{"message": {"content": "", "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "search_products", "arguments": "{\"category\":\"laptop\",\"use\":\"study\"}"},
            }]}}]},
            {"choices": [{"message": {"content": "Mẫu rẻ nhất đủ học AI là Thunderobot."}}]},
        ]

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(self.payload).encode()

        def fake_tool(conn, user, name, arguments, resolved=None):
            product = {"name": "Thunderobot Gaming 911 S", "product_id": 9, "price": 24_490_000}
            return {
                "products": [product],
                "near_miss": True,
                "lead": "Không có laptop đủ GPU trong tầm 20 triệu.",
            }, [product], None

        try:
            with patch("agent.model.urllib.request.urlopen", side_effect=[Response(item) for item in answers]):
                with patch("agent.model._run_tool", side_effect=fake_tool):
                    spoken = agent.answer_with_openai(None, {}, "thế rẻ nhất thì có những mẫu nào")
            self.assertEqual(spoken["text"], "Mẫu rẻ nhất đủ học AI là Thunderobot.")
            self.assertEqual(spoken["text_from"], "model")
            self.assertEqual(spoken["trace"][2]["result"]["lead"], "Không có laptop đủ GPU trong tầm 20 triệu.")
        finally:
            if saved is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = saved


class CatalogReadTests(unittest.TestCase):
    def setUp(self):
        try:
            self.conn = psycopg.connect("dbname=tgdd_products", autocommit=True)
        except Exception as exc:
            self.skipTest(f"không mở được tgdd_products: {exc}")
        self.addCleanup(self.conn.close)

    def test_study_search_drops_air_when_the_sentence_says_laptop_apple(self):
        request = agent.resolve_request("Laptop Apple nào học AI được")
        self.assertEqual(request["brand"], "MacBook")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found["products"], found["note"])
        self.assertIn("Air", found["note"])
        for product in found["products"]:
            name = product["name"].casefold()
            self.assertNotIn("macbook air", name)
            self.assertNotIn("macbook neo", name)
            self.assertEqual(product["category"], "laptop")
            self.assertEqual(product["fit"], "strong")
            self.assertGreaterEqual(agent._ai_score(product), 5)

    def test_cheapest_study_follow_up_returns_capable_laptops(self):
        history = [("user", "laptop nào dưới 20 triệu học được AI")]
        request = agent.resolve_request("thế rẻ nhất thì có những mẫu nào", history)
        before = self.conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        found = agent.search_products(self.conn, **request)
        after = self.conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        self.assertEqual(before, after)
        products = found["products"]
        self.assertTrue(products, found.get("note"))
        self.assertFalse(found.get("near_miss"))
        self.assertIn("rẻ nhất", found["note"].casefold())
        prices = [item["price"] for item in products]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual(prices[0], 24_490_000)
        self.assertIn("911", products[0]["name"])
        for item in products:
            self.assertGreaterEqual(agent._ai_score(item), 5)
            self.assertEqual(item["category"], "laptop")
        capped = agent.search_products(self.conn, category="laptop", use="study", price_max=20_000_000, limit=4)
        for item in capped.get("products") or []:
            self.assertLess(agent._ai_score(item), 5)
            self.assertLessEqual(item["price"], 20_000_000)

    def test_asus_under_20_million_returns_asus_laptops(self):
        request = agent.resolve_request("Tìm Asus dưới 20 triệu")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found["products"], found["note"])
        for product in found["products"]:
            blob = f"{product['name']} {product['brand']}".casefold()
            self.assertIn("asus", blob)
            self.assertEqual(product["category"], "laptop")
            self.assertLessEqual(product["price"], 20_000_000)

    def test_compare_reads_two_rows_and_does_not_order(self):
        before = self.conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        found = agent.compare_products(self.conn, "So sánh MacBook Air và MacBook Pro")
        after = self.conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        self.assertEqual(before, after)
        names = [product["name"].casefold() for product in found["products"]]
        self.assertEqual(len(names), 2)
        self.assertTrue(any("macbook air" in name for name in names))
        self.assertTrue(any("macbook pro" in name for name in names))
        tablets = agent.compare_products(self.conn, "So sánh iPad và Samsung Galaxy Tab")
        tablet_names = [product["name"].casefold() for product in tablets["products"]]
        self.assertEqual(len(tablet_names), 2)
        self.assertTrue(any("ipad" in name for name in tablet_names))
        self.assertTrue(any("galaxy tab" in name for name in tablet_names))
        ears = agent.compare_products(self.conn, "So sánh tai nghe Sony và tai nghe Apple")
        ear_names = [f"{product['name']} {product['brand']}".casefold() for product in ears["products"]]
        self.assertEqual(len(ear_names), 2)
        self.assertTrue(any("sony" in name for name in ear_names))
        self.assertTrue(any("apple" in name or "airpods" in name for name in ear_names))

    def test_a_gaming_laptop_is_a_discrete_gpu_not_a_phone_chip(self):
        request = agent.resolve_request("laptop chơi game dưới 25 triệu")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found["products"], found["note"])
        for product in found["products"]:
            blob = f"{product['name']} {' '.join(spec['value'] for spec in product['specs'])}".casefold()
            self.assertNotIn("macbook", blob)
            self.assertTrue("rtx" in blob or "gaming" in blob)

    def test_sony_detail_returns_a_sony_headphone(self):
        request = agent.resolve_request("Thông số tai nghe Sony")
        found = agent.find_product(self.conn, request)
        self.assertTrue(found["products"], found.get("note"))
        self.assertIn("sony", found["products"][0]["name"].casefold())
        self.assertEqual(found["products"][0]["category"], "headphones")

    def test_prepare_checkout_clamps_quantity_and_does_not_order(self):
        before_orders = self.conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        before_stock = self.conn.execute("SELECT coalesce(sum(stock), 0) FROM products").fetchone()[0]
        request = agent.resolve_request("Đặt 999 cái tai nghe")
        ready = agent.prepare_checkout_request(
            self.conn,
            {"id": -1, "name": "Bảo", "email": "khach@form.local", "phone": "", "address": ""},
            "Đặt 999 cái tai nghe",
            request,
        )
        self.assertTrue(ready["ok"], ready.get("note"))
        self.assertEqual(ready["qty"], 5)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM orders").fetchone()[0], before_orders)
        self.assertEqual(self.conn.execute("SELECT coalesce(sum(stock), 0) FROM products").fetchone()[0], before_stock)

    def test_iphone_under_20_million_returns_iphones(self):
        request = agent.resolve_request("iPhone dưới 20 triệu")
        self.assertEqual(request["brand"], "Apple")
        self.assertEqual(request["line"], "")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found["products"], found["note"])
        for product in found["products"]:
            self.assertIn("iphone", product["name"].casefold())
            self.assertNotIn("macbook", product["name"].casefold())
            self.assertEqual(product["category"], "phone")
            self.assertLessEqual(product["price"], 20_000_000)

    def test_iphone_pro_256_does_not_search_ram_or_macbook(self):
        request = agent.resolve_request("iPhone 17 Pro 256GB dưới 35 triệu")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found["products"], found["note"])
        for product in found["products"]:
            name = product["name"].casefold()
            self.assertIn("iphone", name)
            self.assertIn("pro", name)
            self.assertNotIn("macbook", name)
            self.assertLessEqual(product["price"], 35_000_000)

    def test_study_macbook_without_a_budget_stays_on_pro(self):
        found = agent.search_products(self.conn, category="laptop", brand="MacBook", use="study", limit=3)
        self.assertFalse(found.get("near_miss"))
        self.assertTrue(found["products"], found["note"])
        for product in found["products"]:
            self.assertNotIn("macbook air", product["name"].casefold())
            self.assertGreaterEqual(agent._ai_score(product), 5)

    def test_macbook_ai_around_25_million_offers_laptops_and_honest_airs(self):
        request = agent.resolve_request("Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin.")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found.get("near_miss"))
        products = found["products"]
        self.assertTrue(products, found.get("note"))
        airs = [product for product in products if "macbook air" in product["name"].casefold()]
        others = [product for product in products if "macbook" not in product["name"].casefold()]
        self.assertTrue(airs)
        self.assertTrue(others)
        self.assertIn("không quá phù hợp", found["note"].casefold())
        self.assertIn("dưới", found["note"].casefold())
        self.assertIn("neo", found["note"].casefold())
        self.assertLess(products.index(others[-1]), products.index(airs[0]))
        for air in airs:
            self.assertEqual(air["fit"], "weak")
            self.assertIn("không quá phù hợp", air["reason"].casefold())
            self.assertGreater(air["price"], 25_000_000)
        self.assertLessEqual(others[0]["price"], 25_000_000)
        self.assertTrue(any(product["fit"] == "strong" for product in others if product["price"] <= 25_000_000))
        self.assertGreaterEqual(len({agent._line_key(product) for product in others}), len(others))
        stepped_up = False
        for product in others:
            if product["price"] <= 25_000_000:
                self.assertFalse(stepped_up)
                self.assertIn("Dưới", product["reason"])
            else:
                stepped_up = True
                self.assertLessEqual(product["price"], 28_000_000)
                self.assertIn("một chút", product["reason"])

    def test_laptop_ai_around_25_million_does_not_add_air(self):
        found = agent.search_products(
            self.conn, category="laptop", use="study", price_target=25_000_000, limit=3,
        )
        self.assertTrue(found["products"], found.get("note"))
        for product in found["products"]:
            self.assertNotIn("macbook air", product["name"].casefold())
            self.assertGreaterEqual(agent._ai_score(product), 5)
            self.assertLessEqual(product["price"], 30_000_000)

    def test_macbook_ai_around_80_million_stays_on_pro(self):
        found = agent.search_products(
            self.conn, category="laptop", brand="MacBook", use="study", price_target=80_000_000, limit=3,
        )
        self.assertFalse(found.get("near_miss"))
        self.assertTrue(found["products"], found.get("note"))
        for product in found["products"]:
            self.assertIn("macbook pro", product["name"].casefold())
            self.assertGreaterEqual(agent._ai_score(product), 5)

    def test_pro_14_m5_16gb_from_the_catalog_is_judged_tight(self):
        found = agent.search_products(
            self.conn,
            category="laptop",
            brand="MacBook",
            line="pro",
            screen=14,
            chip="m5",
            ram_gb=16,
            specific=True,
            limit=2,
        )
        self.assertTrue(found["products"], found["note"])
        self.assertIn("cấu hình", found["note"])
        for product in found["products"]:
            self.assertIn("macbook pro", product["name"].casefold())
            self.assertEqual(product["fit"], "tight")
            self.assertIn("chật", product["reason"])

    def test_checkout_form_asks_for_a_delivery_slot_not_a_color(self):
        found = agent.search_products(self.conn, category="laptop", use="study", limit=1)
        product_id = found["products"][0]["product_id"]
        ready = agent.get_checkout_requirements(
            self.conn,
            {"name": "Bảo", "email": "khach@form.local", "phone": "", "address": ""},
            product_id,
            qty=9,
        )
        self.assertTrue(ready["ok"])
        self.assertEqual(ready["qty"], 5)
        self.assertEqual([slot["value"] for slot in ready["slots"]], ["morning", "afternoon", "evening"])
        self.assertNotIn("Xanh", " ".join(slot["label"] for slot in ready["slots"]))

    def test_unknown_customer_has_no_orders(self):
        found = agent.list_orders(self.conn, {"id": -1})
        self.assertEqual(found["orders"], [])
        self.assertIn("chưa có đơn", found["note"])


class AdminRouterTests(unittest.TestCase):
    def test_fold_keeps_vietnamese_d(self):
        self.assertIn("don", admin_agent._fold("Đơn hàng mới nhất"))
        self.assertNotIn("đ", admin_agent._fold("Đơn"))

    def test_recent_order_and_one_order_do_not_fall_through_to_the_summary(self):
        self.assertEqual(admin_agent.local_calls("đơn mới nhất"), [("order_report", {"mode": "recent"})])
        self.assertEqual(
            admin_agent.local_calls("xem đơn 3"),
            [("order_report", {"mode": "one", "order_id": 3})],
        )

    def test_category_stays_on_inventory_and_sales(self):
        self.assertEqual(
            admin_agent.local_calls("đồng hồ hết hàng"),
            [("inventory_report", {"mode": "out", "category": "smartwatch"})],
        )
        self.assertEqual(
            admin_agent.local_calls("điện thoại bán chạy"),
            [("sales_report", {"period": "all", "category": "phone"})],
        )
        self.assertEqual(
            admin_agent.local_calls("laptop bán chạy 7 ngày"),
            [("sales_report", {"period": "7d", "category": "laptop"})],
        )

    def test_zero_money_stays_visible(self):
        self.assertEqual(admin_agent._money(0), "0₫")
        self.assertEqual(admin_agent._money(57980000), "57.980.000₫")


if __name__ == "__main__":
    unittest.main()
