from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from core.state import PipelineState
from core.llm import LLMService


class CancelledError(Exception):
    """Raised when a cooperative cancel is requested."""
    pass

class BaseAgent(ABC):
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self.name = self.__class__.__name__
        self.log_callback = None
        self.cancel_checker: Optional[Callable[[], bool]] = None

    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def set_cancel_checker(self, checker: Optional[Callable[[], bool]]):
        """Inject a cooperative cancel checker callable."""
        self.cancel_checker = checker

    def _is_cancelled(self) -> bool:
        try:
            return bool(self.cancel_checker and self.cancel_checker())
        except Exception:
            return False

    def _cancel_guard(self, where: str = ""):
        if self._is_cancelled():
            msg = f"Cancelled{f' ({where})' if where else ''}."
            self.log(msg)
            raise CancelledError(msg)

    def process(self, state: PipelineState) -> PipelineState:
        """
        Main entry point for the agent.
        1. Logs input state summary.
        2. Executes agent logic.
        3. Logs output summary.
        4. Returns updated state.
        """
        self._cancel_guard("before_process")
        self.log(f"Starting process. Input State: {state.to_dict()}")
        
        try:
            updated_state = self._execute(state)
        except Exception as e:
            self.log(f"CRITICAL ERROR in {self.name}: {str(e)}")
            raise e
            
        self._cancel_guard("after_process")
        self.log(f"Process complete. Output State keys updated.")
        return updated_state

    @abstractmethod
    def _execute(self, state: PipelineState) -> PipelineState:
        """
        Core logic of the agent. 
        Must implement specific reading/writing to PipelineState.
        """
        pass

    def log(self, message: str):
        """Structured logging format."""
        full_msg = f"[{self.name}] {message}"
        print(full_msg)
        if self.log_callback:
            self.log_callback(full_msg)
