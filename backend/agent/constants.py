"""Catalog labels and the filters search applies in SQL or after the query."""
import re

GAMING_CPU = re.compile(
    r"snapdragon\s*8|8\s*elite|snapdragon\s*7\s*gen\s*[3-9]|dimensity\s*(8|9|7[3-9]00|8300|8400)|"
    r"\ba1[6-9]\b|exynos\s*2[4-9]|tensor\s*g[3-9]",
    re.I,
)
LAPTOP_GAMING = re.compile(
    r"\brtx\b|\bgtx\b|\brx\s*\d{3,4}\b|\b(?:tuf|nitro|legion|katana|rog|gaming)\b",
    re.I,
)
SPEC_NAMES = (
    "Chip xử lý (CPU)",
    "Chip xử lý",
    "Công nghệ CPU",
    "RAM",
    "Dung lượng pin",
    "Thông tin Pin",
    "Dung lượng lưu trữ",
    "Ổ cứng",
    "Màn hình rộng",
    "Kích thước màn hình",
    "Card màn hình",
    "Hỗ trợ sạc tối đa",
    "Sạc kèm theo máy",
)
STUDY_CPU_SQL = (
    r"core[[:space:]]*i[7-9]|core[[:space:]]*ultra|core[[:space:]]*7([^0-9]|$)"
    r"|ryzen[[:space:]]*(ai[[:space:]]*)?[7-9]|ryzen[[:space:]]*ai"
    r"|apple[[:space:]]*m[0-9]|snapdragon[[:space:]]*x"
)
CATEGORIES = {"phone", "laptop", "tablet", "headphones", "smartwatch"}
LAPTOP_BRANDS = {"Asus", "Dell", "Lenovo", "Acer", "HP", "MSI", "GIGABYTE", "MacBook"}
HEADPHONE_BRANDS = {"Sony"}
