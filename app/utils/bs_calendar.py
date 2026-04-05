"""
Bikram Sambat calendar utilities.
All month numbers (1-12) in the database correspond to BS months.
"""

BS_MONTHS = {
    1: "Baisakh",
    2: "Jestha",
    3: "Ashadh",
    4: "Shrawan",
    5: "Bhadra",
    6: "Ashwin",
    7: "Kartik",
    8: "Mangsir",
    9: "Poush",
    10: "Magh",
    11: "Falgun",
    12: "Chaitra",
}

BS_MONTH_NAMES = list(BS_MONTHS.values())  # ordered list, index 0 = Baisakh


def bs_period_label(year_bs: int, month: int) -> str:
    """Return a human-readable period label e.g. '2078 Baisakh'."""
    return f"{year_bs} {BS_MONTHS.get(month, str(month))}"
