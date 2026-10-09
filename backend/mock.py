"""Hội thoại hồi quy của trợ lý khách.

Chạy ngoại tuyến với provider giả và catalog thật:
    .venv/bin/python backend/mock.py

Chạy lại cùng các câu với provider thật (chỉ đọc catalog):
    .venv/bin/python backend/mock.py --live
    .venv/bin/python backend/mock.py --live bo_hang_tung_thich_va_uu_tien_camera

Chạy chuỗi nhiều lượt qua HTTP /tro-ly với tài khoản thử tự dọn dẹp:
    .venv/bin/python backend/mock.py --http free_fire_15_trieu_sang_laptop_ai_15_trieu
"""

import json
import http.cookiejar
import os
import re
import socket
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch

import psycopg

from agent.graph import run_shop_graph
from agent.understand import _FIELDS


def requirements(**changes):
    """Một phản hồi đầy đủ theo schema của bước hiểu ý định."""
    value = {
        "category": "phone", "query": "", "color": "",
        "price_min": None, "price_max": None, "price_max_exclusive": False,
        "price_target": None, "budget_mode": "none", "brand": "",
        "excluded_brands": [], "use": "", "priorities": [],
        "ram_gb": None, "min_ram": None, "storage_gb": None, "screen": None,
        "line": "", "variant": "", "chip": "", "family": "",
        "cheapest": False,
    }
    value.update(changes)
    assert set(value) == set(_FIELDS)
    return value


def provider_reply(action, slots, question_to_ask="", latest_excluded=None,
                   latest_use="unchanged", latest_priorities=None, latest_budget=None):
    return {
        "action": action, "question_to_ask": question_to_ask,
        "compare_left": "", "compare_right": "", "qty": None,
        "doc_type": "other", "requirements": slots,
        "latest_excluded_brands": latest_excluded or [],
        "latest_budget": latest_budget or {"mode": "unchanged", "price_min": None,
                                            "price_max": None, "price_target": None},
        "latest_use": latest_use, "latest_priorities": latest_priorities or [],
    }


def budget(mode="unchanged", *, low=None, high=None, target=None):
    return {"mode": mode, "price_min": low, "price_max": high, "price_target": target}


