import time
from typing import Any, Dict

from core.agents.base import BaseAgent, CancelledError
from core.clients.llm import unload_ollama
from core.pipeline.state import PipelineState


class VisualDirectorAgent(BaseAgent):
    DEFAULT_STYLE = "cinematic documentary realism"
    PROMPT_MAX_CHARS = 520

    # Stronger negative prompt tuned for photoreal news-like outputs.
    SD_NEGATIVE_PROMPT = (
        "cartoon, anime, illustration, painting, drawing, text, watermark, signature, logo, "
        "meme layout, collage, split image, bad anatomy, bad proportions, deformed, blurry, noisy, "
        "low quality, pixelated, malformed limbs, extra fingers, missing fingers, fused fingers, "
        "poorly drawn face, asymmetrical eyes, cloned face, distorted face, plastic skin, "
        "overexposed, underexposed"
    )

    def _build_prompt_request(self, target_news: Dict[str, Any]) -> str:
        title = str(target_news.get("title", "")).strip()
        summary = str(target_news.get("summary", "")).strip()
        return (
            "You are a senior visual director creating a single image prompt for SDXL.\n"
            "Task: Convert this news into one photoreal cinematic scene.\n\n"
            f"NEWS TITLE: {title}\n"
            f"NEWS SUMMARY: {summary}\n\n"
            "Rules:\n"
            "1. Output must be ENGLISH only.\n"
            "2. Focus on symbolic/representative scene, not specific real politicians or exact text/numbers.\n"
            "3. Keep it realistic and camera-driven: documentary photography, natural materials, believable lighting.\n"
            "4. Include composition/camera details: lens, framing, lighting, atmosphere.\n"
            "5. Keep it simple and coherent: one main subject, at most two secondary elements.\n"
            "6. Avoid crowds, chaotic action, impossible geometry, and excessive object count.\n"
            "7. If humans appear, prefer mid or wide shot (not extreme close-up portrait).\n"
            "8. Explicitly avoid text overlays in the image.\n"
            "9. Output ONLY one final prompt string, no explanations.\n"
        )

    def _ensure_required_terms(self, prompt: str) -> str:
        required_terms = [
            "photorealistic",
            "single coherent composition",
            "physically plausible scene",
            "realistic human anatomy",
            "natural face symmetry",
            "realistic hands",
            "cinematic lighting",
            "35mm lens",
            "no text",
            "no watermark",
        ]
        output = (prompt or "").strip()
        lowered = output.lower()
        for term in required_terms:
            if term.lower() not in lowered:
                output = f"{output}, {term}" if output else term
                lowered = output.lower()
        return output

    def _normalize_prompt(self, prompt: str, target_news: Dict[str, Any]) -> str:
        cleaned = (prompt or "").replace("\n", " ").strip()
        if ":" in cleaned and len(cleaned.split(":", 1)[0]) < 24:
            cleaned = cleaned.split(":", 1)[1].strip()

        # Fallback when LLM response is too short/noisy.
        if len(cleaned) < 40:
            title = str(target_news.get("title", "")).strip().replace('"', "")
            cleaned = (
                f"A cinematic documentary photograph inspired by '{title}', "
                "wide establishing shot, one clear main subject, realistic environment, soft dramatic lighting, "
                "35mm lens, natural color grading, highly detailed textures"
            )

        cleaned = self._ensure_required_terms(cleaned)
        if len(cleaned) > self.PROMPT_MAX_CHARS:
            cleaned = cleaned[: self.PROMPT_MAX_CHARS].rstrip(", ")
        return cleaned

    def _fallback_retry_prompt(self, target_news: Dict[str, Any]) -> str:
        title = str(target_news.get("title", "")).strip().replace('"', "")
        return (
            f"A photorealistic cinematic news scene inspired by '{title}', "
            "single coherent composition, one main subject, documentary photography, realistic action, "
            "atmospheric depth, 35mm lens, balanced exposure, realistic human anatomy, natural face symmetry, "
            "realistic hands, no text, no watermark"
        )

    def _execute(self, state: PipelineState) -> PipelineState:
        if not state.safe_news_items:
            self.log("No safe news items to visualize.")
            return state

        target_news = state.safe_news_items[0]
        self._cancel_guard("before_visual_prompt")

        try:
            prompt_req = self._build_prompt_request(target_news)
            llm_prompt = self.llm.ask_english(prompt_req, timeout=60, retries=2)
            final_prompt = self._normalize_prompt(llm_prompt, target_news)

            state.visual_style = self.DEFAULT_STYLE
            state.visual_prompts = [final_prompt]
            self.log(f"Generated Prompt: {final_prompt[:120]}...")

            self._cancel_guard("before_sd_vram_cleanup")
            unload_ollama()
            for _ in range(6):
                self._cancel_guard("sd_vram_cooldown")
                time.sleep(0.25)

            self._cancel_guard("before_sd_generation")
            from core.clients.sd_client import resim_ciz

            success, image_path, _ = resim_ciz(
                final_prompt,
                negative_prompt=self.SD_NEGATIVE_PROMPT,
                cancel_checker=self.cancel_checker,
            )
            self._cancel_guard("after_sd_generation")

            if not success:
                self._cancel_guard("before_sd_retry")
                retry_prompt = self._fallback_retry_prompt(target_news)
                state.visual_prompts.append(retry_prompt)
                self.log("First SD attempt failed. Retrying with fallback prompt.")
                success, image_path, _ = resim_ciz(
                    retry_prompt,
                    negative_prompt=self.SD_NEGATIVE_PROMPT,
                    cancel_checker=self.cancel_checker,
                )
                self._cancel_guard("after_sd_retry")

            if success and image_path:
                state.generated_images = [image_path]
                self.log(f"Image successfully generated: {image_path}")
            else:
                self.log("Failed to generate image via SD Client.")

        except CancelledError:
            raise
        except Exception as e:
            self.log(f"Visual Director failed: {e}")

        return state
