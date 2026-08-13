from core.agents.base import BaseAgent
from core.content.caption_format import format_caption_hashtags_bottom
from core.errors import LLMResponseError
from core.pipeline.state import PipelineState


class CaptionAgent(BaseAgent):
    def _execute(self, state: PipelineState) -> PipelineState:
        if not state.safe_news_items:
            return state

        target_news = state.safe_news_items[0]

        schema = {
            "captions": [
                {
                    "text": "string (the caption)",
                    "style": "string (Provocative/Informative/Question)",
                    "engagement_score": "integer (0-10 prediction)",
                }
            ],
            "hashtags": "string (space separated list)",
        }

        prompt = f"""
        Write 3 Instagram captions for this news:
        "{target_news["title"]}"
        
        Styles:
        1. Provocative (Hook-focused)
        2. Informative (Journalistic)
        3. Question (Engagement-focused)
        
        Predict engagement score for each.
        """

        result = self.llm.generate_response(prompt, schema=schema)
        try:
            candidates = result.get("captions", [])
            state.caption_candidates = candidates

            if candidates:
                best_caption = max(candidates, key=lambda x: int(x.get("engagement_score", 0)))
                hashtags = result.get("hashtags", "")
                final_text = format_caption_hashtags_bottom(best_caption.get("text", ""), hashtags)

                state.final_caption = final_text
                self.log(f"Selected Caption ({best_caption['style']}): {final_text[:30]}...")
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise LLMResponseError("Caption response has an invalid shape") from exc

        return state