# history is the conversation before the final user message. In particular,
# the earlier assistant question is kept so the follow-up is tested in context.
MOCK = [
    {
        "name": "lien_quan_17_trieu_provider_mo_form_sai",
        "history": [
            ("user", "t muốn mua điện thoại để chơi liên quân"),
            ("bot", "Bạn có ngân sách khoảng bao nhiêu cho chiếc điện thoại này?"),
        ],
        "user": "khoảng 17 triệu",
        # Intentionally reproduces the bad response seen in production: wrong
        # action and contradictory target/max slots. Code must normalize it.
        "reply": provider_reply("prepare_checkout", requirements(
            use="gaming", price_target=17_000_000, price_max=17_000_000,
            price_max_exclusive=True, budget_mode="target",
        )),
        "max_price": 17_000_000,
        "use": "gaming",
    },
    {
        "name": "danh_dien_tu_12_trieu",
        "history": [
            ("user", "tao muốn mua điện thoại về đánh điện tử"),
            ("bot", "Ngân sách của bạn cho điện thoại khoảng bao nhiêu?"),
        ],
        "user": "khoảng 12 triệu",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_target=12_000_000, budget_mode="target",
        )),
        "max_price": 12_000_000,
        "use": "gaming",
    },
    {
        "name": "loai_xiaomi_sau_khi_giam_gia",
        "history": [
            ("user", "tao muốn mua điện thoại để chơi game"),
            ("bot", "Ngân sách của bạn khoảng bao nhiêu?"),
            ("user", "khoảng 20 triệu"),
            ("bot", "Mình tìm được vài mẫu điện thoại chơi game."),
            ("user", "dưới 20 triệu thôi"),
            ("bot", "Đây là vài máy dưới 20 triệu."),
            ("user", "không thích xiaomi"),
        ],
        "user": "gì cũng được miễn không phải xiaomi",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_max=20_000_000, price_max_exclusive=True,
            budget_mode="max_exclusive", excluded_brands=["Xiaomi"],
        )),
        "max_price": 20_000_000,
        "exclusive": True,
        "excluded": ["Xiaomi"],
        "use": "gaming",
    },
    {
        "name": "khong_thich_xiaomi_ngay_sau_goi_y",
        "history": [
            ("user", "tao muốn mua điện thoại chơi game dưới 20 triệu"),
            ("bot", "Mình tìm được vài mẫu trong ngân sách."),
        ],
        "user": "không thích xiaomi",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_max=20_000_000, price_max_exclusive=True,
            budget_mode="max_exclusive", excluded_brands=["Xiaomi"],
        ), latest_excluded=["Xiaomi"]),
        "max_price": 20_000_000, "exclusive": True,
        "excluded": ["Xiaomi"], "use": "gaming",
    },
    {
        "name": "khong_thich_samsung",
        "history": [("user", "Mình tìm điện thoại chơi game khoảng 17 triệu."),
                    ("bot", "Đây là vài máy trong tầm giá.")],
        "user": "không thích Samsung",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_target=17_000_000, budget_mode="target",
            excluded_brands=["Samsung"],
        ), latest_excluded=["Samsung"]),
        "max_price": 17_000_000, "excluded": ["Samsung"], "use": "gaming",
    },
    {
        "name": "tru_apple_ra",
        "history": [("user", "Cho mình điện thoại tầm 17 triệu để chơi game."),
                    ("bot", "Mình tìm được vài sản phẩm.")],
        "user": "trừ Apple ra",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_target=17_000_000, budget_mode="target",
            excluded_brands=["Apple"],
        ), latest_excluded=["Apple"]),
        "max_price": 17_000_000, "excluded": ["Apple"], "use": "gaming",
    },
    {
        "name": "ngoai_oppo",
        "history": [("user", "Tìm điện thoại chơi game dưới 15 triệu."),
                    ("bot", "Có vài lựa chọn cho bạn.")],
        "user": "hãng nào cũng được ngoài Oppo",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_max=15_000_000, price_max_exclusive=True,
            budget_mode="max_exclusive", excluded_brands=["OPPO"],
        ), latest_excluded=["OPPO"]),
        "max_price": 15_000_000, "exclusive": True,
        "excluded": ["OPPO"], "use": "gaming",
    },
    {
        "name": "doi_ngan_sach_tu_20_xuong_15",
        "history": [
            ("user", "Mình cần điện thoại chơi game, khoảng 20 triệu."),
            ("bot", "Mình tìm được một số mẫu phù hợp."),
        ],
        "user": "thôi, dưới 15 triệu thôi",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_max=15_000_000, price_max_exclusive=True,
            budget_mode="max_exclusive",
        )),
        "max_price": 15_000_000,
        "exclusive": True,
        "use": "gaming",
    },
    {
        "name": "bo_hang_tung_thich_va_uu_tien_camera",
        "history": [
            ("user", "Mình thích Xiaomi, tìm điện thoại chơi game tầm 17 triệu."),
            ("bot", "Mình tìm được vài mẫu Xiaomi."),
        ],
        "user": "thôi không lấy Xiaomi, giờ ưu tiên camera",
        "reply": provider_reply("search_products", requirements(
            price_target=17_000_000, budget_mode="target",
            brand="Xiaomi", use="gaming",
        ), latest_excluded=["Xiaomi"], latest_use="other",
            latest_priorities=["camera"]),
        "max_price": 17_000_000,
        "excluded": ["Xiaomi"],
        "priority": "camera",
        "use": "",
    },
    {
        "name": "bon_dien_thoai_re_nhat",
        "history": [],
        "user": "cho mình xem 4 điện thoại rẻ nhất đang bán",
        "reply": provider_reply("search_products", requirements(cheapest=True)),
        "expected_count": 4,
    },
    {
        "name": "het_hang_trong_ngan_sach",
        "history": [("user", "Cho mình xem điện thoại chơi game")],
        "user": "ngân sách chỉ 100 nghìn thôi",
        "reply": provider_reply("search_products", requirements(
            use="gaming", price_max=100_000, budget_mode="max_inclusive",
        )),
        "max_price": 100_000,
        "empty": True,
        "use": "gaming",
    },
    {
        "name": "muon_dat_bang_tin_nhan_phai_xem_may_truoc",
        "history": [
            ("user", "Mình muốn điện thoại chơi game dưới 17 triệu."),
            ("bot", "Mình tìm được vài máy, bạn xem các thẻ sản phẩm nhé."),
        ],
        "user": "đặt giúp mình một máy nhé",
        "reply": provider_reply("prepare_checkout", requirements(
            use="gaming", price_max=17_000_000,
            budget_mode="max_exclusive", price_max_exclusive=True,
        )),
        "max_price": 17_000_000,
        "exclusive": True,
        "use": "gaming",
    },
]


