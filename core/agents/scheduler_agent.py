from datetime import datetime, timedelta
from core.state import PipelineState
from core.agents.base import BaseAgent

class SchedulerAgent(BaseAgent):
    def _execute(self, state: PipelineState) -> PipelineState:
        # Simple Deterministic Logic
        # News is best posted in the evening
        
        now = datetime.now()
        
        # Logic: If it's before 18:00, schedule for today 18:00. 
        # If after, schedule for tomorrow 18:00.
        
        target_hour = 18
        target_minute = 0
        
        candidate_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        if now.hour >= target_hour:
            candidate_time += timedelta(days=1)
            
        state.scheduled_time = candidate_time
        self.log(f"Scheduled for: {state.scheduled_time}")
        
        return state
