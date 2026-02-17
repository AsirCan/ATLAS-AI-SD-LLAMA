from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class PipelineState:
    """
    Single source of truth for the Multi-Agent Pipeline.
    Agents read from this state and write ONLY to their designated fields.
    """
    # News Agent Outputs
    news_items: List[Dict[str, Any]] = field(default_factory=list)
    
    # Risk Agent Outputs
    safe_news_items: List[Dict[str, Any]] = field(default_factory=list)
    risk_analysis: Dict[str, Any] = field(default_factory=dict)
    
    # Visual Agent Outputs
    visual_style: Optional[str] = None
    visual_prompts: List[str] = field(default_factory=list)
    generated_images: List[str] = field(default_factory=list)  # Paths to images
    
    # Caption Agent Outputs
    caption_candidates: List[Dict[str, Any]] = field(default_factory=list)
    final_caption: Optional[str] = None
    
    # Scheduler Agent Outputs
    scheduled_time: Optional[datetime] = None
    
    # Publisher Outputs
    upload_status: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Helper to serialize state for logging."""
        return {
            "news_count": len(self.news_items),
            "safe_news_count": len(self.safe_news_items),
            "visual_style": self.visual_style,
            "generated_images_count": len(self.generated_images),
            "final_caption_preview": self.final_caption[:50] if self.final_caption else None,
            "scheduled_time": str(self.scheduled_time) if self.scheduled_time else None,
            "upload_status": self.upload_status
        }