ASK_FIRST = {
    "history": [],
    "user": "t muốn mua điện thoại về đánh điện tử",
    # The provider sometimes searches here; the graph must request a budget.
    "reply": provider_reply("search_products", requirements(use="gaming")),
}

ASK_FREE_FIRE = {
    "history": [
        ("user", "Tầm 25 triệu, cần MacBook để code AI, ưu tiên RAM và pin."),
        ("bot", "Mình tìm được vài laptop phù hợp."),
    ],
    "user": "t muốn mua điện thoại cho thằng cháu t chơi free fire",
    # Query can be a game description. It must not bypass the budget question.
    "reply": provider_reply("search_products", requirements(
        query="điện thoại chơi free fire", use="gaming",
    )),
}


# Mỗi kịch bản được phát lại từ đầu. Câu trả lời thật của lượt trước được
# đưa vào history của lượt sau, giống endpoint /assistant của server.
CONVERSATIONS = [
    {
        "name": "free_fire_15_trieu_sang_laptop_ai_15_trieu",
        "turns": [
            {
                "user": "t muốn mua điện thoại cho thằng cháu t chơi free fire",
                "reply": provider_reply("ask", requirements(use="gaming"), "Bạn có ngân sách khoảng bao nhiêu?", latest_use="gaming"),
                "tool": "ask", "category": "phone", "use": "gaming",
            },
            {
                "user": "khoảng 15 triệu",
                "reply": provider_reply("search_products", requirements(use="gaming", price_target=15_000_000, budget_mode="target"),
                                        latest_budget=budget("target", target=15_000_000)),
                "tool": "search_products", "category": "phone", "use": "gaming", "max_price": 15_000_000,
            },
            {
                "user": "với 15 triệu có mua đc laptop nào để học AI không",
                # The full-state summary and action can both be wrong. The
                # current-message budget must repair the summary and search.
                "reply": provider_reply("ask", requirements(category="laptop", use="study"),
                                        "Bạn dự định chi khoảng bao nhiêu?", latest_use="study",
                                        latest_budget=budget("target", target=15_000_000)),
                "tool": "search_products", "category": "laptop", "use": "study", "max_price": 15_000_000,
            },
        ],
    },
    {
        "name": "doi_sang_laptop_khong_noi_gia_roi_bo_sung_gia",
        "turns": [
            {
                "user": "Mình cần điện thoại chơi game tầm 15 triệu",
                "reply": provider_reply("search_products", requirements(use="gaming", price_target=15_000_000, budget_mode="target"),
                                        latest_use="gaming", latest_budget=budget("target", target=15_000_000)),
                "tool": "search_products", "category": "phone", "use": "gaming", "max_price": 15_000_000,
            },
            {
                "user": "thế laptop để học AI thì sao",
                "reply": provider_reply("ask", requirements(category="laptop", use="study"),
                                        "Bạn dự định chi khoảng bao nhiêu cho laptop?", latest_use="study"),
                "tool": "ask", "category": "laptop", "use": "study",
            },
            {
                "user": "15 triệu nhé",
                "reply": provider_reply("search_products", requirements(category="laptop", use="study", price_target=15_000_000, budget_mode="target"),
                                        latest_budget=budget("target", target=15_000_000)),
                "tool": "search_products", "category": "laptop", "use": "study", "max_price": 15_000_000,
            },
        ],
    },
    {
        "name": "giam_gia_roi_doi_uu_tien_camera",
        "turns": [
            {
                "user": "Mình tìm điện thoại chơi game khoảng 20 triệu",
                "reply": provider_reply("search_products", requirements(use="gaming", price_target=20_000_000, budget_mode="target"),
                                        latest_use="gaming", latest_budget=budget("target", target=20_000_000)),
                "tool": "search_products", "category": "phone", "use": "gaming", "max_price": 20_000_000,
            },
            {
                "user": "dưới 15 triệu thôi",
                "reply": provider_reply("search_products", requirements(use="gaming", price_target=20_000_000, budget_mode="target"),
                                        latest_budget=budget("max_exclusive", high=15_000_000)),
                "tool": "search_products", "category": "phone", "use": "gaming", "max_price": 15_000_000, "exclusive": True,
            },
            {
                "user": "giờ ưu tiên camera hơn chơi game",
                "reply": provider_reply("search_products", requirements(price_max=15_000_000, price_max_exclusive=True,
                                                                       budget_mode="max_exclusive", use="gaming"),
                                        latest_use="other", latest_priorities=["camera"]),
                "tool": "search_products", "category": "phone", "use": "", "max_price": 15_000_000,
                "exclusive": True, "priority": "camera",
            },
        ],
    },
    {
        "name": "laptop_ai_tang_gia_tu_15_len_20",
        "turns": [
            {
                "user": "Laptop học AI với 15 triệu có máy nào?",
                "reply": provider_reply("search_products", requirements(category="laptop", use="study", price_target=15_000_000, budget_mode="target"),
                                        latest_use="study", latest_budget=budget("target", target=15_000_000)),
                "tool": "search_products", "category": "laptop", "use": "study", "max_price": 15_000_000,
            },
            {
                "user": "nếu lên 20 triệu thì sao",
                "reply": provider_reply("search_products", requirements(category="laptop", use="study", price_target=15_000_000, budget_mode="target"),
                                        latest_budget=budget("target", target=20_000_000)),
                "tool": "search_products", "category": "laptop", "use": "study", "max_price": 20_000_000,
            },
        ],
    },
]


