"""
Commodity name normalisation and category inference for Kalimati data.
Variants such as "(Nepali)", "(Indian)", "(Local)" are treated as distinct
commodities so that users can compare them directly.
"""

import sqlite3
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Category keyword mapping (lower-case)
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "vegetable": [
        "tomato", "potato", "onion", "garlic", "carrot", "radish", "cabbage",
        "cauliflower", "peas", "bean", "brinjal", "gourd", "cucumber",
        "spinach", "mushroom", "ginger", "turmeric", "yam", "taro",
        "leek", "celery", "asparagus", "artichoke", "turnip", "beet",
        "okra", "corn", "maize", "squash", "pumpkin", "zucchini",
        "capsicum", "chayote", "bitter", "drumstick", "ivy", "broadbean",
        "springonion", "spring onion",
    ],
    "fruit": [
        "apple", "banana", "mango", "orange", "papaya", "pomegranate",
        "grape", "pear", "plum", "lemon", "guava", "litchi", "pineapple",
        "watermelon", "melon", "avocado", "peach", "apricot", "cherry",
        "kiwi", "coconut", "jackfruit", "fig", "date", "berry",
        "mandarin", "tangerine", "lime", "grapefruit",
    ],
    "spice": [
        "chili", "chilli", "pepper", "coriander", "cumin", "fenugreek",
        "mustard", "cardamom", "clove", "cinnamon", "bay", "anise",
        "fennel", "saffron", "turmeric",
    ],
    "fish": [
        "fish", "rohu", "catfish", "tilapia", "salmon", "tuna", "carp",
        "prawn", "shrimp",
    ],
}


def normalize_name(raw_name: str) -> str:
    """
    Strip leading/trailing whitespace and normalise internal whitespace.
    Preserve parenthetical suffixes like (Nepali), (Indian), (Local) so that
    commodity variants remain distinct in the database.
    Apply title-case to the base name (not inside parentheses).
    """
    if not isinstance(raw_name, str):
        return ""

    name = raw_name.strip()
    # Collapse multiple internal spaces
    name = re.sub(r"  +", " ", name)

    # Split on first opening parenthesis to title-case only the base
    match = re.match(r"^(.*?)(\(.*\))?$", name, re.DOTALL)
    if match:
        base = match.group(1).strip().title()
        suffix = match.group(2) or ""
        # Normalise suffix capitalisation: (nepali) -> (Nepali)
        if suffix:
            suffix = "(" + suffix[1:-1].strip().title() + ")"
        name = (base + " " + suffix).strip() if suffix else base

    return name


def _infer_category(name: str) -> str:
    """Return the commodity category based on keyword matching."""
    lower = name.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return category
    return "other"


def get_or_create_commodity(conn: sqlite3.Connection, raw_name: str) -> Optional[int]:
    """
    Return the commodity_id for *raw_name*, inserting a new row when needed.
    Returns None if the normalised name is empty (skip the record).
    """
    name = normalize_name(raw_name)
    if not name:
        return None

    cursor = conn.cursor()

    # Try to find existing
    cursor.execute("SELECT id FROM commodities WHERE name_en = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Insert new
    category = _infer_category(name)
    cursor.execute(
        "INSERT INTO commodities (name_en, category) VALUES (?, ?)",
        (name, category),
    )
    conn.commit()
    return cursor.lastrowid
