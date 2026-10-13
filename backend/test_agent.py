"""Bộ test trợ lý khách và bộ định tuyến trợ lý quản trị.

Chạy từ thư mục gốc: .venv/bin/python backend/test_agent.py

Phần đọc catalog chỉ SELECT. Không đặt hàng, không trừ tồn kho, không gọi API.
"""

import datetime
import inspect
import json
import os
import re
import sys
import unittest
from unittest.mock import patch

import psycopg

os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

import admin_agent
import agent


def _visible_model(name):
    text = re.sub(r"\([^)]*\)", " ", name or "")
    text = re.sub(r"\s+-\s+.*$", "", text)
    text = re.sub(r"\s+\d+\s*GB(?:\s*/\s*\d+\s*(?:GB|TB))?", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _screen_inches(product):
    value = next((spec["value"] for spec in product["specs"] if spec["name"] == "Màn hình"), "")
    match = re.search(r"(\d+(?:[.,]\d+)?)", value)
    return float(match.group(1).replace(",", ".")) if match else 99.0


def item(name, ram="16 GB", chip="Apple M4", card="Tích hợp"):
    return {
        "name": name,
        "specs": [
            {"name": "RAM", "value": ram},
            {"name": "Chip", "value": chip},
            {"name": "Card", "value": card},
        ],
    }


def provider_plan(action, resolved=None, ask="", doc_type="warranty"):
    return {
        "action": action,
        "resolved": resolved or {},
        "ask": ask,
        "compare_left": "",
        "compare_right": "",
        "qty": 1,
        "doc_type": doc_type,
    }


class ProviderUnderstandingTests(unittest.TestCase):
    def test_provider_receives_the_follow_up_and_returns_complete_search_state(self):
        from agent.understand import _FIELDS, understand_turn

        requirements = {key: None for key in _FIELDS}
        requirements.update({
            "category": "phone", "query": "", "color": "", "price_min": 12_000_000,
            "price_max": 12_000_000, "price_max_exclusive": False,
            "price_target": 12_000_000, "budget_mode": "target", "brand": "", "excluded_brands": [],
            "use": "gaming", "priorities": [], "ram_gb": None, "min_ram": None,
            "storage_gb": None, "screen": None, "line": "", "variant": "",
            "chip": "", "family": "", "cheapest": False,
        })
        raw = {
            "action": "search_products", "question_to_ask": "", "compare_left": "",
            "compare_right": "", "qty": None, "doc_type": "other",
            "latest_excluded_brands": [],
            "latest_use": "unchanged", "latest_priorities": [],
            "requirements": requirements,
        }
        history = [("user", "tao muốn mua điện thoại về đánh điện tử"), ("bot", "Ngân sách khoảng bao nhiêu?")]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("agent.model._complete", return_value={"content": json.dumps(raw)}) as complete:
                plan = understand_turn("khoảng 12 triệu", history)
        self.assertEqual(plan["action"], "search_products")
        self.assertEqual(plan["resolved"]["use"], "gaming")
        self.assertEqual(plan["resolved"]["price_target"], 12_000_000)
        self.assertIsNone(plan["resolved"]["price_min"])
        self.assertIsNone(plan["resolved"]["price_max"])
        sent = complete.call_args.args[3]
        self.assertIn("đánh điện tử", sent[1]["content"])
        self.assertIn("khoảng 12 triệu", sent[1]["content"])
        self.assertTrue(complete.call_args.kwargs["response_format"]["json_schema"]["strict"])

    def test_provider_failure_does_not_reuse_the_regex_parser(self):
        from agent.understand import understand_turn

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with patch("agent.slots.resolve_request", side_effect=AssertionError("regex parser called")):
                with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                    understand_turn("tao muốn mua điện thoại về đánh điện tử")

    def test_langfuse_trace_shows_each_step_and_hides_secrets(self):
        from agent.langfuse_log import publish_turn

        captured = {}

        def capture(url, body, headers):
            captured["url"] = url
            captured["body"] = body
            captured["headers"] = headers

        spoken = {
            "text": "Dạ iPhone 16.",
            "text_from": "model",
            "trace": [
                {
                    "kind": "slots", "type": "SPAN", "name": "Đọc câu hỏi",
                    "arguments": {"query": "iPhone 16", "category": "phone", "phone": "090"},
                    "input": {"question": "t muốn mua iphone 16"}, "t0": 0, "t1": 10,
                },
                {
                    "kind": "intent", "type": "SPAN", "name": "Chọn việc", "tool": "search_products",
                    "model_action": "ask", "text": "Tool search_products.", "arguments": {},
                    "input": {"question": "t muốn mua iphone 16"}, "t0": 10, "t1": 12,
                },
                {
                    "kind": "tool", "type": "TOOL", "name": "search_products",
                    "sent": {}, "ran": {"query": "iPhone 16"},
                    "result": {"count": 1, "products": [{"name": "iPhone 16"}]},
                    "t0": 12, "t1": 40,
                },
                {
                    "kind": "model", "type": "GENERATION", "name": "gpt-5.6-luna",
                    "text": "Dạ iPhone 16.", "input": {"tool": "search_products"},
                    "t0": 40, "t1": 80,
                },
            ],
        }
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""}, clear=False):
            with patch("builtins.open", side_effect=OSError):
                self.assertFalse(publish_turn("hi", spoken, None))
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        }, clear=False):
            self.assertTrue(publish_turn(
                "t muốn mua iphone 16", spoken,
                {"id": 7, "token": "session-secret", "email": "khach@form.local"},
                send=capture,
            ))
        raw = json.dumps(captured["body"], ensure_ascii=False)
        self.assertNotIn("090", raw)
        self.assertNotIn("session-secret", raw)
        self.assertNotIn("khach@form.local", raw)
        self.assertNotIn("sk-lf-test", raw)
        self.assertTrue(captured["url"].endswith("/api/public/otel/v1/traces"))
        self.assertEqual(captured["headers"]["x-langfuse-ingestion-version"], "4")
        names = [span["name"] for span in captured["body"]["resourceSpans"][0]["scopeSpans"][0]["spans"]]
        self.assertIn("search_products", names)
        self.assertIn("gpt-5.6-luna", names)
        self.assertIn("Đọc câu hỏi", names)
        self.assertIn("Chọn việc", names)
        self.assertIn("iPhone 16", raw)
        self.assertIn("shop-7", raw)