def check_conversation_turn(test, step, spoken):
    trace = spoken["trace"]
    slots = next(part["arguments"] for part in trace if part["kind"] == "slots")
    tool = next(part["tool"] for part in trace if part["kind"] == "intent")
    test.assertEqual(tool, step["tool"], step["user"])
    test.assertEqual(slots["category"], step["category"], step["user"])
    test.assertEqual(slots["use"], step["use"], step["user"])
    test.assertIsNone(spoken["checkout"], step["user"])
    if step.get("priority"):
        test.assertIn(step["priority"], slots["priorities"], step["user"])
    if step["tool"] == "ask":
        test.assertFalse(spoken["products"], step["user"])
        test.assertIn("bao nhiêu", spoken["text"].casefold(), step["user"])
        return
    test.assertEqual(next(part["name"] for part in trace if part["kind"] == "tool"), "search_products")
    ceiling = step["max_price"]
    test.assertIn(ceiling, (slots.get("price_target"), slots.get("price_max")), step["user"])
    for product in spoken["products"]:
        test.assertEqual(product["category"], step["category"], step["user"])
        if step.get("exclusive"):
            test.assertLess(product["price"], ceiling, step["user"])
        else:
            test.assertLessEqual(product["price"], ceiling, step["user"])
    if not spoken["products"]:
        test.assertIn("không", spoken["text"].casefold(), step["user"])


