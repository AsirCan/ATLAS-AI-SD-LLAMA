import re
from typing import List, Dict, Any, Optional
from core.pipeline.state import PipelineState
from core.agents.base import BaseAgent
from core.agents.base import CancelledError
from core.runtime.config import (
    RISK_BLACKLIST_KEYWORDS,
    RISK_WHITELIST_KEYWORDS,
    RISK_CATEGORY_THRESHOLDS,
    RISK_DEFAULT_THRESHOLD,
    RISK_WHITELIST_MAX_SCORE,
)


def _find_keyword_hit(text: str, keywords: List[str]) -> Optional[str]:
    haystack = str(text or "").lower()
    for kw in keywords:
        # Match whole words to avoid false positives like "war" inside "water".
        pattern = rf"\b{re.escape(str(kw).lower())}\b"
        if re.search(pattern, haystack):
            return kw
    return None


class RiskAgent(BaseAgent):
    def _execute(self, state: PipelineState) -> PipelineState:
        safe_items = []
        risk_report = {}
        
        risk_schema = {
            "risk_score": "integer (0-10, 0=Safe, 10=Dangerous)",
            "categories": [
                "list of strings from: violence, hate_speech, adult, sexual, politics, political_bias, misinformation, drugs"
            ],
            "safe_to_post": "boolean"
        }

        for item in state.news_items:
            self._cancel_guard("risk_loop")
            title = item.get("title", "")
            summary = item.get("summary", "")
            combined = f"{title} {summary}"

            # Hard blacklist: immediate block
            blacklisted_kw = _find_keyword_hit(combined, RISK_BLACKLIST_KEYWORDS)
            if blacklisted_kw:
                risk_report[title] = {"score": 10, "reason": [f"blacklist_hit:{blacklisted_kw}"]}
                self.log(f"Blocked item (blacklist:{blacklisted_kw}): {title}")
                continue

            whitelist_hit = _find_keyword_hit(combined, RISK_WHITELIST_KEYWORDS) is not None

            prompt = f"""
            Analyze this news item for Instagram Brand Safety.
            Title: {title}
            Summary: {summary}
            
            Check for:
            1. Violence / Gore
            2. Hate Speech
            3. Sexual / Adult
            4. Explicit Political Bias / Controversy
            5. Misinformation / Clickbait Risk
            6. Drugs
            
            Return a risk score (0-10). 0 is perfectly safe. >5 is risky.
            Use only the category labels provided in the schema.
            """
            
            try:
                # LLM provides ANALYSIS
                analysis = self.llm.generate_response(prompt, schema=risk_schema)
                
                risk_score = int(analysis.get("risk_score", 10)) # Default to high risk on error
                categories = analysis.get("categories", [])
                categories = [str(c).strip().lower().replace(" ", "_") for c in categories]
                
                # Category-based thresholding
                threshold = RISK_DEFAULT_THRESHOLD
                for c in categories:
                    if c in RISK_CATEGORY_THRESHOLDS:
                        threshold = min(threshold, RISK_CATEGORY_THRESHOLDS[c])

                # Whitelist soft-pass (still respects a max score)
                if whitelist_hit and risk_score <= RISK_WHITELIST_MAX_SCORE:
                    is_safe = True
                else:
                    is_safe = risk_score <= threshold
                
                risk_report[item['title']] = {
                    "score": risk_score,
                    "reason": categories
                }
                
                if is_safe:
                    safe_items.append(item)
                else:
                    self.log(f"Blocked item: {item['title']} (Score: {risk_score})")

            except Exception as e:
                self.log(f"Risk check failed for item '{item['title'][:20]}...'. default BLOCK.")
                risk_report[item['title']] = {"error": str(e)}

        state.safe_news_items = safe_items
        state.risk_analysis = risk_report
        
        self.log(f"Risk Filter: {len(state.news_items)} -> {len(safe_items)} safe items.")
        return state

