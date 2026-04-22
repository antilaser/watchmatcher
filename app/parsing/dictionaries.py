"""Brand, condition, and currency dictionaries used by the rule-based extractor.

Lists are intentionally lowercased and tokenized; matching is done via
case-insensitive token containment to avoid false positives on substrings.
"""

from __future__ import annotations

# Brand canonical names and their accepted aliases (lowercased on lookup).
BRANDS: dict[str, list[str]] = {
    "Rolex": ["rolex", "rlx", "роллекс", "ролекс"],
    "Patek Philippe": ["patek", "patek philippe", "pp", "патек", "патек филипп"],
    "Audemars Piguet": ["audemars", "audemars piguet", "ap", "АП", "ап"],
    "Richard Mille": ["richard mille", "rm", "ришар миль"],
    "Cartier": ["cartier", "картье"],
    "Omega": ["omega", "омега"],
    "Vacheron Constantin": ["vacheron", "vacheron constantin", "vc", "вашерон"],
    "A. Lange & Söhne": ["lange", "a lange", "a. lange", "a. lange & sohne", "a. lange & söhne"],
    "IWC": ["iwc"],
    "Breitling": ["breitling", "брайтлинг"],
    "Tudor": ["tudor", "тюдор"],
    "Panerai": ["panerai", "панераи"],
    "Hublot": ["hublot", "хублот"],
    "Jaeger-LeCoultre": ["jaeger", "jaeger-lecoultre", "jlc", "jaeger lecoultre"],
}


CONDITION_KEYWORDS: dict[str, list[str]] = {
    "new": ["new", "brand new", "bnib", "unworn", "sealed"],
    "mint": ["mint", "like new", "near mint"],
    "excellent": ["excellent", "great condition", "very good"],
    "good": ["good condition", "good"],
    "worn": ["worn", "used"],
    "polished": ["polished"],
}


SET_COMPLETENESS_KEYWORDS: dict[str, list[str]] = {
    "full_set": ["full set", "fullset", "complete set", "box and papers", "box & papers", "b&p", "boxes papers"],
    "watch_only": ["watch only", "head only", "naked"],
    "papers_only": ["papers only"],
    "box_only": ["box only"],
}


CURRENCY_SYMBOLS: dict[str, str] = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "¥": "JPY",
    "₣": "CHF",
    "chf": "CHF",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "usd": "USD",
    "gbp": "GBP",
    "aed": "AED",
    "jpy": "JPY",
    "jpy¥": "JPY",
    "евро": "EUR",
    "долл": "USD",
    "руб": "RUB",
    "rub": "RUB",
}


SELL_KEYWORDS: list[str] = [
    "for sale",
    "fs ",
    "f/s",
    "for-sale",
    "available",
    "selling",
    "i sell",
    "i'm selling",
    "im selling",
    "offering at",
    "asking",
    "wts",
    "продам",
    "продаю",
    "продается",
    "продажа",
    "vendo",
    "verkaufe",
]

BUY_KEYWORDS: list[str] = [
    "wtb",
    "looking for",
    "looking 4",
    "searching",
    "in search of",
    "iso",
    "want to buy",
    "buying",
    "i buy",
    "i'm looking",
    "im looking",
    "куплю",
    "ищу",
    "нужен",
    "нужна",
    "купим",
    "compro",
    "suche",
]


NEGOTIABLE_KEYWORDS = ["obo", "negotiable", "neg.", "or best offer", "торг"]