def check_result(test, case, spoken):
    trace = spoken["trace"]
    slots = next(step["arguments"] for step in trace if step["kind"] == "slots")
    tool = next(step for step in trace if step["kind"] == "tool")
    test.assertEqual(tool["name"], "search_products", case["name"])
    test.assertIsNone(spoken["checkout"], case["name"])
    test.assertNotIn("<form", spoken["text"].casefold(), case["name"])
    test.assertEqual(slots.get("category"), "phone", case["name"])
    if "use" in case:
        test.assertEqual(slots.get("use"), case["use"], case["name"])
    if case.get("priority"):
        test.assertIn(case["priority"], slots.get("priorities") or [], case["name"])
    if case.get("excluded"):
        test.assertEqual(
            [name.casefold() for name in slots.get("excluded_brands") or []],
            [name.casefold() for name in case["excluded"]], case["name"],
        )
        test.assertNotIn(slots.get("brand", "").casefold(),
                         [name.casefold() for name in case["excluded"]], case["name"])
    products = spoken["products"]
    reasons = spoken.get("product_reasons") or {}
    if case.get("empty"):
        test.assertFalse(products, case["name"])
        test.assertIn("không", spoken["text"].casefold(), case["name"])
    else:
        test.assertTrue(products, case["name"])
        if case.get("expected_count"):
            test.assertEqual(len(products), case["expected_count"], case["name"])
        test.assertEqual(set(reasons), {product["product_id"] for product in products}, case["name"])
        for product in products:
            test.assertGreater(len(reasons[product["product_id"]].strip()), 20, case["name"])
        test.assertEqual(len({reason.casefold() for reason in reasons.values()}), len(products), case["name"])
        from server import assistant_advice_markup, esc
        with patch("server.shown_image", return_value=""):
            markup = assistant_advice_markup(spoken)
        test.assertEqual(markup.count('class="advice-reason"'), len(products), case["name"])
        for reason in reasons.values():
            test.assertIn(esc(reason), markup, case["name"])
    for product in products:
        if case.get("max_price") is not None:
            if case.get("exclusive"):
                test.assertLess(product["price"], case["max_price"], case["name"])
            else:
                test.assertLessEqual(product["price"], case["max_price"], case["name"])
        blob = (product.get("brand", "") + " " + product["name"]).casefold()
        for excluded in case.get("excluded", []):
            test.assertNotIn(excluded.casefold(), blob, case["name"])


class ConversationMockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conn = psycopg.connect(os.environ.get("DATABASE_URL", "dbname=tgdd_products"), autocommit=True)
        except psycopg.Error as exc:
            raise unittest.SkipTest(f"Catalog chưa sẵn sàng: {exc}") from exc

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_first_turn_asks_for_budget_once(self):
        def fake_complete(*_args, **_options):
            return {"content": json.dumps(ASK_FIRST["reply"], ensure_ascii=False)}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}):
            with patch("agent.model._complete", side_effect=fake_complete):
                spoken = run_shop_graph(self.conn, {}, ASK_FIRST["user"])
        self.assertIn("bao nhiêu", spoken["text"].casefold())
        self.assertNotIn("chơi game hay", spoken["text"].casefold())
        self.assertFalse(spoken["products"])
        self.assertIsNone(spoken["checkout"])

    def test_new_phone_consultation_does_not_reuse_laptop_budget_or_search_game_name(self):
        def fake_complete(*_args, **_options):
            return {"content": json.dumps(ASK_FREE_FIRE["reply"], ensure_ascii=False)}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}):
            with patch("agent.model._complete", side_effect=fake_complete):
                spoken = run_shop_graph(self.conn, {}, ASK_FREE_FIRE["user"], ASK_FREE_FIRE["history"])
        self.assertIn("bao nhiêu", spoken["text"].casefold())
        self.assertFalse(spoken["products"])
        self.assertEqual(next(step["tool"] for step in spoken["trace"] if step["kind"] == "intent"), "ask")

    def test_natural_follow_ups_and_hard_limits(self):
        for case in MOCK:
            with self.subTest(case=case["name"]):
                def fake_complete(_base, _key, _model, _messages, **options):
                    schema = (options.get("response_format") or {}).get("json_schema") or {}
                    if schema.get("name") == "shop_turn":
                        return {"content": json.dumps(case["reply"], ensure_ascii=False)}
                    if schema.get("name") == "recommendation_explanation":
                        payload = json.loads(_messages[-1]["content"].split("\n", 1)[1])
                        products = payload["tool_result"]["products"]
                        reasons = {}
                        for product in products:
                            fact = (product.get("rear_camera") if case.get("priority") == "camera"
                                    else product.get("chip")) or product.get("battery") or product["name"]
                            reasons[str(product["product_id"])] = (
                                f"{product['name']} có {fact}, đây là thông số để cân nhắc theo nhu cầu của bạn."
                            )
                        return {"content": json.dumps({
                            "intro": "Mình đã tìm được các mẫu trong ngân sách của bạn.",
                            "reasons": reasons,
                        }, ensure_ascii=False)}
                    raise AssertionError("Unexpected provider response format")

                with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}):
                    with patch("agent.model._complete", side_effect=fake_complete):
                        spoken = run_shop_graph(self.conn, {}, case["user"], case["history"])
                check_result(self, case, spoken)

    def test_full_conversations_keep_each_turns_context(self):
        from server import assistant_advice_markup

        for scenario in CONVERSATIONS:
            history = []
            for step in scenario["turns"]:
                with self.subTest(scenario=scenario["name"], user=step["user"]):
                    def fake_complete(_base, _key, _model, messages, **options):
                        schema = (options.get("response_format") or {}).get("json_schema") or {}
                        if schema.get("name") == "shop_turn":
                            return {"content": json.dumps(step["reply"], ensure_ascii=False)}
                        if schema.get("name") == "recommendation_explanation":
                            payload = json.loads(messages[-1]["content"].split("\n", 1)[1])
                            products = payload["tool_result"]["products"]
                            return {"content": json.dumps({
                                "intro": "Mình đã kiểm tra các mẫu trong ngân sách của bạn.",
                                "reasons": {str(item["product_id"]):
                                            f"{item['name']} có thông số phù hợp để cân nhắc cho nhu cầu vừa nêu."
                                            for item in products},
                            }, ensure_ascii=False)}
                        raise AssertionError("Unexpected provider response format")

                    with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}):
                        with patch("agent.model._complete", side_effect=fake_complete):
                            spoken = run_shop_graph(self.conn, {}, step["user"], history)
                    check_conversation_turn(self, step, spoken)
                    with patch("server.shown_image", return_value=""):
                        bot_html = assistant_advice_markup(spoken)
                    history.extend((("user", step["user"]), ("bot", bot_html)))


