import logging

from core.agents.base import CancelledError
from core.agents.caption_agent import CaptionAgent

# Agents
from core.agents.news_agent import NewsAgent
from core.agents.risk_agent import RiskAgent
from core.agents.scheduler_agent import SchedulerAgent
from core.agents.visual_agent import VisualDirectorAgent

# Output
from core.clients.insta_client import login_and_upload
from core.clients.llm import LLMService
from core.content.news_memory import mark_used_titles
from core.errors import AtlasError
from core.pipeline.state import PipelineState

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self._log_callback = None
        self._cancel_checker = None

        # Init Infrastructure
        self.llm = LLMService()  # Uses default from core/clients/llm.py
        self.state = PipelineState()

        # Init Agents
        self.news_agent = NewsAgent(self.llm)
        self.risk_agent = RiskAgent(self.llm)
        self.visual_agent = VisualDirectorAgent(self.llm)
        self.caption_agent = CaptionAgent(self.llm)
        self.scheduler_agent = SchedulerAgent(self.llm)

        # Init IO (Not an Agent)

    def set_logger(self, callback):
        """Propagate logger callback to all agents + orchestrator itself."""
        self._log_callback = callback
        self.news_agent.set_log_callback(callback)
        self.risk_agent.set_log_callback(callback)
        self.visual_agent.set_log_callback(callback)
        self.caption_agent.set_log_callback(callback)
        self.scheduler_agent.set_log_callback(callback)

    def set_cancel_checker(self, checker):
        """Propagate cooperative cancel checker to all agents."""
        self._cancel_checker = checker
        self.llm.set_cancel_checker(checker)
        self.news_agent.set_cancel_checker(checker)
        self.risk_agent.set_cancel_checker(checker)
        self.visual_agent.set_cancel_checker(checker)
        self.caption_agent.set_cancel_checker(checker)
        self.scheduler_agent.set_cancel_checker(checker)

    def _log(self, message: str):
        full = f"[Orchestrator] {message}"
        logger.info(full)
        if self._log_callback:
            self._log_callback(full)

    def _cancel_guard(self, where: str):
        if callable(self._cancel_checker) and self._cancel_checker():
            raise CancelledError(f"Cancelled ({where})")

    def _fail(self, *, stage: str, code: str, message: str, source: str) -> PipelineState:
        if not any(error.get("code") == code and error.get("stage") == stage for error in self.state.errors):
            self.state.add_error(
                stage=stage,
                code=code,
                message=message,
                source=source,
                fatal=True,
            )
        self.state.upload_status = {"success": False, "message": message}
        self._log(f"PIPELINE FAILURE [{code}]: {message}")
        return self.state

    def _stop_on_recorded_error(self) -> PipelineState | None:
        error = self.state.fatal_error
        if error is None:
            return None
        return self._fail(
            stage=str(error.get("stage") or "pipeline"),
            code=str(error.get("code") or "pipeline_failed"),
            message=str(error.get("message") or "Pipeline tamamlanamadı."),
            source=str(error.get("source") or "Orchestrator"),
        )

    def run_pipeline(self):
        stage = "starting"
        try:
            self._log(f"Starting pipeline. Dry Run: {self.dry_run}")
            self._cancel_guard("start")

            stage = "news"
            self._log("Step 1/6: News Gathering")
            self.state = self.news_agent.process(self.state)
            self._cancel_guard("after_news")
            if failed := self._stop_on_recorded_error():
                return failed
            if not self.state.news_items:
                return self._fail(
                    stage=stage,
                    code="news_output_missing",
                    message="Haber kaynağından işlenebilir içerik alınamadı.",
                    source="NewsAgent",
                )

            stage = "risk"
            self._log("Step 2/6: Risk Analysis")
            self.state = self.risk_agent.process(self.state)
            self._cancel_guard("after_risk")
            if failed := self._stop_on_recorded_error():
                return failed
            if not self.state.safe_news_items:
                return self._fail(
                    stage=stage,
                    code="safe_news_output_missing",
                    message="Paylaşım için güvenli bir haber bulunamadı.",
                    source="RiskAgent",
                )

            stage = "visual"
            self._log("Step 3/6: Visual Generation")
            self.state = self.visual_agent.process(self.state)
            self._cancel_guard("after_visual")
            if failed := self._stop_on_recorded_error():
                return failed
            if not self.state.generated_images:
                return self._fail(
                    stage=stage,
                    code="visual_output_missing",
                    message="Stable Diffusion görsel üretemedi.",
                    source="VisualDirectorAgent",
                )
            used_title = self.state.safe_news_items[0].get("title")
            if used_title:
                mark_used_titles([used_title], source="agent")

            stage = "caption"
            self._log("Step 4/6: Captioning")
            self.state = self.caption_agent.process(self.state)
            self._cancel_guard("after_caption")
            if failed := self._stop_on_recorded_error():
                return failed
            if not self.state.final_caption:
                return self._fail(
                    stage=stage,
                    code="caption_output_missing",
                    message="Gönderi açıklaması üretilemedi.",
                    source="CaptionAgent",
                )

            stage = "schedule"
            self._log("Step 5/6: Scheduling")
            self.state = self.scheduler_agent.process(self.state)
            self._cancel_guard("after_schedule")
            if failed := self._stop_on_recorded_error():
                return failed
            if not self.state.scheduled_time:
                return self._fail(
                    stage=stage,
                    code="schedule_output_missing",
                    message="Yayın zamanı belirlenemedi.",
                    source="SchedulerAgent",
                )

            stage = "publish"
            self._cancel_guard("before_publish")
            target_image = self.state.generated_images[0]
            target_caption = self.state.final_caption

            self._log("Step 6/6: Publishing")
            self._log(f"Publish preview image: {target_image}")
            self._log(f"Publish time: {self.state.scheduled_time}")

            if self.dry_run:
                self._log("Dry Run: Skipping upload.")
                result = {"success": True, "message": "Dry Run OK"}
            else:
                success, msg = login_and_upload(target_image, target_caption)
                result = {"success": success, "message": msg, "url": "Check Instagram" if success else None}

            self.state.upload_status = result
            if not result.get("success"):
                self.state.add_error(
                    stage=stage,
                    code="publish_failed",
                    message=str(result.get("message") or "Instagram yüklemesi başarısız oldu."),
                    source="InstagramPublisher",
                    fatal=True,
                )
                return self.state

            self._log("Pipeline complete.")
            return self.state
        except CancelledError as exc:
            self._log(f"Cancelled: {exc}")
            self.state.upload_status = {"success": False, "message": "Cancelled"}
            return self.state
        except AtlasError as exc:
            logger.exception("Pipeline failed at stage %s", stage)
            return self._fail(
                stage=stage,
                code=exc.code,
                message=exc.user_message,
                source=type(exc).__name__,
            )
        except Exception:
            logger.exception("Unexpected pipeline failure at stage %s", stage)
            return self._fail(
                stage=stage,
                code="pipeline_failed",
                message="Pipeline beklenmeyen bir hata nedeniyle durdu.",
                source="Orchestrator",
            )
