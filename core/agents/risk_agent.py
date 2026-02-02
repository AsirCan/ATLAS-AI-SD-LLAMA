from typing import List, Dict, Any
from core.state import PipelineState
from core.agents.base import BaseAgent
from core.agents.base import CancelledError
from core.config import (
    RISK_BLACKLIST_KEYWORDS,
    RISK_WHITELIST_KEYWORDS,
    RISK_CATEGORY_THRESHOLDS,
    RISK_DEFAULT_THRESHOLD,
    RISK_WHITELIST_MAX_SCORE,
)

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
            combined = f"{title} {summary}".lower()

            # Hard blacklist: immediate block
            if any(k in combined for k in RISK_BLACKLIST_KEYWORDS):
                risk_report[title] = {"score": 10, "reason": ["blacklist_hit"]}
                self.log(f"Blocked item (blacklist): {title}")
                continue

            whitelist_hit = any(k in combined for k in RISK_WHITELIST_KEYWORDS)

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