class CardExplanationTests(unittest.TestCase):
    def test_every_returned_card_gets_its_own_explanation(self):
        from server import assistant_advice_markup

        for count in (1, 2, 4):
            with self.subTest(card_count=count):
                products = [
                    {
                        "product_id": 9000 + index,
                        "name": f"Điện thoại mẫu {index}",
                        "brand": f"Hãng {index}",
                        "price": 10_000_000 + index * 100_000,
                        "stock": 2,
                        "category": "phone",
                        "color_name": "",
                        "image_url": "",
                        "specs": [{"name": "Chip", "value": f"Chip {index}"},
                                  {"name": "RAM", "value": "12 GB"}],
                    }
                    for index in range(count)
                ]
                reasons = {
                    str(item["product_id"]): f"Chip {item['product_id'] - 9000} và RAM 12 GB là cơ sở để cân nhắc mẫu này cho nhu cầu chơi game."
                    for item in reversed(products)
                }

                def fake_complete(*_args, **options):
                    schema = options["response_format"]["json_schema"]["schema"]
                    self.assertEqual(set(schema["properties"]["reasons"]["required"]), set(reasons))
                    return {"content": json.dumps({"intro": "Các mẫu này ở trong ngân sách của bạn.",
                                                   "reasons": reasons}, ensure_ascii=False)}

                plan = provider_reply("search_products", requirements(
                    use="gaming", price_target=17_000_000, budget_mode="target",
                ))
                from agent.understand import _clean_requirements
                understood = {"action": plan["action"], "ask": "",
                              "resolved": _clean_requirements(plan["requirements"])}
                with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}):
                    with patch("agent.understand.understand_turn", return_value=understood):
                        with patch("agent.model._run_tool", return_value=({"products": products}, products, None)):
                            with patch("agent.model._complete", side_effect=fake_complete):
                                spoken = run_shop_graph(None, {}, "Tìm điện thoại chơi game tầm 17 triệu")
                self.assertEqual(set(spoken["product_reasons"]), {item["product_id"] for item in products})
                with patch("server.shown_image", return_value=""):
                    markup = assistant_advice_markup(spoken)
                self.assertEqual(markup.count('class="advice-reason"'), count)
                positions = [markup.index(reasons[str(item["product_id"])]) for item in products]
                self.assertEqual(positions, sorted(positions))

    def test_missing_provider_reason_uses_only_that_products_catalog_specs(self):
        from agent.graph import _recommendation_reply

        products = [
            {"product_id": 1, "reason": "", "specs": [{"name": "Chip", "value": "Chip Alpha"},
                                                        {"name": "RAM", "value": "8 GB"}]},
            {"product_id": 2, "reason": "", "specs": [{"name": "Chip", "value": "Chip Beta"},
                                                        {"name": "RAM", "value": "12 GB"}]},
        ]
        intro, reasons = _recommendation_reply(
            json.dumps({"intro": "Hai máy trong ngân sách.", "reasons": {"1": "Chip Alpha và RAM 8 GB đáp ứng nhu cầu chơi game của bạn."}}),
            products, {"use": "gaming"}, "",
        )
        self.assertEqual(intro, "Hai máy trong ngân sách.")
        self.assertIn("Chip Beta", reasons[2])
        self.assertNotIn("Chip Alpha", reasons[2])

    def test_products_still_render_when_explanation_connection_resets(self):
        from agent.understand import _clean_requirements
        from server import assistant_advice_markup

        product = {
            "product_id": 9011, "name": "Điện thoại mẫu thử", "brand": "Hãng thử",
            "price": 12_000_000, "stock": 2, "category": "phone",
            "color_name": "", "image_url": "", "reason": "",
            "specs": [{"name": "Chip", "value": "Chip Gamma"},
                      {"name": "RAM", "value": "12 GB"}],
        }
        understood = {
            "action": "search_products", "ask": "",
            "resolved": _clean_requirements(requirements(
                use="gaming", price_target=17_000_000, budget_mode="target",
            )),
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}):
            with patch("agent.understand.understand_turn", return_value=understood):
                with patch("agent.model._run_tool", return_value=({"products": [product]}, [product], None)):
                    with patch("agent.model._complete", side_effect=ConnectionResetError("provider reset")):
                        spoken = run_shop_graph(None, {}, "Tìm điện thoại chơi game tầm 17 triệu")
        self.assertEqual(len(spoken["products"]), 1)
        self.assertIn("Chip Gamma", spoken["product_reasons"][9011])
        self.assertEqual(spoken["text_from"], "tool_note")
        with patch("server.shown_image", return_value=""):
            markup = assistant_advice_markup(spoken)
        self.assertEqual(markup.count('class="advice-reason"'), 1)


