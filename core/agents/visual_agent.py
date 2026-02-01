from typing import List, Dict, Any
from core.state import PipelineState
from core.agents.base import BaseAgent
# import core.config as config  # Would import SD settings here
from core.agents.base import CancelledError

class VisualDirectorAgent(BaseAgent):
    def _execute(self, state: PipelineState) -> PipelineState:
        prompts = []
        
        style_schema = {
            "style": "string (Cinematic, Macro, Documentary, Anime)",
            "visual_description": "string (detailed description of the scene)",
            "negative_prompt": "string (what to avoid)"
        }

        # Select the single best news item to visualize for now, or loop 
        # Strategy: Visualize the top 1 safe news item
        if not state.safe_news_items:
            self.log("No safe news items to visualize.")
            return state

        target_news = state.safe_news_items[0] # Focus on the best story
        self._cancel_guard("before_visual_prompt")
        
        prompt_req = f"""
        Act as an Art Director. Create a visual concept for this news story:
        "{target_news['title']}"
        
        Choose a style that fits the mood (e.g. Serious -> Documentary, Tech -> Cyberpunk).
        Describe the image visually.
        """
        
        try:
            # LLM Suggests
            analysis = self.llm.generate_response(prompt_req, schema=style_schema)
            
            style = analysis.get("style", "Cinematic")
            desc = analysis.get("visual_description", "")
            
            state.visual_style = style
            
            # Python Constructs Final Prompt (Deterministic Template)
            final_prompt = f"{style} style, {desc}, highly detailed, 8k resolution, trending on artstation"
            negative_prompt = analysis.get("negative_prompt", "blur, text, watermark, bad anatomy")
            
            prompts.append(final_prompt)
            state.visual_prompts = prompts
            
            self.log(f"Generated Prompt: {final_prompt[:50]}...")
            self._cancel_guard("before_sd_generation")
            
            # Call actual Stable Diffusion generation
            from core.sd_client import resim_ciz
            success, image_path, _ = resim_ciz(final_prompt)
            
            if success and image_path:
                state.generated_images = [image_path]
                self.log(f"Image successfully generated: {image_path}")
            else:
                self.log("Failed to generate image via SD Client.")
                # Optional: Fail fast or retry strategy could be added here

        except Exception as e:
            self.log(f"Visual Director failed: {e}")
            
        return state