class RequestReadingTests(unittest.TestCase):
    def test_brand_rejections_and_latest_requirements_survive_follow_ups(self):
        from agent.requirements import consultation, extract_requirements

        history = []
        for question in (
            "tao muốn mua điện thoại để chơi game",
            "khoảng 20 triệu",
            "dưới 20 triệu thôi",
        ):
            history.append(("user", question))
        rejected = agent.resolve_request("không thích xiaomi", history)
        self.assertEqual(rejected["excluded_brands"], ["Xiaomi"])
        self.assertEqual(rejected["use"], "gaming")
        self.assertEqual(rejected["price_max"], 20_000_000)
        self.assertTrue(rejected["price_max_exclusive"])
        self.assertEqual(agent.route("không thích xiaomi", rejected, history)["tool"], "search_products")
        self.assertIsNone(consultation("không thích xiaomi", history, agent.route("không thích xiaomi", rejected, history)))

        history.append(("user", "không thích xiaomi"))
        question = "gì cũng được miễn không phải xiaomi"
        resolved = agent.resolve_request(question, history)
        extracted = extract_requirements(question, history)
        self.assertEqual(resolved["excluded_brands"], ["Xiaomi"])
        self.assertEqual(resolved["brand"], "")
        self.assertEqual(extracted["brand_exclusions"], ["Xiaomi"])
        self.assertEqual(extracted["use_cases"], ["gaming"])
        self.assertEqual(extracted["budget_max"], 20_000_000)
        self.assertIsNone(consultation(question, history, agent.route(question, resolved, history)))

        for sentence, brand in (
            ("không thích Samsung", "Samsung"),
            ("trừ Apple ra", "Apple"),
            ("hãng nào cũng được ngoài Oppo", "OPPO"),
            ("không lấy máy Xiaomi nữa", "Xiaomi"),
        ):
            self.assertEqual(agent.resolve_request(sentence)["excluded_brands"], [brand])
        switched = agent.resolve_request(
            "thôi không lấy Xiaomi", [("user", "thích Xiaomi để chơi game"), ("user", "dưới 20 triệu")]
        )
        self.assertEqual(switched["brand"], "")
        self.assertEqual(switched["excluded_brands"], ["Xiaomi"])
        cheaper = agent.resolve_request("dưới 15 triệu", history)
        self.assertEqual(cheaper["price_max"], 15_000_000)
        self.assertTrue(cheaper["price_max_exclusive"])
        camera = agent.resolve_request("giờ ưu tiên camera", history)
        self.assertEqual(camera["use"], "")
        self.assertEqual(camera["priorities"], ["camera"])
        self.assertEqual(camera["color"], "")
        self.assertEqual(extract_requirements("giờ ưu tiên camera", history)["camera_priority"], "high")
        self.assertIsNone(consultation("giờ ưu tiên camera", history, agent.route("giờ ưu tiên camera", camera, history)))

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

    def test_accounting_study_is_not_the_ai_laptop_path(self):
        request = agent.resolve_request("t muốn mua laptop học kế toán giá dưới 23 triệu")
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["use"], "")
        self.assertEqual(request["price_max"], 23_000_000)
        self.assertEqual(agent.resolve_request("Laptop nào phù hợp để học AI")["use"], "study")
        self.assertEqual(agent.resolve_request("Laptop cho sinh viên học AI")["use"], "study")
        from agent.slots import demands_ai

        coding = "mình muốn mua laptop để mang đi học, mình muốn mỏng nhẹ, chơi game tốt, học code nữa"
        self.assertFalse(demands_ai(coding))
        self.assertTrue(demands_ai("Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin."))
        self.assertEqual(agent.resolve_request(coding)["use"], "gaming")
        self.assertEqual(agent.resolve_request("laptop để học code")["use"], "")

    def test_turn_guards_keep_ai_study_and_mark_a_light_office_follow_up(self):
        from agent.graph import apply_turn_guards

        ai = {"use": "study", "priorities": ["ram", "battery"]}
        apply_turn_guards("Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin.", [], ai)
        self.assertEqual(ai["use"], "study")
        self.assertEqual(ai["priorities"], ["ram", "battery"])
        office = {"use": "study", "priorities": []}
        apply_turn_guards(
            "ưu tiên máy nhẹ, pin dùng được cả ngày",
            [("user", "t muốn mua laptop học kế toán giá dưới 23 triệu")],
            office,
        )
        self.assertEqual(office["use"], "")
        self.assertEqual(office["priorities"], ["weight", "battery"])
        coded = {"use": "study", "priorities": []}
        apply_turn_guards(
            "khoảng 20 triệu",
            [("user", "mình muốn mua laptop để mang đi học, mình muốn mỏng nhẹ, chơi game tốt, học code nữa")],
            coded,
        )
        self.assertEqual(coded["use"], "gaming")
        self.assertIn("weight", coded["priorities"])

    def test_a_battery_or_weight_overclaim_is_rewritten_from_the_spec(self):
        from agent.graph import _ground_intro, _ground_reason

        product = {
            "specs": [
                {"name": "Chip", "value": "Intel Core 5 210H"},
                {"name": "RAM", "value": "16 GB"},
                {"name": "Màn hình", "value": '14"'},
                {"name": "Pin", "value": "70 Wh"},
            ],
        }
        text = _ground_reason(
            "Chip i5 và RAM 16 GB, hợp mở bảng tính. Pin 70 Wh nên dùng cả ngày, máy lại nhẹ.",
            product,
        )
        self.assertIn("bảng tính", text)
        self.assertNotIn("cả ngày", text.casefold())
        self.assertNotIn("nhẹ", text.casefold())
        self.assertIn("70 Wh", text)
        self.assertIn("chưa", text)
        self.assertNotIn('"', text)
        kept = _ground_reason("Chip i5 và RAM 16 GB, hợp mở bảng tính.", product)
        self.assertEqual(kept, "Chip i5 và RAM 16 GB, hợp mở bảng tính.")
        lead = _ground_intro(
            "Đây là laptop nhẹ, pin tốt.",
            [{"specs": [{"name": "Màn hình", "value": '14"'}]}],
            {"price_max": 18_000_000, "price_max_exclusive": True},
            "thế tầm 18 triệu thì có máy nào gọn hơn không",
        )
        self.assertNotIn("nhẹ", lead.casefold())
        self.assertNotIn("pin tốt", lead.casefold())
        self.assertIn("Trong tầm 18 triệu", lead)
        self.assertNotIn("dưới 18", lead.casefold())
        crossed = _ground_reason(
            "Samsung Galaxy S26+ 5G có pin 4900 mAh, thấp hơn iPhone 16 nhưng vẫn đủ để đáp ứng nhu cầu sử dụng hàng ngày.",
            {"specs": [
                {"name": "Chip", "value": "Exynos 2600"},
                {"name": "RAM", "value": "12 GB"},
                {"name": "Màn hình", "value": '6.7" - Tần số quét 120 Hz'},
                {"name": "Pin", "value": "4900 mAh"},
            ]},
        )
        self.assertIn("4900 mAh", crossed)
        self.assertIn("chưa", crossed.casefold())
        self.assertNotIn("thấp hơn", crossed.casefold())
        self.assertNotIn("hàng ngày", crossed.casefold())
        self.assertNotIn('"', crossed)

    def test_a_named_iphone_is_not_turned_into_a_budget_question(self):
        from agent.graph import pin_named_model

        resolved = {"category": "", "query": "", "brand": "", "family": "", "use": ""}
        self.assertTrue(pin_named_model("t muốn mua iphone 16", resolved))
        self.assertEqual(resolved["query"], "iPhone 16")
        self.assertEqual(resolved["family"], "iPhone")
        self.assertEqual(resolved["category"], "phone")
        vague = {"category": "phone", "use": "gaming", "query": ""}
        self.assertFalse(pin_named_model("t muốn mua điện thoại để chơi game", vague))
        self.assertEqual(vague["query"], "")
        corrected = {"category": "", "query": "", "brand": "", "family": "", "use": ""}
        self.assertTrue(pin_named_model("16 pro max cơ", corrected))
        self.assertEqual(corrected["query"], "iPhone 16 Pro Max")
        self.assertEqual(corrected["variant"], "pro max")
        self.assertEqual(corrected["category"], "phone")

    def test_a_discount_price_stays_on_the_phone_being_bargained(self):
        from agent.graph import bargain_turn

        resolved = {
            "category": "phone", "query": "", "brand": "", "family": "",
            "price_max": 13_000_000, "price_max_exclusive": True, "price_target": None,
        }
        history = [
            ("user", "phone 16 có bớt đc k"),
            ("assistant", "Bạn muốn giảm giá bao nhiêu cho iPhone 16?"),
        ]
        decision = bargain_turn("giá 13 triệu", history, resolved)
        self.assertEqual(decision["mode"], "quote")
        self.assertEqual(resolved["query"], "iPhone 16")
        self.assertIsNone(resolved["price_max"])
        self.assertEqual(resolved["bargain_offer"], 13_000_000)
        self.assertIsNone(bargain_turn(
            "tầm 15 triệu",
            [("user", "t muốn mua điện thoại để chơi game")],
            {"category": "phone", "price_target": 15_000_000},
        ))

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

    def test_a_new_budget_replaces_the_previous_ceiling(self):
        history = [("user", "Tìm iPhone dưới 20 triệu")]
        request = agent.resolve_request(
            "Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin.",
            history,
        )
        self.assertIsNone(request["price_max"])
        self.assertEqual(request["price_target"], 25_000_000)
        self.assertEqual(request["category"], "laptop")
        self.assertEqual(request["use"], "study")


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
        wish = "t muốn mua điện thoại để chơi game"
        self.assertEqual(agent.route(wish, agent.resolve_request(wish))["tool"], "prepare_checkout")

    def test_a_wish_asks_for_budget_before_a_form_or_a_search(self):
        from agent.graph import run_shop_graph
        from agent.requirements import DEFAULT_RULES, PROMPT, consultation, follow_up_arguments

        self.assertIn("budget", PROMPT.casefold())
        self.assertIn("không tự suy diễn", PROMPT.casefold())
        self.assertEqual(DEFAULT_RULES["ai"]["ram_min"], 16)
        self.assertEqual(DEFAULT_RULES["ai"]["storage_gb"], 512)
        wish = "t muốn mua điện thoại để chơi game"
        decision = agent.route(wish, agent.resolve_request(wish))
        chosen = consultation(wish, [], decision)
        self.assertEqual(chosen[0], "ask")
        self.assertIn("ngân sách", chosen[2].casefold())
        self.assertNotIn("màu", chosen[2].casefold())
        self.assertNotIn("ram", chosen[2].casefold())
        typo = consultation("t muốn mua điên thoại để chơi game", [], decision)
        self.assertEqual(typo[0], "ask")
        self.assertIn("điện thoại", typo[2].casefold())
        carry = "T cần laptop 25 triệu để code AI, mang đi học nhiều."
        carry_resolved = agent.resolve_request(carry)
        self.assertEqual(carry_resolved["price_target"], 25_000_000)
        self.assertIsNone(carry_resolved["price_max"])
        carry_decision = agent.route(carry, carry_resolved)
        carry_choice = consultation(carry, [], carry_decision)
        self.assertEqual(carry_choice[0], "ask")
        self.assertIn("gpu", carry_choice[2].casefold())
        ready = "Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin."
        ready_decision = agent.route(ready, agent.resolve_request(ready))
        self.assertIsNone(consultation(ready, [], ready_decision))
        close = consultation("Mua giúp tôi iPhone 17", [], {"tool": "prepare_checkout"})
        self.assertIsNone(close)
        switched = consultation(
            "Thôi, cho tôi iPhone",
            [("user", "Đặt MacBook Air cho tôi")],
            {"tool": "prepare_checkout"},
        )
        self.assertIsNone(switched)
        self.assertIsNone(consultation("xin chào", [], {"tool": "none"}))
        self.assertIsNone(consultation(
            "cảm ơn",
            [("user", "Tìm laptop học AI"), ("bot", "Có vài laptop.")],
            {"tool": "none"},
        ))
        budget_history = [("user", wish)]
        priced = agent.resolve_request("15 triệu", budget_history)
        self.assertEqual(priced["category"], "phone")
        self.assertEqual(priced["use"], "gaming")
        self.assertEqual(priced["price_target"], 15_000_000)
        priced_route = agent.route("15 triệu", priced, budget_history)
        self.assertEqual(priced_route["tool"], "search_products")
        self.assertIsNone(consultation("15 triệu", budget_history, priced_route))
        tradeoff_history = [
            ("user", carry),
            ("bot", carry_choice[2]),
        ]
        gpu_pick = consultation("GPU mạnh hơn", tradeoff_history, {"tool": "none"})
        self.assertEqual(gpu_pick[0], "search_products")
        self.assertEqual(follow_up_arguments("GPU mạnh hơn", tradeoff_history), {})
        pin_pick = consultation("pin và máy nhẹ hơn", tradeoff_history, {"tool": "none"})
        self.assertEqual(pin_pick[0], "search_products")
        self.assertEqual(follow_up_arguments("pin và máy nhẹ hơn", tradeoff_history), {"priorities": ["battery"]})
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            plan = provider_plan("ask", agent.resolve_request(wish), "Ngân sách của bạn cho điện thoại để chơi game khoảng bao nhiêu?")
            with patch("agent.understand.understand_turn", return_value=plan):
                with patch("agent.model.urllib.request.urlopen") as opened:
                    spoken = run_shop_graph(None, {}, wish)
            opened.assert_not_called()
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        self.assertIsNone(spoken["checkout"])
        self.assertEqual(spoken["products"], [])
        self.assertIn("ngân sách", spoken["text"].casefold())
        self.assertIn("chơi game", spoken["text"].casefold())
        self.assertEqual(spoken["trace"][1]["tool"], "ask")
        self.assertEqual([step["kind"] for step in spoken["trace"]], ["slots", "intent", "explain"])
        self.assertNotIn("màu", spoken["text"].casefold())

    def test_requirement_state_follows_the_prompt_contract(self):
        from agent.requirements import extract_requirements

        ai = extract_requirements("t cần laptop để học AI")
        self.assertIn("ai", ai["use_cases"])
        self.assertTrue(ai["gpu_required"])
        self.assertIsNone(ai["ram_min"])
        self.assertIsNone(ai["ssd_min"])
        self.assertEqual(ai["brand_preferences"], [])
        hated = extract_requirements("không thích Samsung")
        self.assertIn("Samsung", hated["brand_exclusions"])
        self.assertNotIn("Samsung", hated["brand_preferences"])
        self.assertIsNone(hated["ram_min"])
        span = agent.resolve_request("laptop 20 đến 25 triệu")
        self.assertEqual(span["price_min"], 20_000_000)
        self.assertEqual(span["price_max"], 25_000_000)
        self.assertIsNone(span["price_target"])
        stretched = agent.resolve_request(
            "có thể cố thêm 2 triệu",
            [("user", "Tầm 25 triệu, cần laptop để code AI")],
        )
        self.assertEqual(stretched["price_max"], 27_000_000)
        self.assertIsNone(stretched["price_target"])
        self.assertEqual(stretched["use"], "study")
        carry = extract_requirements("T cần laptop 25 triệu để code AI, mang đi học nhiều.")
        self.assertEqual(carry["portability"], "high")
        self.assertIsNone(carry["weight_priority"])
        self.assertEqual(carry["budget_target"], 25_000_000)
        self.assertIsNone(carry["budget_max"])
        self.assertIsNone(carry["ram_min"])
        library = extract_requirements("tai nghe để học thư viện")
        self.assertEqual(library["category"], "headphones")
        self.assertIsNone(library["anc_priority"])

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
            [
                "search_products",
                "get_product",
                "compare_products",
                "check_inventory",
                "list_orders",
                "prepare_checkout",
                "search_documents",
            ],
        )
        documents = agent.TOOLS[-1]["function"]
        self.assertEqual(documents["name"], "search_documents")
        self.assertIn("bảo hành", documents["description"].casefold())
        self.assertIn("Không dùng để tìm giá", documents["description"])
        self.assertIn("warranty", documents["parameters"]["properties"]["doc_type"]["enum"])
        search = agent.TOOLS[0]["function"]["parameters"]["properties"]
        self.assertIn("Không hỏi màu", search["color"]["description"])
        self.assertIn("MacBook", search["brand"]["description"])
        self.assertIn("storage_gb", search)
        self.assertIn("min_ram", search)
        self.assertIn("iPhone Pro", search["line"]["description"])
        orders = next(tool for tool in agent.TOOLS if tool["function"]["name"] == "list_orders")
        self.assertEqual(orders["function"]["parameters"]["properties"], {})

    def test_document_search_does_not_attach_product_cards(self):
        with patch("rag.search.search_documents", return_value={"note": "không có", "passages": []}):
            result, products, checkout = agent.model._run_tool(
                None, {}, "search_documents", {"query": "bảo hành OPPO", "doc_type": "warranty"}
            )
        self.assertEqual(products, [])
        self.assertIsNone(checkout)
        self.assertEqual(result["note"], "không có")

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

    def test_the_live_graph_explains_once_after_the_tool(self):
        saved = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"
        answers = [
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
                    with patch("agent.understand.understand_turn", return_value=provider_plan("search_products", agent.resolve_request("Tìm iPhone dưới 20 triệu"))):
                        spoken = agent.answer_with_openai(None, {}, "Tìm iPhone dưới 20 triệu")
            self.assertEqual(opened.call_count, 1)
            sent = json.loads(opened.call_args_list[0].args[0].data.decode())
            self.assertNotIn("tools", sent)
            self.assertIn("search_documents", sent["messages"][0]["content"])
            self.assertIn("Bạn là trợ lý bán hàng của Octopus Store", sent["messages"][0]["content"])
            self.assertIn("Giữ nguyên thứ tự", sent["messages"][0]["content"])
            self.assertNotIn("test-key", sent["messages"][0]["content"])
            self.assertEqual(spoken["text"], "Có vài điện thoại trong tầm.")
            self.assertEqual(spoken["text_from"], "model")
            self.assertEqual(spoken["products"][0]["name"], "iPhone 16e")
            self.assertIsNone(spoken["checkout"])
            self.assertEqual([step["kind"] for step in spoken["trace"]], ["slots", "intent", "tool", "model"])
            self.assertEqual([step["type"] for step in spoken["trace"]], ["SPAN", "SPAN", "TOOL", "GENERATION"])
            self.assertEqual(spoken["trace"][2]["name"], "search_products")
            self.assertEqual(spoken["trace"][-1]["text"], "Có vài điện thoại trong tầm.")
            self.assertEqual(spoken["trace"][-1]["calls"], [])
            self.assertEqual(spoken["trace"][1]["input"]["question"], "Tìm iPhone dưới 20 triệu")
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

    def test_near_miss_warning_survives_an_overoptimistic_model_answer(self):
        saved = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"
        answers = [
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
            self.assertEqual(name, "search_products")
            product = {"name": "Thunderobot Gaming 911 S", "product_id": 9, "price": 19_490_000}
            return {
                "products": [product],
                "near_miss": True,
                "lead": "Không có laptop đủ GPU trong tầm 20 triệu.",
            }, [product], None

        try:
            with patch("agent.model.urllib.request.urlopen", side_effect=[Response(item) for item in answers]):
                with patch("agent.model._run_tool", side_effect=fake_tool):
                    with patch("agent.understand.understand_turn", return_value=provider_plan("search_products", agent.resolve_request("Laptop dưới 25 triệu học AI được"))):
                        spoken = agent.answer_with_openai(None, {}, "Laptop dưới 25 triệu học AI được")
            self.assertEqual(spoken["text"], "Không có laptop đủ GPU trong tầm 20 triệu.")
            self.assertEqual(spoken["text_from"], "model")
            self.assertEqual(spoken["products"][0]["name"], "Thunderobot Gaming 911 S")
            self.assertEqual(spoken["trace"][2]["result"]["lead"], "Không có laptop đủ GPU trong tầm 20 triệu.")
        finally:
            if saved is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = saved

    def test_offline_route_does_not_call_langgraph_or_qdrant(self):
        source = inspect.getsource(agent.route)
        folded = source.casefold()
        self.assertNotIn("langgraph", folded)
        self.assertNotIn("qdrant", folded)
        self.assertNotIn("openai", folded)
        self.assertNotIn("search_documents", folded)
        question = "Tai nghe Philips bảo hành bao lâu"
        before = set(sys.modules)
        decision = agent.route(question)
        added = set(sys.modules) - before
        self.assertFalse(any("langgraph" in name or "qdrant" in name or "openai" in name for name in added))
        self.assertNotEqual(decision["tool"], "search_documents")
        self.assertEqual(decision["tool"], "search_products")


class CatalogReadTests(unittest.TestCase):
    def setUp(self):
        try:
            self.conn = psycopg.connect("dbname=tgdd_products", autocommit=True)
        except Exception as exc:
            self.skipTest(f"không mở được tgdd_products: {exc}")
        self.addCleanup(self.conn.close)

    def test_excluded_brand_and_budget_are_hard_filters_in_live_graph(self):
        from agent.graph import run_shop_graph

        history = [("user", line) for line in (
            "tao muốn mua điện thoại để chơi game",
            "khoảng 20 triệu",
            "dưới 20 triệu thôi",
            "không thích xiaomi",
        )]
        question = "gì cũng được miễn không phải xiaomi"
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with patch("agent.understand.understand_turn", return_value=provider_plan("search_products", agent.resolve_request(question, history))):
                spoken = run_shop_graph(self.conn, {}, question, history)
        self.assertTrue(spoken["products"])
        self.assertEqual(spoken["trace"][2]["name"], "search_products")
        self.assertEqual(spoken["trace"][2]["ran"]["excluded_brands"], ["Xiaomi"])
        self.assertEqual(spoken["trace"][2]["ran"]["price_max"], 20_000_000)
        for product in spoken["products"]:
            self.assertNotIn("xiaomi", (product["name"] + product["brand"]).casefold())
            self.assertLess(product["price"], 20_000_000)
        narrower = agent.resolve_request("dưới 15 triệu", history)
        narrowed_products = agent.search_products(self.conn, **narrower)["products"]
        self.assertTrue(narrowed_products)
        for product in narrowed_products:
            self.assertNotIn("xiaomi", (product["name"] + product["brand"]).casefold())
            self.assertLess(product["price"], 15_000_000)
        impossible = agent.search_products(
            self.conn, category="phone", brand="Xiaomi", excluded_brands=["Xiaomi"], price_max=20_000_000
        )
        self.assertEqual(impossible["products"], [])
        self.assertIn("Không thấy", impossible["note"])

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

    def test_office_budget_shows_distinct_models_and_a_compact_follow_up(self):
        found = agent.search_products(
            self.conn, category="laptop", price_max=23_000_000, price_max_exclusive=True, limit=3,
        )
        products = found["products"]
        self.assertEqual(len(products), 3)
        self.assertNotIn("học AI", found.get("note") or "")
        self.assertEqual(len({_visible_model(item["name"]) for item in products}), 3)
        for item in products:
            self.assertLess(item["price"], 23_000_000)
        light = agent.search_products(
            self.conn,
            category="laptop",
            price_max=23_000_000,
            price_max_exclusive=True,
            priorities=["weight", "battery"],
            limit=3,
        )
        picked = light["products"]
        self.assertEqual(len(picked), 3)
        self.assertNotIn("học AI", light.get("note") or "")
        self.assertIn("Wh", light.get("note") or "")
        self.assertEqual(len({_visible_model(item["name"]) for item in picked}), 3)
        for item in picked:
            self.assertLess(_screen_inches(item), 15)
            self.assertLess(item["price"], 23_000_000)
        self.assertGreater(agent._battery_wh(picked[0]), 60)

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
        three = agent.compare_products(self.conn, "So sánh iPhone 16, iPhone 16 Plus và iPhone 16e")
        three_names = [product["name"].casefold() for product in three["products"]]
        self.assertEqual(len(three_names), 3, three_names)
        self.assertEqual(len(three_names), len(set(three_names)))
        base = [
            name for name in three_names
            if "iphone 16" in name and "plus" not in name and "16e" not in name and "pro" not in name
        ]
        self.assertEqual(len(base), 1, three_names)
        self.assertTrue(any("iphone 16 plus" in name for name in three_names), three_names)
        self.assertTrue(any("iphone 16e" in name for name in three_names), three_names)

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

    def test_restated_budget_keeps_the_same_near_miss_order(self):
        question = "Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin."
        history = [("user", "Tìm iPhone dưới 20 triệu"), ("assistant", "iPhone 16e")]
        followed = agent.search_products(self.conn, **agent.resolve_request(question, history))
        alone = agent.search_products(self.conn, **agent.resolve_request(question))
        self.assertEqual(
            [item["product_id"] for item in followed["products"]],
            [item["product_id"] for item in alone["products"]],
        )
        self.assertTrue(followed.get("near_miss"))

    def test_macbook_ai_around_25_million_stays_inside_budget(self):
        request = agent.resolve_request("Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin.")
        found = agent.search_products(self.conn, **request)
        self.assertTrue(found.get("near_miss"))
        products = found["products"]
        self.assertTrue(products, found.get("note"))
        others = [product for product in products if "macbook" not in product["name"].casefold()]
        self.assertEqual(products, others)
        self.assertIn("dưới", found["note"].casefold())
        self.assertIn("neo", found["note"].casefold())
        self.assertTrue(any(product["fit"] == "strong" for product in others))
        self.assertGreaterEqual(len({agent._line_key(product) for product in others}), len(others))
        for product in others:
            self.assertLessEqual(product["price"], 25_000_000)
            self.assertIn("Dưới", product["reason"])

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

    def test_buying_a_named_iphone_searches_instead_of_asking_the_budget(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            asked = provider_plan("ask", {"category": "", "query": "", "use": ""}, ask="Bạn dự định chi khoảng bao nhiêu?")
            gaming = provider_plan("search_products", {
                "category": "phone", "use": "gaming", "query": "", "brand": "", "family": "",
                "price_min": None, "price_max": None, "price_target": None, "specific": False,
            })
            with patch("agent.understand.understand_turn", return_value=asked):
                bought = run_shop_graph(self.conn, {}, "t muốn mua iphone 16")
            with patch("agent.understand.understand_turn", return_value=gaming):
                wish = run_shop_graph(self.conn, {}, "t muốn mua điện thoại để chơi game")
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        names = [product["name"].casefold() for product in bought["products"]]
        self.assertTrue(names, bought["text"])
        for name in names:
            self.assertIn("iphone 16", name)
            self.assertNotIn("plus", name)
            self.assertNotIn("16e", name)
        self.assertEqual(bought["products"][0]["price"], 24_990_000)
        self.assertNotIn("bao nhiêu", bought["text"].casefold())
        self.assertIsNone(bought["checkout"])
        self.assertEqual(wish["products"], [])
        self.assertEqual(wish["trace"][1]["tool"], "ask")
        self.assertIsNone(wish["checkout"])
        plus = agent.search_products(
            self.conn, category="phone", query="iPhone 16 Plus", brand="Apple", family="iPhone", variant="plus", limit=3,
        )
        self.assertTrue(plus["products"])
        for product in plus["products"]:
            self.assertIn("plus", product["name"].casefold())

    def test_a_missing_pro_max_is_not_replaced_by_a_newer_one(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            asked = provider_plan("ask", {"category": "", "query": "", "use": ""}, ask="Bạn dự định chi khoảng bao nhiêu?")
            history = [
                ("user", "t muốn mua iphone 16 pro max"),
                ("bot", '<input type="hidden" name="product_id" value="361270">'),
            ]
            with patch("agent.understand.understand_turn", return_value=asked):
                bought = run_shop_graph(self.conn, {}, "t muốn mua iphone 16 pro max")
                reply = run_shop_graph(self.conn, {}, "16 pro max cơ", history)
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        for spoken in (bought, reply):
            self.assertEqual(spoken["products"], [])
            self.assertIn("iPhone 16 Pro Max", spoken["text"])
            self.assertIn("không thấy", spoken["text"].casefold())
            self.assertNotIn("bao nhiêu", spoken["text"].casefold())
            self.assertIsNone(spoken["checkout"])
            for product_name in ("iphone 17", "iphone 18"):
                self.assertNotIn(product_name, " ".join(
                    product["name"].casefold() for product in spoken["products"]
                ))
        direct = agent.search_products(
            self.conn, category="phone", query="iPhone 16 Pro Max", brand="Apple",
            family="iPhone", variant="pro max",
        )
        self.assertEqual(direct["products"], [])
        self.assertIn("iPhone 16 Pro Max", direct["note"])
        self.assertIn("iPhone 17 Pro Max", direct["note"])
        self.assertIn("iPhone 18 Pro Max", direct["note"])

    def test_learning_to_code_does_not_search_for_ai(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            plan = provider_plan("search_products", {
                "category": "laptop", "brand": "", "query": "", "use": "study",
                "family": "", "line": "", "variant": "", "chip": "", "specific": False,
                "price_min": None, "price_max": None, "price_target": 20_000_000,
                "priorities": [],
            })
            history = [(
                "user",
                "mình muốn mua laptop để mang đi học, mình muốn mỏng nhẹ, chơi game tốt, học code nữa",
            )]
            with patch("agent.understand.understand_turn", return_value=plan):
                spoken = run_shop_graph(self.conn, {}, "khoảng 20 triệu", history)
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        self.assertEqual(spoken["trace"][0]["arguments"]["use"], "gaming")
        self.assertIsNone(spoken["checkout"])
        self.assertTrue(spoken["products"])
        blob = spoken["text"]
        for product in spoken["products"]:
            blob += " " + (product.get("reason") or "")
            blob += " " + (product.get("name") or "")
        self.assertNotIn("học ai", blob.casefold())
        self.assertNotIn("gpu tích hợp, học", blob.casefold())

    def test_a_category_question_lists_brands_instead_of_asking_budget(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            plan = provider_plan("search_products", {
                "category": "phone", "brand": "", "query": "", "use": "",
                "family": "", "line": "", "variant": "", "chip": "", "specific": False,
                "price_min": None, "price_max": None, "price_target": None,
            })
            with patch("agent.understand.understand_turn", return_value=plan):
                spoken = run_shop_graph(self.conn, {}, "shop có những điện thoại gì")
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        from agent.retrieve import list_category

        brands = list_category(self.conn, "phone")["brands"]
        self.assertGreater(len(brands), 1)
        self.assertEqual(spoken["trace"][1]["tool"], "list_category")
        self.assertEqual(spoken["products"], [])
        self.assertIsNone(spoken["checkout"])
        self.assertIn(brands[0]["brand"], spoken["text"])
        self.assertIn("brand-chip", spoken["text"])
        self.assertNotIn("bao nhiêu", spoken["text"].casefold())
        self.assertNotIn("dự định chi", spoken["text"].casefold())

    def test_asking_whether_a_brand_exists_searches_that_brand(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            exists = provider_plan("check_inventory", {
                "category": "phone", "brand": "", "query": "asus", "use": "",
                "family": "", "line": "", "variant": "", "chip": "", "specific": False,
            })
            stock = provider_plan("check_inventory", {
                "category": "phone", "brand": "Apple", "query": "iPhone 16",
                "family": "iPhone", "use": "", "specific": False,
            })
            with patch("agent.understand.understand_turn", return_value=exists):
                spoken = run_shop_graph(self.conn, {}, "có điện thoại asus không")
            with patch("agent.understand.understand_turn", return_value=stock):
                counted = run_shop_graph(self.conn, {}, "iPhone 16 còn hàng không")
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        self.assertEqual(spoken["trace"][1]["tool"], "search_products")
        self.assertEqual(spoken["trace"][1]["model_action"], "check_inventory")
        self.assertEqual(spoken["products"], [])
        self.assertIn("asus", spoken["text"].casefold())
        self.assertNotIn("tồn kho", spoken["text"].casefold())
        self.assertNotIn("bao nhiêu", spoken["text"].casefold())
        self.assertIsNone(spoken["checkout"])
        self.assertEqual(counted["trace"][1]["tool"], "check_inventory")
        self.assertTrue(counted["products"])
        self.assertIn("còn", counted["text"].casefold())

    def test_bargaining_an_iphone_quotes_the_list_price(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            wrong = provider_plan("search_products", {
                "category": "phone",
                "query": "",
                "brand": "",
                "family": "",
                "use": "",
                "price_max": 13_000_000,
                "price_max_exclusive": True,
                "price_target": None,
                "price_min": None,
                "specific": False,
                "cheapest": False,
            })
            history = [
                ("user", "phone 16 có bớt đc k"),
                ("assistant", "<p>Bạn muốn giảm giá bao nhiêu cho iPhone 16?</p>"),
            ]
            with patch("agent.understand.understand_turn", return_value=wrong):
                with patch("agent.model.urllib.request.urlopen") as opened:
                    spoken = run_shop_graph(
                        self.conn, {}, "giá 13 triệu", history,
                    )
            opened.assert_not_called()
            opening = provider_plan("ask", {"category": "phone"}, ask="Bạn muốn giảm bao nhiêu?")
            with patch("agent.understand.understand_turn", return_value=opening):
                asked = run_shop_graph(self.conn, {}, "phone 16 có bớt đc k")
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        names = [product["name"].casefold() for product in spoken["products"]]
        self.assertTrue(names, spoken["text"])
        for name in names:
            self.assertIn("iphone 16", name)
            self.assertNotIn("plus", name)
            self.assertNotIn("16e", name)
            self.assertNotIn("samsung", name)
        self.assertEqual(spoken["products"][0]["price"], 24_990_000)
        self.assertIn("24.990.000", spoken["text"])
        self.assertIn("13 triệu", spoken["text"])
        self.assertIn("không bớt", spoken["text"])
        self.assertIsNone(spoken["checkout"])
        self.assertIn("24.990.000", asked["text"])
        self.assertIn("bao nhiêu", asked["text"].casefold())
        self.assertEqual(asked["products"], [])

    def test_this_price_means_the_phone_already_on_screen(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            kept = provider_plan("search_products", {
                "category": "phone",
                "query": "iPhone 16",
                "brand": "Apple",
                "family": "iPhone",
                "use": "gaming",
                "price_min": None,
                "price_max": None,
                "price_target": None,
                "specific": False,
                "cheapest": False,
            })
            history = [
                ("user", "t muốn mua iphone 16"),
                ("bot", '<p class="chat-lead">iPhone 16 có tần số quét 60 Hz.</p>'
                 '<p class="family-price">24.990.000₫<span>Còn 181</span></p>'),
            ]
            question = "thế cho t xem mấy máy tần số quét cao hơn, tầm giá này"
            with patch("agent.understand.understand_turn", return_value=kept):
                spoken = run_shop_graph(self.conn, {}, question, history)
            cheaper = provider_plan("search_products", {
                "category": "phone",
                "query": "",
                "brand": "",
                "family": "",
                "use": "",
                "price_target": 15_000_000,
                "price_min": None,
                "price_max": None,
                "specific": False,
            })
            with patch("agent.understand.understand_turn", return_value=cheaper):
                capped = run_shop_graph(
                    self.conn, {}, "thế tầm 15 triệu thì có máy quét cao không", history,
                )
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved

        def hz_of(product):
            screen = next((spec["value"] for spec in product["specs"] if spec["name"] == "Màn hình"), "")
            match = re.search(r"(\d+)\s*hz", screen, re.I)
            return int(match.group(1)) if match else 0

        products = spoken["products"]
        self.assertTrue(products, spoken["text"])
        self.assertNotIn("bao nhiêu", spoken["text"].casefold())
        self.assertIsNone(spoken["checkout"])
        self.assertIn("tần số quét", spoken["text"].casefold())
        for product in products:
            self.assertLessEqual(product["price"], 24_990_000)
            self.assertGreater(hz_of(product), 60)
            self.assertNotIn("iphone 16", product["name"].casefold())
        self.assertTrue(capped["products"], capped["text"])
        for product in capped["products"]:
            self.assertLessEqual(product["price"], 15_000_000)
            self.assertGreater(hz_of(product), 60)

    def test_these_phones_keep_the_cards_on_screen(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph

            wrong = provider_plan("compare_products", {
                "category": "phone",
                "query": "Xiaomi 17 Ultra",
                "brand": "Xiaomi",
                "family": "",
                "use": "",
                "price_target": None,
                "specific": False,
            })
            cards = "".join(
                '<input type="hidden" name="product_id" value="%s">' % ident
                for ident in (361269, 370849, 361949)
            )
            history = [
                ("user", "thế cho t xem mấy máy tần số quét cao hơn, tầm giá này"),
                ("bot", '<p class="chat-lead">Máy quét cao hơn.</p>' + cards),
            ]
            question = "pin mấy máy này so với iphone 16 lúc nãy thì sao, có trâu hơn không"
            with patch("agent.understand.understand_turn", return_value=wrong):
                spoken = run_shop_graph(self.conn, {}, question, history)
            challenge = provider_plan("search_products", {
                "category": "phone", "query": "", "brand": "", "family": "", "use": "",
                "price_target": None, "price_min": None, "price_max": None, "specific": False,
            })
            challenged = [
                ("user", question),
                ("bot", cards + '<input type="hidden" name="product_id" value="329135">'),
            ]
            with patch("agent.understand.understand_turn", return_value=challenge):
                reply = run_shop_graph(
                    self.conn, {},
                    "cậu bảo Galaxy pin thấp hơn iPhone là thấp chỗ nào, hai bên khác đơn vị mà",
                    challenged,
                )
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        names = [product["name"].casefold() for product in spoken["products"]]
        self.assertEqual(len(names), 4, names)
        self.assertTrue(any("xiaomi 17" in name and "ultra" not in name for name in names))
        self.assertTrue(any("poco f9 ultra" in name for name in names))
        self.assertTrue(any("s26+" in name for name in names))
        self.assertTrue(any(name.startswith("điện thoại iphone 16") or "iphone 16 " in name for name in names))
        self.assertFalse(any("17 ultra" in name for name in names))
        self.assertIn("không kết luận", spoken["text"].casefold())
        self.assertNotIn("trâu hơn", spoken["text"].casefold())
        self.assertIn("mAh", spoken["text"])
        self.assertIsNone(spoken["checkout"])
        reply_names = [product["name"].casefold() for product in reply["products"]]
        self.assertTrue(any("s26+" in name for name in reply_names), reply_names)
        self.assertTrue(any("iphone 16" in name for name in reply_names), reply_names)
        self.assertNotIn("bao nhiêu", reply["text"].casefold())
        self.assertIsNone(reply["checkout"])

    def test_live_graph_keeps_the_near_miss_card_order(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            question = "Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin."
            request = agent.resolve_request(question)
            expected = agent.search_products(self.conn, **request)
            from agent.graph import run_shop_graph
            with patch("agent.understand.understand_turn", return_value=provider_plan("search_products", request)):
                with patch("agent.model.urllib.request.urlopen") as opened:
                    spoken = run_shop_graph(self.conn, {}, question)
            opened.assert_not_called()
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        self.assertEqual(
            [item["product_id"] for item in spoken["products"]],
            [item["product_id"] for item in expected["products"]],
        )
        products = spoken["products"]
        others = [item for item in products if "macbook" not in item["name"].casefold()]
        self.assertEqual(products, others)
        self.assertTrue(others)
        for item in others:
            self.assertLessEqual(item["price"], 25_000_000)
        self.assertIn("25 triệu", (spoken["text"] or "").casefold())
        self.assertEqual(spoken["trace"][2]["name"], "search_products")

    def test_live_graph_does_not_borrow_a_warranty_from_another_brand(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph
            with patch("rag.search.embed_texts") as embed:
                with patch("agent.understand.understand_turn", return_value=provider_plan("search_documents", {"brand": "Philips"})):
                    with patch("agent.model.urllib.request.urlopen") as opened:
                        spoken = run_shop_graph(self.conn, {}, "Tai nghe Philips bảo hành bao lâu")
            embed.assert_not_called()
            opened.assert_not_called()
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved
        text = spoken["text"]
        self.assertIn("Đừng lấy điều khoản hãng khác", text)
        folded = text.casefold()
        for brand in ("xiaomi", "samsung", "apple", "oppo"):
            self.assertNotIn(brand, folded)
        self.assertEqual(spoken["products"], [])
        self.assertEqual(spoken["trace"][2]["name"], "search_documents")

    def test_admin_tracing_and_product_edit_modal(self):
        import server

        home = server.render_admin(self.conn)
        self.assertIn('href="/admin/tracing"', home)
        self.assertNotIn('href="/tracing"', home)
        listing = server.render_admin_products(self.conn, "", 1, "phone")
        self.assertIn('id="product-edit"', listing)
        self.assertIn('class="admin-edit"', listing)
        self.assertNotRegex(listing, r'href="/admin/\d+">Sửa</a>')
        self.assertIn(">Sửa</button>", listing)

    def test_live_graph_does_not_quote_terms_for_a_brand_outside_the_denylist(self):
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            from agent.graph import run_shop_graph
            from rag.search import gap_brand, search_documents

            questions = (
                "Tai nghe Marshall bảo hành bao lâu",
                "Điện thoại Tecno bảo hành bao lâu",
            )
            for question in questions:
                self.assertEqual(gap_brand(question), "")
                with patch("rag.search.embed_texts") as embed:
                    with patch("agent.understand.understand_turn", return_value=provider_plan("search_documents")):
                        with patch("agent.model.urllib.request.urlopen") as opened:
                            found = search_documents(question, doc_type="warranty")
                            spoken = run_shop_graph(self.conn, {}, question)
                embed.assert_not_called()
                opened.assert_not_called()
                self.assertEqual(found["passages"], [])
                self.assertIn("Đừng lấy điều khoản hãng khác", found["note"])
                text = spoken["text"]
                self.assertIn("Đừng lấy điều khoản hãng khác", text)
                folded = text.casefold()
                for brand in ("xiaomi", "samsung", "apple", "oppo", "realme"):
                    self.assertNotIn(brand, folded)
                self.assertNotIn("passages", spoken["trace"][2].get("result") or {})
                self.assertEqual(spoken["products"], [])
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved


class OrderWriteTests(unittest.TestCase):
    def test_place_shop_order_writes_and_rejects_atomically(self):
        from agent.ordersql import ensure_order_sql

        setup = psycopg.connect("dbname=tgdd_products", autocommit=True)
        try:
            ensure_order_sql(setup)
            user = setup.execute(
                "SELECT id FROM app_users WHERE email=%s",
                ("khach@form.local",),
            ).fetchone()
            product = setup.execute(
                """
                SELECT source_product_id, stock
                FROM products
                WHERE is_live_catalog AND stock > 2
                ORDER BY source_product_id
                LIMIT 1
                """
            ).fetchone()
            self.assertIsNotNone(user)
            self.assertIsNotNone(product)
            trigger = setup.execute(
                "SELECT 1 FROM pg_trigger WHERE tgname='products_stock_nonnegative' AND NOT tgisinternal"
            ).fetchone()
            function = setup.execute(
                "SELECT 1 FROM pg_proc WHERE proname='place_shop_order'"
            ).fetchone()
            guard = setup.execute(
                "SELECT 1 FROM pg_proc WHERE proname='reject_negative_stock'"
            ).fetchone()
            self.assertIsNotNone(trigger)
            self.assertIsNotNone(function)
            self.assertIsNotNone(guard)
        finally:
            setup.close()

        pid, original = product
        conn = psycopg.connect("dbname=tgdd_products", autocommit=False)
        try:
            conn.execute("UPDATE products SET stock = 1 WHERE source_product_id=%s", (pid,))
            orders_before = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
            items_before = conn.execute("SELECT count(*) FROM order_items").fetchone()[0]
            shipment = {
                "name": "Kiem thu don",
                "email": "order-check@form.local",
                "phone": "0900000099",
                "address": "Kho kiem thu",
                "deliver_on": datetime.date.today() + datetime.timedelta(days=2),
                "deliver_slot": "morning",
                "pay_method": "cod",
            }
            failed = agent.place_order(conn, {"id": user[0]}, shipment, pid, "", 2)
            self.assertFalse(failed["ok"])
            self.assertIn("Chỉ còn 1", failed["note"])
            self.assertEqual(
                conn.execute("SELECT stock FROM products WHERE source_product_id=%s", (pid,)).fetchone()[0],
                1,
            )
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], orders_before)
            self.assertEqual(conn.execute("SELECT count(*) FROM order_items").fetchone()[0], items_before)

            placed = agent.place_order(conn, {"id": user[0]}, shipment, pid, "", 1)
            self.assertTrue(placed["ok"])
            self.assertEqual(placed["qty"], 1)
            self.assertEqual(placed["stock_left"], 0)
            self.assertEqual(
                conn.execute("SELECT stock FROM products WHERE source_product_id=%s", (pid,)).fetchone()[0],
                0,
            )
            self.assertEqual(conn.execute("SELECT count(*) FROM orders").fetchone()[0], orders_before + 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM order_items").fetchone()[0], items_before + 1)
            row = conn.execute(
                """
                SELECT i.qty, o.total_vnd
                FROM order_items i
                JOIN orders o ON o.id = i.order_id
                WHERE o.id = %s
                """,
                (placed["order_id"],),
            ).fetchone()
            self.assertEqual(row[0], 1)
            self.assertEqual(row[1], placed["total"])

            conn.execute("SAVEPOINT stock_guard")
            with self.assertRaises(psycopg.Error):
                conn.execute("UPDATE products SET stock = -1 WHERE source_product_id=%s", (pid,))
            conn.execute("ROLLBACK TO SAVEPOINT stock_guard")
            self.assertEqual(
                conn.execute("SELECT stock FROM products WHERE source_product_id=%s", (pid,)).fetchone()[0],
                0,
            )
        finally:
            conn.rollback()
            conn.close()

        check = psycopg.connect("dbname=tgdd_products", autocommit=True)
        try:
            restored = check.execute(
                "SELECT stock FROM products WHERE source_product_id=%s",
                (pid,),
            ).fetchone()[0]
            self.assertEqual(restored, original)
            self.assertIsNone(
                check.execute(
                    "SELECT 1 FROM orders WHERE ship_email=%s",
                    ("order-check@form.local",),
                ).fetchone()
            )
        finally:
            check.close()


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

    def _choice(self, **kwargs):
        choice = {
            "tool": "store_summary",
            "period": "",
            "category": "",
            "inventory_mode": "",
            "query": "",
            "order_mode": "",
            "order_id": None,
        }
        choice.update(kwargs)
        return choice

    def test_explicit_admin_sentence_stays_on_the_offline_route(self):
        tool, args = admin_agent.apply_admin_guards(
            "laptop bán chạy 7 ngày",
            [],
            self._choice(tool="store_summary"),
        )
        self.assertEqual(tool, "sales_report")
        self.assertEqual(args["period"], "7d")
        self.assertEqual(args["category"], "laptop")

    def test_category_follow_up_keeps_the_earlier_period(self):
        history = [
            ("user", "Điện thoại bán chạy 7 ngày"),
            ("bot", "Bán chạy 7 ngày qua, Điện thoại: 2 đơn."),
        ]
        tool, args = admin_agent.apply_admin_guards(
            "Thế còn laptop",
            history,
            self._choice(tool="sales_report", period="all", category="laptop"),
        )
        self.assertEqual(tool, "sales_report")
        self.assertEqual(args["category"], "laptop")
        self.assertEqual(args["period"], "7d")

    def test_order_follow_up_uses_the_order_just_shown(self):
        history = [("bot", "Đơn #41 · Đã đặt\nĐơn #40 · Hoàn tất")]
        tool, args = admin_agent.apply_admin_guards(
            "Đơn đó của ai",
            history,
            self._choice(tool="order_report", order_mode="status"),
        )
        self.assertEqual(tool, "order_report")
        self.assertEqual(args["mode"], "one")
        self.assertEqual(args["order_id"], 41)

    def test_stock_follow_up_reuses_the_product_just_named(self):
        history = [("bot", "• MacBook Air: 2 máy, 10.000.000₫")]
        tool, args = admin_agent.apply_admin_guards(
            "Máy đó còn bao nhiêu",
            history,
            self._choice(tool="inventory_report", inventory_mode="lookup", query=""),
        )
        self.assertEqual(tool, "inventory_report")
        self.assertEqual(args["mode"], "lookup")
        self.assertEqual(args["query"], "MacBook Air")

    def test_a_write_request_selects_no_report(self):
        tool, args = admin_agent.apply_admin_guards(
            "xóa hết đơn đi",
            [],
            self._choice(tool="order_report", order_mode="recent"),
        )
        self.assertEqual((tool, args), ("none", {}))

    def test_graph_runs_one_report_then_explains(self):
        payloads = [
            {"content": json.dumps(self._choice(tool="store_summary"))},
            {"content": "Đang bán 12 sản phẩm. Doanh thu đơn chưa hủy 10.000.000₫."},
        ]

        def fake_complete(*args, **kwargs):
            return payloads.pop(0)

        summary = {
            "products": 12,
            "categories": [{"category": "Điện thoại", "count": 12}],
            "orders": [{"status": "Đã đặt", "count": 1}],
            "revenue_excluding_cancelled": "10.000.000₫",
            "users": 2,
            "reviews": 0,
            "rating_average": None,
            "reviews_pending": 0,
            "support_requests": 0,
            "out_of_stock": 0,
            "low_stock": 0,
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("agent.model._complete", fake_complete):
                with patch("admin_agent.answer._run_tool", return_value=summary) as tool:
                    spoken = admin_agent.run_admin_graph(object(), "tổng quan cửa hàng")
        self.assertEqual(tool.call_count, 1)
        self.assertEqual(tool.call_args.args[1], "store_summary")
        self.assertEqual(spoken["tool"], "store_summary")
        self.assertEqual(spoken["text_from"], "model")
        self.assertIn("12", spoken["text"])
        self.assertIn("10.000.000₫", spoken["text"])

    def test_graph_overrides_a_wrong_tool_and_drops_loose_prose(self):
        payloads = [
            {"content": json.dumps(self._choice(tool="store_summary"))},
            {"content": "Ổn."},
        ]

        def fake_complete(*args, **kwargs):
            return payloads.pop(0)

        sales = {
            "period": "7 ngày qua",
            "category": "Laptop",
            "orders": 1,
            "units": 2,
            "revenue": "10.000.000₫",
            "best_sellers": [{"name": "MacBook Air", "qty": 2, "revenue": "10.000.000₫"}],
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("agent.model._complete", fake_complete):
                with patch("admin_agent.answer._run_tool", return_value=sales) as tool:
                    spoken = admin_agent.run_admin_graph(object(), "laptop bán chạy 7 ngày")
        self.assertEqual(tool.call_count, 1)
        self.assertEqual(tool.call_args.args[1], "sales_report")
        self.assertEqual(tool.call_args.args[2]["period"], "7d")
        self.assertEqual(tool.call_args.args[2]["category"], "laptop")
        self.assertEqual(spoken["text_from"], "tool_note")
        self.assertIn("MacBook Air", spoken["text"])
        self.assertIn("7 ngày qua", spoken["text"])

    def test_graph_refuses_a_write_without_calling_a_tool(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("agent.model._complete") as complete:
                with patch("admin_agent.answer._run_tool") as tool:
                    spoken = admin_agent.run_admin_graph(object(), "xóa hết đơn đi")
        self.assertEqual(complete.call_count, 0)
        self.assertEqual(tool.call_count, 0)
        self.assertEqual(spoken["tool"], "none")
        self.assertIn("không xóa", spoken["text"])

    def test_missing_key_still_answers_from_the_offline_router(self):
        conn = psycopg.connect("dbname=tgdd_products", autocommit=True)
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                text, note = admin_agent.answer_admin(conn, "đơn mới nhất")
        finally:
            conn.close()
        self.assertIn("số liệu trong máy", note)
        self.assertTrue("Đơn #" in text or "Chưa có đơn" in text)

    def test_admin_thread_keeps_earlier_turns(self):
        import server

        page = server.render_admin_assistant(
            [("user", "đơn mới nhất"), ("bot", "Đơn #3 · Đã đặt")],
            "",
        )
        self.assertLess(page.find("đơn mới nhất"), page.find("Đơn #3"))
        self.assertIn("Cuộc mới", page)
        self.assertIn('name="action" value="clear"', page)
        self.assertEqual(server.admin_chat_token({"token": "abc"}), "admin:abc")
        self.assertEqual(server.admin_chat_token({}), "")


class StorefrontTests(unittest.TestCase):
    def test_chat_panel_names_octopus_store_and_has_two_animations(self):
        import server

        page = server.layout("Octopus Store", "<main id=\"content\"></main>", 0, home=True)
        self.assertIn(">Octopus Store</span>", page)
        self.assertIn(">Octopus Store</h2>", page)
        self.assertIn('id="octopus-mascot"', page)
        self.assertIn('data-state="idle"', page)
        self.assertIn("<agent-robot-avatar", page)
        self.assertIn("agent-robot-avatar.js?v=105", page)
        self.assertNotIn("assistant-robot.jpg", page)
        self.assertIn("Trợ lý AI", page)
        self.assertIn('class="assistant-caption"', page)
        self.assertNotIn("Trợ lý cửa hàng", page)
        css = (server.ROOT / "frontend" / "store.css").read_text()
        self.assertIn("think-glow", css)
        self.assertIn('[data-state="idle"]', css)
        self.assertIn('[data-state="busy"]', css)
        self.assertNotEqual(
            css.split('[data-state="idle"]')[1].split("@keyframes")[0],
            css.split('[data-state="busy"]')[1].split("@keyframes")[0],
        )
        script = (server.ROOT / "frontend" / "store.js").read_text()
        self.assertIn('setMascot("busy")', script)
        self.assertIn('setMascot("idle")', script)
        self.assertIn("startWaiting", script)
        self.assertIn("store.css?v=105", page)
        self.assertIn(".assistant-pop:has(.chat-compare.cols-3)", css)
        self.assertIn("min(760px, calc(100vw - 32px))", css)
        self.assertIn("store.js?v=105", page)
        self.assertIn('id="assistant-status"', page)
        self.assertIn("think-dots", script)
        self.assertIn("Đang nghĩ…", script)
        self.assertIn("think-bounce", css)
        self.assertIn('class="online-dot"', page)
        self.assertIn("Mở trợ lý AI, đang trực tuyến", page)
        self.assertIn('class="qc-link qc-zalo"', page)
        self.assertIn(">Zalo</span>", page)
        self.assertIn(">Facebook</span>", page)
        self.assertIn(">Gọi ngay</span>", page)
        self.assertIn(">Email</span>", page)
        self.assertIn('id="compare-dock"', page)
        self.assertIn('class="bag-icon"', page)
        self.assertIn('aria-label="Túi hàng, 0 sản phẩm"', page)
        self.assertNotIn(">Túi</a>", page)
        rail = server.line_rail_markup(["<div class=\"line-slide\">Một</div>", "<div class=\"line-slide\">Hai</div>"])
        self.assertIn('id="line-rail" data-loop data-auto', rail)
        self.assertIn('data-loop-for="line-rail"', rail)
        for key in ("phone", "laptop", "tablet", "headphones", "smartwatch"):
            count = len(server.CATEGORY_BANNERS[key])
            self.assertGreaterEqual(count, 3)
            self.assertLessEqual(count, 4)
        self.assertIn("is-clone", script)
        self.assertIn("data-loop-for", script)
        self.assertIn('hasAttribute("data-auto")', script)
        self.assertIn("AUTO_MS", script)
        self.assertIn("octopus-compare", script)
        self.assertIn("Chỉ so sánh được máy cùng nhóm", script)
        kept, category, mixed = server.pick_compare([(1, "phone"), (2, "phone"), (3, "laptop"), (4, "phone"), (5, "phone"), (6, "phone")])
        self.assertEqual(kept, [1, 2, 4, 5])
        self.assertEqual(category, "phone")
        self.assertTrue(mixed)
        table = server.compare_markup(
            [
                {"id": 1, "category": "phone", "title": "Máy A", "price_label": "1₫", "image": "", "specs": [("", "RAM", "8 GB")]},
                {"id": 2, "category": "phone", "title": "Máy B", "price_label": "2₫", "image": "", "specs": [("", "RAM", "12 GB"), ("Màn hình", "Tấm nền", "OLED")]},
            ],
            "Điện thoại",
        )
        self.assertIn("Máy A", table)
        self.assertIn("Máy B", table)
        self.assertIn("8 GB", table)
        self.assertIn("OLED", table)
        self.assertIn("—", table)
        self.assertIn(">So sánh điện thoại</h1>", table)
        self.assertEqual(table.count("data-compare-id="), 2)
        left = {
            "product_id": 11, "name": "iPhone 16", "price": 24990000, "stock": 181,
            "image_url": "", "color_name": "Trắng",
            "specs": [{"name": "RAM", "value": "8 GB"}, {"name": "Chip", "value": "A18"}],
        }
        right = {
            "product_id": 12, "name": "iPhone 16 Plus", "price": 25490000, "stock": 229,
            "image_url": "", "color_name": "",
            "specs": [{"name": "RAM", "value": "8 GB"}, {"name": "Chip", "value": "A18"}, {"name": "Pin", "value": "4674 mAh"}],
        }
        third = {
            "product_id": 13, "name": "iPhone 16e", "price": 16990000, "stock": 270,
            "image_url": "", "color_name": "",
            "specs": [{"name": "RAM", "value": "8 GB"}, {"name": "Chip", "value": "A18"}],
        }
        compared = server.assistant_advice_markup({
            "text": "Hai máy khác nhau ở giá.",
            "tool": "compare_products",
            "products": [left, right],
        })
        self.assertIn("chat-compare", compared)
        self.assertIn("<table", compared)
        self.assertIn("iPhone 16", compared)
        self.assertIn("iPhone 16 Plus", compared)
        self.assertIn("24.990.000₫", compared)
        self.assertIn("Còn 181", compared)
        self.assertIn("4674 mAh", compared)
        self.assertIn("—", compared)
        self.assertIn('class="is-diff"', compared)
        self.assertIn("Đặt giúp tôi", compared)
        self.assertIn('href="/p/11"', compared)
        self.assertNotIn("advice-card", compared)
        self.assertIn("Hai máy khác nhau ở giá.", compared)
        ram_row = compared.split(">RAM</th>", 1)[1].split("</tr>", 1)[0]
        self.assertNotIn("is-diff", ram_row)
        price_row = compared.split(">Giá</th>", 1)[1].split("</tr>", 1)[0]
        self.assertEqual(price_row.count("is-diff"), 2)
        many = server.chat_compare_markup([left, right, third])
        self.assertIn("cols-3", many)
        self.assertEqual(many.count("chat-compare-product"), 3)
        self.assertIn("16.990.000₫", many)
        pin_row = many.split(">Pin</th>", 1)[1].split("</tr>", 1)[0]
        self.assertEqual(pin_row.count("is-diff"), 1)
        searched = server.assistant_advice_markup({
            "text": "Hai máy trong tầm giá.",
            "tool": "search_products",
            "products": [left, right],
        })
        self.assertIn("advice-card", searched)
        self.assertNotIn("chat-compare", searched)
        self.assertIn('href="/">Trang chủ</a>', page)
        self.assertIn('href="/gioi-thieu">Giới thiệu</a>', page)
        self.assertIn('href="/lien-he">Liên hệ</a>', page)
        home = server.layout("Octopus Store", "<main></main>", 0, current="home", home=True)
        self.assertIn('href="/" aria-current="page">Trang chủ</a>', home)
        about = server.render_about(0)
        self.assertIn('class="about-hero"', about)
        self.assertIn("<h1>Octopus Store</h1>", about)
        self.assertIn("Giá niêm yết tham chiếu tại Hà Nội.", about)
        self.assertIn('href="/c/phone"', about)
        self.assertIn('href="/c/laptop"', about)
        self.assertIn('href="/lien-he"', about)
        self.assertIn("Trợ lý AI", about)
        self.assertIn('href="/gioi-thieu" aria-current="page">Giới thiệu</a>', about)
        self.assertNotIn("reason-band", about)
        self.assertIn("about-feature", about)
        self.assertIn("iPhone Duo", about)
        self.assertIn("about-pick", about)
        self.assertIn("Mở ra một màn hình.", about)
        footer_rule = css.split(".footer {", 1)[1].split("}", 1)[0]
        self.assertIn("text-align: center", footer_rule)
        contact = server.render_contact(None)
        self.assertIn('class="contact-hero"', contact)
        self.assertIn('class="contact-grid"', contact)
        self.assertIn("Gửi yêu cầu", contact)
        self.assertIn('action="/lien-he"', contact)
        self.assertIn('name="body"', contact)
        self.assertIn("Giá niêm yết tham chiếu tại Hà Nội.", contact)
        self.assertIn('href="/lien-he" aria-current="page"', contact)
        self.assertNotIn("reason-band", contact)
        self.assertNotIn("0879", contact)
        self.assertNotIn("facebook.com", contact)
        self.assertNotIn("zalo.me", contact)
        self.assertNotIn("24 giờ", contact)
        filled = server.render_contact(
            None,
            {"name": "An", "email": "a@b.co", "phone": "", "body": "xin chào shop"},
            error="Email chưa đúng.",
        )
        self.assertIn("Email chưa đúng.", filled)
        self.assertIn('value="An"', filled)
        self.assertIn("data-reason-rail", script)
        self.assertIn("reason-dialog", script)
        self.assertIn(".reason-card", css)
        self.assertIn("Liên hệ nhanh", page)
        reasons = server.store_reasons()
        self.assertIn("reason-band", reasons)
        self.assertIn("reason-dialog", reasons)
        self.assertIn("Giao trên cả nước.", reasons)
        self.assertIn("Đọc đúng điều khoản hãng.", reasons)
        self.assertIn("Giá niêm yết phải chăng.", reasons)
        self.assertIn("Mua có trợ lý đi cùng.", reasons)
        self.assertIn("Thanh toán gọn lúc chốt.", reasons)
        self.assertIn('src="/frontend/reasons/warranty.png"', reasons)
        self.assertIn('src="/frontend/reasons/ship.png"', reasons)
        self.assertIn('src="/frontend/reasons/price.png"', reasons)
        self.assertIn('src="/frontend/reasons/assistant.png"', reasons)
        self.assertIn('src="/frontend/reasons/pay.png"', reasons)
        self.assertIn("robot-fallback", page)
        self.assertIn("clamp(44px, 4vw, 72px)", css)
        self.assertIn("reviveRobots", script)
        self.assertIn('viewBox="0 0 16 16"', reasons)
        self.assertNotIn("apple.com", reasons)
        lowered = reasons.lower()
        self.assertNotIn("trade in", lowered)
        self.assertNotIn("lãi suất", lowered)
        self.assertNotIn("miễn phí", lowered)
        self.assertNotIn("chuyên gia", lowered)
        self.assertNotIn("15:00", reasons)
        self.assertNotIn("reason-band", page)
        self.assertIn('src="/frontend/logo.png"', page)
        self.assertIn("translateY(-6px)", css)
        self.assertIn("width: 54px; height: 54px", css)
        self.assertIn("width: 2.35em", css)
        self.assertIn(".hero-brand::after", css)
        cat = server.layout("Điện thoại", "<main></main>", 0, current="phone", show_reasons=True)
        self.assertIn("reason-band", cat)
        self.assertLess(cat.index("reason-band"), cat.index('class="footer"'))
        card = server.line_banner(
            {
                "id": 370977,
                "title": "iPhone 18 Pro 256GB",
                "line": "Pro hơn hẳn.",
                "image": "/cutout/x.png",
                "alt": "iPhone 18 Pro",
            },
            "iPhone",
        )
        self.assertIn('class="line-banner"', card)
        self.assertIn("iPhone 18 Pro 256GB", card)
        self.assertIn("Tìm hiểu thêm ›", card)
        self.assertIn('href="/p/370977"', card)
        self.assertIn("© 2026 Octopus store. All rights reserved.", page)
        self.assertNotIn("thegioididong.com", page)
        self.assertNotIn("Quản trị local", page)
        self.assertIn('rel="icon" href="/frontend/favicon.svg"', page)
        self.assertIn("M32 4c-11", (server.ROOT / "frontend" / "favicon.svg").read_text())
        hero = server.banner(
            {
                "id": 370987,
                "title": "Điện thoại iPhone Duo",
                "headline": "iPhone Duo",
                "line": "Mở ra một màn hình.",
                "note": "Từ 64.990.000₫. Đang có tại cửa hàng.",
                "image": "/cutout/918b591ddb94.png",
                "alt": "Điện thoại iPhone Duo",
                "price": 64990000,
                "category": "phone",
            },
            primary=True,
            tone="ink",
            brand="Octopus Store",
        )
        self.assertIn('class="hero-logo" src="/frontend/logo.png"', hero)
        hero_rule = css.split(".banner.stage-wide .hero-brand {", 1)[1].split("}", 1)[0]
        self.assertIn("flex-direction: column", hero_rule)
        self.assertIn('class="hero-brand">', hero)
        self.assertIn("Octopus Store</p>", hero)
        self.assertIn("home-hero", hero)
        self.assertIn(">iPhone Duo</p>", hero)
        self.assertIn("Mở ra một màn hình.", hero)
        plain = server.banner(
            {
                "id": 1,
                "title": "iPhone 18 Pro Max",
                "headline": "iPhone 18 Pro Max",
                "line": "Cùng Pro. Màn hình lớn hơn.",
                "note": "",
                "image": "/cutout/x.png",
                "alt": "iPhone 18 Pro Max",
                "price": 41990000,
                "category": "phone",
            },
            tone="white",
        )
        self.assertNotIn("hero-brand", plain)
        self.assertNotIn("Octopus Store", plain)
        spoken = {
            "text": (
                'Shop đang có vài hãng điện thoại.<div class="brand-chips">'
                '<button type="button" class="brand-chip" data-q="cho mình xem điện thoại Samsung">Samsung</button>'
                "</div>"
            ),
            "products": [],
            "product_reasons": {},
        }
        html = server.assistant_advice_markup(spoken)
        self.assertIn('class="brand-chip"', html)
        self.assertIn('data-q="cho mình xem điện thoại Samsung"', html)
        self.assertIn(">Samsung</button>", html)
        self.assertIn("Shop đang có vài hãng điện thoại.", html)
        self.assertNotIn("&lt;button", html)
        poisoned = server.assistant_advice_markup({
            "text": 'Xin chào bạn nhé.<div class="brand-chips"><script>alert(1)</script></div>',
            "products": [],
            "product_reasons": {},
        })
        self.assertNotIn("<script>", poisoned)
        self.assertIn("&lt;script&gt;", poisoned)

    def test_warranty_reply_quotes_the_passage_and_the_invoice_stays_in_chat(self):
        import server

        quoted = server.warranty_markup({
            "tool": "search_documents",
            "text": "Chỉ được kể các đoạn dưới đây. Đừng bịa.",
            "passages": [{
                "brand": "Apple",
                "title": "Bảo hành iPhone",
                "source_url": "https://www.apple.com/legal/warranty/example",
                "text": "Đoạn điều khoản được truy xuất nguyên văn.",
            }],
        })
        self.assertIn('class="citation"', quoted)
        self.assertIn("Apple · Bảo hành iPhone", quoted)
        self.assertIn("Đoạn điều khoản được truy xuất nguyên văn.", quoted)
        self.assertIn('href="https://www.apple.com/legal/warranty/example"', quoted)
        self.assertNotIn("Chỉ được kể các đoạn", quoted)
        blocked = server.warranty_markup({
            "tool": "search_documents",
            "text": "note",
            "passages": [{
                "brand": "Apple",
                "title": "Điều khoản",
                "source_url": "javascript:alert(1)",
                "text": "Đoạn hợp lệ.",
            }],
        })
        self.assertNotIn("javascript:", blocked)
        self.assertIn("Đoạn hợp lệ.", blocked)
        self.assertNotIn("<a ", blocked)
        empty = server.warranty_markup({
            "tool": "search_documents",
            "text": "Không có điều khoản của hãng này trong kho. Đừng lấy điều khoản hãng khác.",
            "passages": [],
        })
        self.assertIn("Đừng lấy điều khoản hãng khác", empty)
        self.assertNotIn("citation", empty)
        routed = server.assistant_advice_markup({
            "tool": "search_documents",
            "text": "Chỉ được kể các đoạn dưới đây.",
            "passages": [{
                "brand": "Apple",
                "title": "Điều khoản",
                "source_url": "https://www.apple.com/legal/warranty/example",
                "text": "Đoạn được trích.",
            }],
            "products": [],
        })
        self.assertIn("Đoạn được trích.", routed)
        self.assertNotIn("Chỉ được kể các đoạn", routed)
        page = server.assistant_receipt({
            "order_id": 42,
            "name": "điện thoại iphone 16 128gb",
            "color_name": "Trắng",
            "qty": 1,
            "total": 24990000,
            "ship_name": "Bảo",
            "ship_phone": "0900000000",
            "ship_address": "1 phố Demo, Hà Nội",
            "deliver_on": "14.10.2026",
            "deliver_slot": "morning",
            "pay_method": "cod",
        }, "Chưa gửi hoá đơn qua email. Chưa trừ tiền thật.")
        self.assertIn('class="chat-invoice"', page)
        self.assertIn("Hoá đơn đơn hàng #42", page)
        self.assertIn("24.990.000₫", page)
        self.assertIn("Chưa trừ tiền thật.", page)
        self.assertIn("Thanh toán khi nhận hàng", page)
        self.assertIn("Bảo", page)
        self.assertNotIn("vietqr", page.casefold())
        self.assertNotIn("img.vietqr.io", page)
        css = (server.ROOT / "frontend" / "store.css").read_text()
        self.assertIn(".citation blockquote", css)
        self.assertIn("white-space: pre-wrap", css)
        self.assertIn(".chat-invoice", css)
        self.assertIn(".invoice-total", css)
        script = (server.ROOT / "frontend" / "store.js").read_text()
        self.assertIn("chat-invoice", script)
        self.assertIn("citation", script)


if __name__ == "__main__":
    unittest.main()