class ProviderTransportTests(unittest.TestCase):
    def test_connection_reset_gets_one_retry(self):
        from agent.model import _complete

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}]}'

        with patch("agent.model.urllib.request.urlopen",
                   side_effect=[ConnectionResetError("provider reset"), Response()]) as opened:
            with patch("agent.model.time.sleep") as sleep:
                message = _complete("https://example.invalid/v1", "test-key", "test-model",
                                    [{"role": "user", "content": "hello"}])
        self.assertEqual(message["content"], "ok")
        self.assertEqual(opened.call_count, 2)
        sleep.assert_called_once_with(0.4)


def run_live(selected=None):
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.is_file():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Cần OPENAI_API_KEY để chạy --live")
    chosen = [case for case in MOCK if not selected or case["name"] in selected]
    conversations = [case for case in CONVERSATIONS if not selected or case["name"] in selected]
    unknown = set(selected or []) - {case["name"] for case in chosen + conversations}
    if unknown:
        raise ValueError("Không có mock: " + ", ".join(sorted(unknown)))
    conn = psycopg.connect(os.environ.get("DATABASE_URL", "dbname=tgdd_products"), autocommit=True)
    try:
        if not selected:
            first = run_shop_graph(conn, {}, ASK_FIRST["user"])
            assert "bao nhiêu" in first["text"].casefold(), first["text"]
            assert not first["products"] and first["checkout"] is None
            print(f"[hoi_ngan_sach_lan_dau] {first['text']}", flush=True)
        for case in chosen:
            print(f"[đang kiểm tra {case['name']}]", flush=True)
            for attempt in range(2):
                try:
                    spoken = run_shop_graph(conn, {}, case["user"], case["history"])
                    break
                except (urllib.error.URLError, TimeoutError, socket.timeout):
                    if attempt:
                        raise
                    print("  Kết nối provider bị gián đoạn; thử lại một lần.", flush=True)
            check_result(unittest.TestCase(), case, spoken)
            print(f"[{case['name']}] {spoken['text']}", flush=True)
            print("  ", [(p["name"], p["price"], spoken["product_reasons"].get(p["product_id"]))
                          for p in spoken["products"]], flush=True)
        from server import assistant_advice_markup
        for scenario in conversations:
            history = []
            for index, step in enumerate(scenario["turns"], 1):
                print(f"[đang kiểm tra {scenario['name']} / lượt {index}] {step['user']}", flush=True)
                for attempt in range(2):
                    try:
                        spoken = run_shop_graph(conn, {}, step["user"], history)
                        break
                    except (urllib.error.URLError, TimeoutError, socket.timeout):
                        if attempt:
                            raise
                        print("  Kết nối provider bị gián đoạn; thử lại một lần.", flush=True)
                check_conversation_turn(unittest.TestCase(), step, spoken)
                print(f"  {spoken['text']}", flush=True)
                print("  ", [(p["product_id"], p["category"], p["price"])
                              for p in spoken["products"]], flush=True)
                history.extend((("user", step["user"]), ("bot", assistant_advice_markup(spoken))))
    finally:
        conn.close()


