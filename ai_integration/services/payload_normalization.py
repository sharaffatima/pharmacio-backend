from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional, Tuple


_DEFAULT_CONFIDENCE = 0.5


def _normalize_digits(text: str) -> str:
    # Convert Arabic-Indic digits to ASCII digits for parsing.
    arabic_indic = "٠١٢٣٤٥٦٧٨٩"
    eastern_arabic_indic = "۰۱۲۳۴۵۶۷۸۹"
    trans = {}
    for i, digit in enumerate(arabic_indic):
        trans[ord(digit)] = str(i)
    for i, digit in enumerate(eastern_arabic_indic):
        trans[ord(digit)] = str(i)
    return text.translate(trans)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _clean_text_advanced(value: Any) -> str:
    """
    Adapted from the notebook cleaning routine to normalize Arabic OCR noise.
    """
    text = _clean_text(value)
    if not text:
        return ""

    replacements = {
        "ى": "ي",
        "ة": "ه",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ؤ": "و",
        "ئ": "ي",
        "گ": "ك",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[/\\><{}\[\]()~_|+\-=]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_number_with_english(text: str) -> str:
    text = re.sub(r"(\d+)\s*([a-zA-Z]+)", r"\1\2", text)
    text = re.sub(r"([a-zA-Z]+)\s*(\d+)", r"\2\1", text)
    return text


def _normalize_spacing_between_numbers_and_words(text: str) -> str:
    text = re.sub(r"(\d+)\s+([\u0600-\u06FFa-zA-Z])", r"\1\2", text)
    text = re.sub(r"([\u0600-\u06FFa-zA-Z])\s+(\d+)", r"\1\2", text)
    return text


def _normalize_spacing_between_arabic_english(text: str) -> str:
    text = re.sub(r"([\u0600-\u06FF])\s+([a-zA-Z])", r"\1\2", text)
    text = re.sub(r"([a-zA-Z])\s+([\u0600-\u06FF])", r"\1\2", text)
    return text


def _normalize_percentage(text: str) -> str:
    text = re.sub(r"(\d+)\s*%", r"\1%", text)
    text = re.sub(r"%\s*(\d+)", r"\1%", text)
    return text


def _normalize_all(text: str) -> str:
    if not text:
        return ""
    text = _normalize_percentage(text)
    text = _normalize_number_with_english(text)
    text = _normalize_spacing_between_numbers_and_words(text)
    text = _normalize_spacing_between_arabic_english(text)
    return text


def _normalize_product_or_company(value: Any) -> str:
    return _normalize_all(_clean_text_advanced(value))


def _parse_price(raw: str) -> Optional[Decimal]:
    text = _normalize_digits(_clean_text(raw))
    if not text:
        return None

    # Keep only numeric separators and sign.
    text = text.replace("،", ",")
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text:
        return None

    if "." in text and "," in text:
        # Assume comma as thousands separator.
        normalized = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        # If trailing group length is 3, treat as thousands separator.
        if len(parts[-1]) == 3:
            normalized = "".join(parts)
        else:
            normalized = ".".join(parts)
    else:
        normalized = text

    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None

    if value < 0:
        return None

    return value.quantize(Decimal("0.01"))


def _split_product_company(product_cell: str, current_company: Optional[str]) -> Tuple[str, Optional[str]]:
    raw_text = _clean_text(product_cell)
    text = _normalize_product_or_company(raw_text)

    if not text:
        return "", _normalize_product_or_company(current_company)

    # Common format: "product / company"
    if "/" in raw_text:
        left, right = raw_text.rsplit("/", 1)
        left = _normalize_product_or_company(left)
        right = _normalize_product_or_company(right)
        if left and right:
            return left, right

    # Some OCR emits company-only header rows. Keep current company if available.
    return text, _normalize_product_or_company(current_company)


def normalize_ocr_payload_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normalize OCR payloads into unified item records expected by persistence logic.

    Supported input formats:
    1) Legacy normalized shape:
       {"items": [{drug_name, company, price, confidence, review_required}, ...]}
    2) Raw table shape from OCR engine:
       {"page_001_raw_steps": [{"Col_1": ..., "Col_2": ..., "Col_3": ...}, ...], ...}
    """
    if "items" in payload:
        normalized_items: List[Dict[str, Any]] = []
        for item in payload["items"]:
            normalized_items.append(
                {
                    "drug_name": _normalize_product_or_company(item.get("drug_name")),
                    "company": _normalize_product_or_company(item.get("company")) or None,
                    "price": item.get("price"),
                    "confidence": item.get("confidence", _DEFAULT_CONFIDENCE),
                    "review_required": item.get("review_required", False),
                }
            )
        return normalized_items

    items: List[Dict[str, Any]] = []
    current_company: Optional[str] = None

    raw_step_keys = sorted(k for k in payload.keys() if k.endswith("_raw_steps"))
    for page_key in raw_step_keys:
        rows = payload.get(page_key) or []
        for row in rows:
            col_1 = _clean_text(row.get("Col_1"))
            col_3_raw = _clean_text(row.get("Col_3"))
            col_3 = _normalize_product_or_company(col_3_raw)

            # Skip empty rows.
            if not col_1 and not col_3:
                continue

            parsed_price = _parse_price(col_1)

            # Company header-like row: no price and only a label in product column.
            if parsed_price is None and col_3:
                if "/" not in col_3_raw:
                    current_company = col_3
                continue

            if parsed_price is None:
                continue

            drug_name, company = _split_product_company(col_3_raw, current_company)
            if not drug_name:
                continue

            items.append(
                {
                    "drug_name": drug_name,
                    "company": company,
                    "price": parsed_price,
                    # Raw tables do not provide confidence/review flags per row.
                    "confidence": _DEFAULT_CONFIDENCE,
                    "review_required": True,
                }
            )

    return items
