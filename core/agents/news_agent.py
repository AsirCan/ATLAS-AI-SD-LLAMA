import re
from typing import List, Dict, Any, Optional
import feedparser
from core.pipeline.state import PipelineState
from core.agents.base import BaseAgent
from core.clients.llm import LLMService
from core.content.news_fetcher import RSS_SOURCES
from core.agents.base import CancelledError
from core.content.news_memory import get_used_title_set, normalize_title, prune_expired
from core.runtime.config import USED_NEWS_TTL_DAYS


def _find_keyword_hit(text: str, keywords: List[str]) -> Optional[str]:
    haystack = str(text or "").lower()
    for kw in keywords:
        pattern = rf"\b{re.escape(str(kw).lower())}\b"
        if re.search(pattern, haystack):
            return kw
    return None


class NewsAgent(BaseAgent):
    def __init__(self, llm_service: LLMService, rss_urls: List[str] = None):
        super().__init__(llm_service)
        # Default RSS list if none provided (single source of truth)
        self.rss_urls = rss_urls or list(RSS_SOURCES)

    def _execute(self, state: PipelineState) -> PipelineState:
        raw_news = self._fetch_news()
        
        if not raw_news:
            self.log("[NewsAgent] ⚠️ WARNING: No news fetched from any source.")
            return state

        scored_news = self._score_news(raw_news)
        
        # Deterministic Selection: keep more candidates to give RiskAgent enough room
        # Python Logic: Sort by integer score
        selected_news = sorted(scored_news, key=lambda x: x.get('final_score', 0), reverse=True)[:10]
        
        state.news_items = selected_news
        self.log(f"Selected {len(selected_news)} news items from {len(raw_news)} raw items.")
        return state

    def _fetch_news(self) -> List[Dict[str, str]]:
        items = []
        blocked_keywords = [
            "rape", "sexual", "sex", "epstein",
            "deadly", "killed", "murder", "shoot", "shooting",
            "bomb", "attack", "terror", "war",
        ]
        ttl_seconds = USED_NEWS_TTL_DAYS * 24 * 60 * 60
        prune_expired(ttl_seconds)
        used_set = get_used_title_set(ttl_seconds)

        for url in self.rss_urls:
            self._cancel_guard("fetch_news")
            try:
                self.log(f"Fetching: {url}...")
                feed = feedparser.parse(url)
                
                # Check for bozo bit (malformed XML) or empty entries
                if not feed.entries:
                    self.log(f"  -> No entries found in {url}")
                    continue
                    
                count = 0
                for entry in feed.entries[:5]: # Take top 5 from each feed to save processing
                    self._cancel_guard("fetch_news_entries")
                    title = getattr(entry, "title", "")
                    if _find_keyword_hit(title, blocked_keywords):
                        continue
                    if normalize_title(title) in used_set:
                        continue
                    items.append({
                        "title": title,
                        "link": entry.link,
                        "summary": getattr(entry, 'summary', '')
                    })
                    count += 1
                self.log(f"  -> Fetched {count} items.")
            except Exception as e:
                self.log(f"Error fetching RSS {url}: {e}")
        return items

    def _score_news(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        scored_items = []
        # Schema for LLM validation
        score_schema = {
            "emotional_score": "integer (0-10)",
            "viral_potential": "integer (0-10)",
            "reason": "string"
        }
        
        for item in items:
            self._cancel_guard("score_news")
            prompt = f"""
            Analyze this news item for social media potential.
            Title: {item['title']}
            Summary: {item['summary']}
            
            Rate on 0-10 scale:
            - Emotional Impact (how likely to trigger emotion)
            - Viral Potential (how likely to be shared)
            """
            
            try:
                # LLM provides ANALYSIS (Scores)
                analysis = self.llm.generate_response(prompt, schema=score_schema)
                
                emotional = int(analysis.get("emotional_score", 0))
                viral = int(analysis.get("viral_potential", 0))
                
                # Python provides DECISION (Weighted Score)
                # Formula: 60% Viral + 40% Emotional
                final_score = (viral * 0.6) + (emotional * 0.4)
                
                item_data = item.copy()
                item_data.update({
                    "emotional_score": emotional,
                    "viral_potential": viral,
                    "final_score": final_score,
                    "analysis_reason": analysis.get("reason", "")
                })
                scored_items.append(item_data)
                
            except Exception as e:
                self.log(f"Skipping item '{item['title'][:20]}...' due to scoring error: {e}")
        
        return scored_items

