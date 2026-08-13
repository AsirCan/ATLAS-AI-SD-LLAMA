from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PipelineState:
    """
    Single source of truth for the Multi-Agent Pipeline.
    Agents read from this state and write ONLY to their designated fields.
    """

    # News Agent Outputs
    news_items: list[dict[str, Any]] = field(default_factory=list)

    # Risk Agent Outputs
    safe_news_items: list[dict[str, Any]] = field(default_factory=list)
    risk_analysis: dict[str, Any] = field(default_factory=dict)

    # Visual Agent Outputs
    visual_style: str | None = None
    visual_prompts: list[str] = field(default_factory=list)
    generated_images: list[str] = field(default_factory=list)  # Paths to images

    # Caption Agent Outputs
    caption_candidates: list[dict[str, Any]] = field(default_factory=list)
    final_caption: str | None = None

    # Scheduler Agent Outputs
    scheduled_time: datetime | None = None

    # Publisher Outputs
    upload_status: dict[str, Any] = field(default_factory=dict)

    # Structured errors carried from agents to API/UI callers.
    errors: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(
        self,
        *,
        stage: str,
        code: str,
        message: str,
        source: str,
        fatal: bool = True,
    ) -> dict[str, Any]:
        error = {
            "stage": stage,
            "code": code,
            "message": message,
            "source": source,
            "fatal": fatal,
        }
        self.errors.append(error)
        return error

    @property
    def fatal_error(self) -> dict[str, Any] | None:
        return next((error for error in self.errors if error.get("fatal")), None)

    def to_dict(self) -> dict[str, Any]:
        """Helper to serialize state for logging."""
        return {
            "news_count": len(self.news_items),
            "safe_news_count": len(self.safe_news_items),
            "visual_style": self.visual_style,
            "generated_images_count": len(self.generated_images),
            "final_caption_preview": self.final_caption[:50] if self.final_caption else None,
            "scheduled_time": str(self.scheduled_time) if self.scheduled_time else None,
            "upload_status": self.upload_status,
            "errors": [dict(error) for error in self.errors],
            "has_fatal_errors": self.fatal_error is not None,
        }
