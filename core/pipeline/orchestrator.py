from core.pipeline.state import PipelineState
from core.clients.llm import LLMService
# Agents
from core.agents.news_agent import NewsAgent
from core.agents.risk_agent import RiskAgent
from core.agents.visual_agent import VisualDirectorAgent
from core.agents.caption_agent import CaptionAgent
from core.agents.scheduler_agent import SchedulerAgent
# Output
from core.clients.insta_client import login_and_upload
from core.agents.base import CancelledError
from core.content.news_memory import mark_used_titles

class Orchestrator:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self._log_callback = None
        self._cancel_checker = None
        
        # Init Infrastructure
        self.llm = LLMService() # Uses default from core/clients/llm.py
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
        try:
            self.llm.set_cancel_checker(checker)
        except Exception:
            pass
        self.news_agent.set_cancel_checker(checker)
        self.risk_agent.set_cancel_checker(checker)
        self.visual_agent.set_cancel_checker(checker)
        self.caption_agent.set_cancel_checker(checker)
        self.scheduler_agent.set_cancel_checker(checker)

    def _log(self, message: str):
        full = f"[Orchestrator] {message}"
        print(full)
        if self._log_callback:
            self._log_callback(full)

    def _cancel_guard(self, where: str):
        try:
            if callable(self._cancel_checker) and self._cancel_checker():
                raise CancelledError(f"Cancelled ({where})")
        except CancelledError:
            raise
        except Exception:
            # If cancel checker fails, ignore.
            return

    def run_pipeline(self):
        try:
            self._log(f"Starting pipeline. Dry Run: {self.dry_run}")
            self._cancel_guard("start")
        
            # 1. News Gathering
            self._log("Step 1/6: News Gathering")
            self.state = self.news_agent.process(self.state)
            self._cancel_guard("after_news")
            if not self.state.news_items:
                self._log("GUARD FAILURE: No news items found. Aborting.")
                return self.state

            # 2. Risk Analysis
            self._log("Step 2/6: Risk Analysis")
            self.state = self.risk_agent.process(self.state)
            self._cancel_guard("after_risk")
            if not self.state.safe_news_items:
                self._log("GUARD FAILURE: No safe news items passed risk filter. Aborting.")
                return self.state

            # 3. Visual Director
            self._log("Step 3/6: Visual Generation")
            self.state = self.visual_agent.process(self.state)
            self._cancel_guard("after_visual")
            if not self.state.generated_images:
                self._log("GUARD FAILURE: No images generated. Aborting.")
                return self.state
            # Mark the used news title after successful visual generation
            if self.state.safe_news_items:
                used_title = self.state.safe_news_items[0].get("title")
                if used_title:
                    mark_used_titles([used_title], source="agent")

            # 4. Captioning
            self._log("Step 4/6: Captioning")
            self.state = self.caption_agent.process(self.state)
            self._cancel_guard("after_caption")
            if not self.state.final_caption:
                self._log("GUARD FAILURE: No caption generated. Aborting.")
                return self.state

            # 5. Scheduling
            self._log("Step 5/6: Scheduling")
            self.state = self.scheduler_agent.process(self.state)
            self._cancel_guard("after_schedule")
            if not self.state.scheduled_time:
                self._log("GUARD FAILURE: scheduling failed. Aborting.")
                return self.state

            # 6. Publishing (IO Layer)
            self._cancel_guard("before_publish")
            # Verify invariants one last time
            target_image = self.state.generated_images[0]
            target_caption = self.state.final_caption
            
            self._log("Step 6/6: Publishing")
            self._log(f"Publish preview image: {target_image}")
            self._log(f"Publish time: {self.state.scheduled_time}")
            
            # Execute
            if self.dry_run:
                self._log("Dry Run: Skipping upload.")
                result = {"success": True, "message": "Dry Run OK"}
            else:
                success, msg = login_and_upload(target_image, target_caption)
                result = {
                    "success": success,
                    "message": msg,
                    "url": "Check Instagram" if success else None
                }
            
            self.state.upload_status = result
            self._log("Pipeline complete.")
            return self.state
        except CancelledError as e:
            self._log(f"Cancelled: {e}")
            # Mark state for callers
            self.state.upload_status = {"success": False, "message": "Cancelled"}
            return self.state

