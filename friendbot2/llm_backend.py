"""
Resident local-LLM backend for persona chat.

Mirrors the FluxBackend pattern: the model is loaded once (NF4-quantized on GPU
by default, ~2.5 GB VRAM for a 3B model) and kept resident, with all torch work
on a single dedicated worker thread so the asyncio event loop never blocks and
the CUDA context stays pinned to one thread.

The model is used completion-style: the prompt is a plain-text chat transcript
("Name: message" per line) ending with "<persona>:", and the model continues it.
This matches the format tools/build_dataset.py emits and tools/train_lora.py
fine-tunes on, so base (non-Instruct) checkpoints work best. If a LoRA adapter
trained on your server's history exists, it is loaded on top of the base model.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class LLMBackend:
    """Loads a (optionally LoRA-adapted) causal LM and generates chat replies."""

    def __init__(
        self,
        base_model: str,
        adapter_path: Optional[Path] = None,
        *,
        quantize_4bit: bool = True,
        context_tokens: int = 1536,
        max_new_tokens: int = 120,
        temperature: float = 0.9,
        top_p: float = 0.95,
    ):
        self.base_model = base_model
        self.adapter_path = Path(adapter_path) if adapter_path else None
        self.quantize_4bit = quantize_4bit
        self.context_tokens = context_tokens
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self._model = None
        self._tokenizer = None
        # max_workers=1 keeps every torch call on the same thread and serializes
        # GPU access, exactly like FluxBackend.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm")

    # -- loading ------------------------------------------------------------
    def _load(self) -> None:
        # Heavy imports stay inside the worker so importing this module is cheap.
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        kwargs: dict = {"dtype": torch.bfloat16}
        if self.quantize_4bit:
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            kwargs["device_map"] = {"": 0}

        log.info("Loading tokenizer + base model %s ...", self.base_model)
        tokenizer = AutoTokenizer.from_pretrained(self.base_model)
        # Long transcripts are trimmed from the oldest lines, not the newest.
        tokenizer.truncation_side = "left"
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(self.base_model, **kwargs)

        if self.adapter_path is not None and self.adapter_path.exists():
            from peft import PeftModel

            log.info("Applying LoRA adapter from %s", self.adapter_path)
            model = PeftModel.from_pretrained(model, self.adapter_path)
        else:
            log.warning(
                "No LoRA adapter found%s — running the raw base model. "
                "Run tools/train_lora.py to create one.",
                f" at {self.adapter_path}" if self.adapter_path else "",
            )

        model.eval()
        self._tokenizer = tokenizer
        self._model = model

    async def load(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._load)

    @property
    def ready(self) -> bool:
        return self._model is not None

    # -- generation ---------------------------------------------------------
    def _chat(self, transcript_lines: list[str], persona: str) -> str:
        import torch

        prompt = "\n".join([*transcript_lines, f"{persona}:"])
        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.context_tokens,
        ).to(self._model.device)

        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=True,
                temperature=self.temperature,
                top_p=self.top_p,
                repetition_penalty=1.1,
                pad_token_id=self._tokenizer.pad_token_id,
            )

        completion = self._tokenizer.decode(
            output[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        # The model continues the whole transcript; keep only the persona's line.
        reply = completion.split("\n", 1)[0].strip()
        if reply.lower().startswith(f"{persona.lower()}:"):
            reply = reply[len(persona) + 1 :].strip()
        return reply[:1900] or "..."

    async def chat(self, transcript_lines: list[str], persona: str) -> str:
        """Continue the transcript as ``persona`` and return their next line."""
        if not self.ready:
            raise RuntimeError("LLM is not loaded yet.")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._chat, list(transcript_lines), persona
        )

    # -- teardown -----------------------------------------------------------
    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
