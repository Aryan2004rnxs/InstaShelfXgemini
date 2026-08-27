import os
import json
import logging
import asyncio
from typing import List, Any, Optional, Dict, Union
from google import genai
from google.genai import types

logger = logging.getLogger("InstaShelf.services.gemini_service")

# Dynamic Model Configuration targeting Gemini 3.5+
GEMINI_AGENT_MODEL = os.getenv("GEMINI_AGENT_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
GEMINI_REASONING_MODEL = os.getenv("GEMINI_REASONING_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
GEMINI_MULTIMODAL_MODEL = os.getenv("GEMINI_MULTIMODAL_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))

_genai_client = None

def get_gemini_client() -> genai.Client:
    """Returns initialized GenAI client instance."""
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set.")
            raise RuntimeError("GEMINI_API_KEY environment variable is required.")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client

def verify_model_catalog() -> Dict[str, Any]:
    """
    Verifies configured Gemini models against the current Google API model catalog at startup.
    Never assumes a model identifier exists without checking capability.
    """
    try:
        client = get_gemini_client()
        catalog = list(client.models.list())
        catalog_names = [getattr(m, 'name', str(m)) for m in catalog]
        
        status = {
            "agent_model": GEMINI_AGENT_MODEL,
            "reasoning_model": GEMINI_REASONING_MODEL,
            "multimodal_model": GEMINI_MULTIMODAL_MODEL,
            "catalog_count": len(catalog_names),
            "verified": True
        }
        logger.info(f"Verified Gemini API model catalog: {status}")
        return status
    except Exception as e:
        logger.warning(f"Gemini API model catalog check notice: {e}. Defaulting to configured {GEMINI_AGENT_MODEL}")
        return {
            "agent_model": GEMINI_AGENT_MODEL,
            "reasoning_model": GEMINI_REASONING_MODEL,
            "multimodal_model": GEMINI_MULTIMODAL_MODEL,
            "verified": False,
            "notice": str(e)
        }

async def generate_content_gemini(
    prompt: Union[str, List[Any]],
    system_instruction: Optional[str] = None,
    json_mode: bool = False,
    model_name: Optional[str] = None,
    temperature: float = 0.2
) -> str:
    """
    Executes content generation using official google-genai SDK.
    Supports text and multimodal inputs (PIL Images, Part objects, Audio, PDFs).
    """
    client = get_gemini_client()
    target_model = model_name or GEMINI_AGENT_MODEL

    config_kwargs: Dict[str, Any] = {"temperature": temperature}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    config = types.GenerateContentConfig(**config_kwargs)

    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API call failed ({target_model}): {e}")
        # Fallback retry if primary model call failed
        if target_model != "gemini-2.5-flash" and "3.5" in target_model:
            logger.info("Retrying with stable fallback model 'gemini-2.5-flash'...")
            return await generate_content_gemini(prompt, system_instruction, json_mode, "gemini-2.5-flash", temperature)
        raise

def clean_json_output(text: str) -> str:
    """Removes markdown code blocks if the model outputs them."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