def run_http(selected=None):
    """Exercise actual session history, rendering, and catalog limits over HTTP."""
    from server import DSN

    scenarios = [case for case in CONVERSATIONS if not selected or case["name"] in selected]
    unknown = set(selected or []) - {case["name"] for case in scenarios}
    if unknown:
        raise ValueError("Không có hội thoại HTTP: " + ", ".join(sorted(unknown)))
    base = os.environ.get("MOCK_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
    with psycopg.connect(DSN, autocommit=True) as conn:
        for scenario in scenarios:
            email = f"codex-mock-{uuid.uuid4().hex}@example.invalid"
            cookies = http.cookiejar.CookieJar()
            client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

            def post(path, fields):
                data = urllib.parse.urlencode(fields).encode()
                request = urllib.request.Request(base + path, data=data, method="POST")
                if path == "/tro-ly":
                    request.add_header("X-Assistant-Panel", "1")
                with client.open(request, timeout=120) as response:
                    return response.read().decode("utf-8", "replace")

            try:
                post("/register", {"name": "Mock Conversation", "email": email,
                                    "password": "mock-test-password"})
                user_id = conn.execute("SELECT id FROM app_users WHERE email=%s", (email,)).fetchone()[0]
                for index, step in enumerate(scenario["turns"], 1):
                    html = post("/tro-ly", {"panel": "1", "q": step["user"]})
                    ids = [int(value) for value in re.findall(r'name="product_id" value="(\d+)"', html)]
                    if step["tool"] == "ask":
                        assert not ids and "bao nhiêu" in html.casefold(), (scenario["name"], index, html[:300])
                    else:
                        assert ids or "không" in html.casefold(), (scenario["name"], index, html[:300])
                        assert html.count('class="advice-reason"') == len(ids), (scenario["name"], index)
                        if ids:
                            rows = conn.execute(
                                "SELECT source_product_id,category,price_vnd FROM products WHERE source_product_id=ANY(%s)",
                                (ids,),
                            ).fetchall()
                            assert len(rows) == len(set(ids)), (scenario["name"], index, ids)
                            for _product_id, category, price in rows:
                                assert category == step["category"], (scenario["name"], index, category)
                                if step.get("exclusive"):
                                    assert price < step["max_price"], (scenario["name"], index, price)
                                else:
                                    assert price <= step["max_price"], (scenario["name"], index, price)
                    saved = conn.execute("SELECT count(*) FROM app_chat_messages WHERE user_id=%s", (user_id,)).fetchone()[0]
                    assert saved == index * 2, (scenario["name"], index, saved)
                    print(f"[{scenario['name']} / HTTP {index}] {step['user']} -> {len(ids)} sản phẩm; lưu {saved} tin", flush=True)
            finally:
                conn.execute("DELETE FROM app_users WHERE email=%s", (email,))


if __name__ == "__main__":
    if "--http" in sys.argv:
        run_http([arg for arg in sys.argv[1:] if arg != "--http"])
    elif "--live" in sys.argv:
        run_live([arg for arg in sys.argv[1:] if arg != "--live"])
    else:
        unittest.main()
