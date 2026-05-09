from __future__ import annotations

from dataclasses import dataclass
import re


_COLOR_ALIASES: dict[str, tuple[str, ...]] = {
    "black": ("black", "noir"),
    "white": ("white", "polar"),
    "silver": ("silver",),
    "blue": ("blue", "bleu"),
    "green": ("green", "vert"),
    "red": ("red",),
    "brown": ("brown", "chocolate", "rootbeer", "root beer"),
    "grey": ("grey", "gray"),
    "champagne": ("champagne",),
    "pink": ("pink",),
    "lavender": ("lavender", "lavander"),
    "gold": ("gold", "yellow gold"),
    "rose gold": ("rose gold", "everose"),
    "two-tone": ("two tone", "two-tone", "bicolor", "bi-color"),
    "tiffany": ("tiffany", "turquoise"),
    "panda": ("panda",),
}

_DIAL_VARIANTS: dict[str, tuple[str, ...]] = {
    "azzurro": ("azzurro", "azzuro"),
    "candy pink": ("candy pink",),
    "dusty pink": ("dusty pink",),
    "ice blue": ("ice blue", "iceblue"),
    "mint green": ("mint green", "mint"),
    "olive": ("olive", "olive green"),
    "palm": ("palm dial", "palm motif", "palm"),
    "panda": ("panda",),
    "rhodium": ("rhodium",),
    "slate": ("slate",),
    "sundust": ("sundust", "sun dust"),
    "tiffany": ("tiffany", "turquoise"),
    "wimbledon": ("wimbledon",),
}

_VARIANT_BASE_COLORS: dict[str, str] = {
    "azzurro": "blue",
    "candy pink": "pink",
    "dusty pink": "pink",
    "ice blue": "blue",
    "mint green": "green",
    "olive": "green",
    "palm": "green",
    "rhodium": "grey",
    "slate": "grey",
    "sundust": "rose gold",
    "tiffany": "blue",
}

_BEZEL_NICKNAMES: dict[str, tuple[str, ...]] = {
    "blue/black": ("batman", "batgirl"),
    "red/blue": ("pepsi",),
    "black/green": ("sprite",),
    "brown/black": ("rootbeer", "root beer"),
    "green": ("starbucks", "cermit", "kermit"),
}

_MATERIAL_ALIASES: dict[str, tuple[str, ...]] = {
    "steel": ("steel", "stainless", "ss", "oystersteel"),
    "yellow gold": ("yellow gold", "yg"),
    "rose gold": ("rose gold", "everose", "rg"),
    "white gold": ("white gold", "wg"),
    "platinum": ("platinum", "plat"),
    "ceramic": ("ceramic", "cerachrom"),
    "titanium": ("titanium",),
    "two-tone": ("two tone", "two-tone", "bicolor", "bi-color", "rolesor"),
}

_BRACELET_ALIASES: dict[str, tuple[str, ...]] = {
    "oyster": ("oyster",),
    "jubilee": ("jubilee",),
    "president": ("president", "presidential"),
    "rubber": ("rubber", "oysterflex"),
    "leather": ("leather", "strap"),
}

_LABEL_RE = re.compile(r"(?im)^\s*(DIAL_COLOR|DIAL_VARIANT|BEZEL_COLOR|CASE_MATERIAL|BRACELET|BRACELET_TYPE|VISUAL_CONFIDENCE|NOTES)\s*:\s*(.+?)\s*$")


@dataclass(frozen=True)
class VisualAttributes:
    dial_color: str | None = None
    dial_variant: str | None = None
    bezel_color: str | None = None
    case_material: str | None = None
    bracelet_type: str | None = None
    visual_confidence: float | None = None

    def as_dict(self) -> dict[str, str | float | None]:
        return {
            "dial_color": self.dial_color,
            "dial_variant": self.dial_variant,
            "bezel_color": self.bezel_color,
            "case_material": self.case_material,
            "bracelet_type": self.bracelet_type,
            "visual_confidence": self.visual_confidence,
        }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    if not v or v in {"none", "unknown", "n/a", "na", "null"}:
        return None
    return re.sub(r"\s+", " ", v)


def _find_alias(text: str, aliases: dict[str, tuple[str, ...]]) -> str | None:
    low = text.lower()
    for canonical, terms in aliases.items():
        for term in terms:
            if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low):
                return canonical
    return None


def _label_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _LABEL_RE.finditer(text):
        out[match.group(1).upper()] = match.group(2).strip()
    return out


def _confidence(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw.strip())
    except ValueError:
        return None
    if value > 1.0 and value <= 100:
        value /= 100.0
    return max(0.0, min(1.0, value))


def extract_visual_attributes(text: str | None) -> VisualAttributes:
    body = text or ""
    labels = _label_values(body)
    visual_text = "\n".join(
        value for key, value in labels.items() if key in {"DIAL_COLOR", "DIAL_VARIANT", "NOTES"}
    )
    search_body = f"{body}\n{visual_text}" if visual_text else body
    labeled_dial = _clean(labels.get("DIAL_COLOR"))
    labeled_variant = _clean(labels.get("DIAL_VARIANT"))
    variant = _find_alias(labeled_variant or "", _DIAL_VARIANTS) or labeled_variant or _find_alias(labeled_dial or "", _DIAL_VARIANTS) or _find_alias(search_body, _DIAL_VARIANTS)
    dial = labeled_dial or _find_alias(search_body, _COLOR_ALIASES)
    if variant and not dial:
        dial = _VARIANT_BASE_COLORS.get(variant)
    elif variant and dial == variant:
        dial = _VARIANT_BASE_COLORS.get(variant, dial)
    bezel = _clean(labels.get("BEZEL_COLOR")) or _find_alias(body, _BEZEL_NICKNAMES)
    case_material = _clean(labels.get("CASE_MATERIAL")) or _find_alias(body, _MATERIAL_ALIASES)
    bracelet = _clean(labels.get("BRACELET_TYPE") or labels.get("BRACELET")) or _find_alias(body, _BRACELET_ALIASES)
    confidence = _confidence(labels.get("VISUAL_CONFIDENCE"))
    return VisualAttributes(
        dial_color=dial,
        dial_variant=variant,
        bezel_color=bezel,
        case_material=case_material,
        bracelet_type=bracelet,
        visual_confidence=confidence,
    )
