import re
import unicodedata


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return normalized.strip()


def compact_text(text: str) -> str:
    normalized = normalize_text(text)
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠ー]+", "", normalized)