import re
from typing import List

# Matches hashtags like #AI, #SeaTurtles, #marine_bio
HASHTAG_RE = re.compile(r"(?<![\w#])#[\w]+", re.UNICODE)


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def format_caption_hashtags_bottom(text: str, extra_hashtags: str = "") -> str:
    """
    Normalize caption so hashtags are always at the bottom.
    - Collect hashtags from caption text + extra_hashtags
    - Remove hashtags from main body
    - Rebuild as:
        body

        #tag1 #tag2 ...
    """
    base_text = str(text or "").strip()
    extra = str(extra_hashtags or "").strip()

    tags = _unique_preserve_order(HASHTAG_RE.findall(f"{base_text}\n{extra}"))

    body = HASHTAG_RE.sub("", base_text)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r" *\n *", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"\s+([,.!?;:])", r"\1", body).strip()

    if not tags:
        return body

    hashtag_line = " ".join(tags)
    if not body:
        return hashtag_line
    return f"{body}\n\n{hashtag_line}"

