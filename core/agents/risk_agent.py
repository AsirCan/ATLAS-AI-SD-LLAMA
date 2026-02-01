from typing import List, Dict, Any
from core.state import PipelineState
from core.agents.base import BaseAgent
from core.agents.base import CancelledError

class RiskAgent(BaseAgent):
    def _execute(self, state: PipelineState) -> PipelineState:
        safe_items = []
        risk_report = {}
        
        risk_schema = {
            "risk_score": "integer (0-10, 0=Safe, 10=Dangerous)",
            "categories": ["list of strings (e.g. 'violence', 'political_bias')"],
            "safe_to_post": "boolean"
        }

        for item in state.news_items:
            self._cancel_guard("risk_loop")
            prompt = f"""
            Analyze this news item for Instagram Brand Safety.
            Title: {item['title']}
            Summary: {item['summary']}
            
            Check for:
            1. Violence / Gore
            2. Hate Speech
            3. Explicit Political Bias / Controversy
            4. Misinformation / Clickbait Risk
            
            Return a risk score (0-10). 0 is perfectly safe. >5 is risky.
            """
            
            try:
                # LLM provides ANALYSIS
                analysis = self.llm.generate_response(prompt, schema=risk_schema)
                
                risk_score = int(analysis.get("risk_score", 10)) # Default to high risk on error
                
                # Python provides DECISION
                # Logic (deterministic): primarily trust numeric risk_score.
                # The model's boolean can be overly conservative/inconsistent; treat it as a hint only.
                # Threshold: <=4 safe, >=5 blocked.
                is_safe = risk_score <= 4
                
                risk_report[item['title']] = {
                    "score": risk_score,
                    "reason": analysis.get("categories", [])
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
