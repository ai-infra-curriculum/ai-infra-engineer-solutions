"""
LLM Server Implementation using vLLM

Provides high-performance LLM serving with:
- Continuous batching
- KV cache optimization
- Streaming responses
- Model quantization support
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional, Union
from dataclasses import dataclass
import torch

try:
    from vllm import AsyncLLMEngine, SamplingParams, AsyncEngineArgs
    from vllm.utils import random_uuid
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    logging.warning("vLLM not available, falling back to transformers")

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TextIteratorStreamer,
)
from threading import Thread

from .model_config import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class GenerationRequest:
    """Request for LLM generation"""
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stream: bool = False
    stop_sequences: Optional[List[str]] = None


@dataclass
class GenerationResponse:
    """Response from LLM generation"""
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    model: str


class LLMServer:
    """
    High-performance LLM server with vLLM backend
    Falls back to transformers if vLLM is not available
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.engine = None
        self.use_vllm = VLLM_AVAILABLE and config.use_vllm

        logger.info(f"Initializing LLM server with model: {config.model_name}")
        logger.info(f"Using vLLM: {self.use_vllm}")

    async def initialize(self):
        """Initialize the model and engine"""
        try:
            if self.use_vllm:
                await self._initialize_vllm()
            else:
                await self._initialize_transformers()

            logger.info("LLM server initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM server: {e}")
            raise

    async def _initialize_vllm(self):
        """Initialize vLLM engine"""
        logger.info("Initializing vLLM engine...")

        engine_args = AsyncEngineArgs(
            model=self.config.model_name,
            tokenizer=self.config.tokenizer_name or self.config.model_name,
            dtype=self.config.dtype,
            quantization=self.config.quantization,
            max_model_len=self.config.max_model_len,
            gpu_memory_utilization=self.config.gpu_memory_utilization,
            trust_remote_code=self.config.trust_remote_code,
            download_dir=self.config.cache_dir,
            tensor_parallel_size=self.config.tensor_parallel_size,
        )

        self.engine = AsyncLLMEngine.from_engine_args(engine_args)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.tokenizer_name or self.config.model_name,
            cache_dir=self.config.cache_dir,
        )

        logger.info("vLLM engine initialized")

    async def _initialize_transformers(self):
        """Initialize transformers model (fallback)"""
        logger.info("Initializing transformers model...")

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            cache_dir=self.config.cache_dir,
        )

        # Determine dtype
        dtype = torch.float16 if self.config.dtype == "float16" else torch.float32

        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            cache_dir=self.config.cache_dir,
            torch_dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=self.config.trust_remote_code,
        )

        if torch.cuda.is_available():
            logger.info(f"Model loaded on GPU: {torch.cuda.get_device_name()}")
        else:
            logger.warning("No GPU available, using CPU (will be slow)")

        logger.info("Transformers model initialized")

    async def generate(
        self, request: GenerationRequest
    ) -> Union[GenerationResponse, AsyncGenerator[str, None]]:
        """
        Generate text from prompt

        Args:
            request: Generation request

        Returns:
            GenerationResponse or AsyncGenerator for streaming
        """
        if request.stream:
            return self._generate_stream(request)
        else:
            return await self._generate_sync(request)

    async def _generate_sync(self, request: GenerationRequest) -> GenerationResponse:
        """Non-streaming generation"""
        if self.use_vllm:
            return await self._generate_vllm(request)
        else:
            return await self._generate_transformers(request)

    async def _generate_vllm(self, request: GenerationRequest) -> GenerationResponse:
        """Generate using vLLM engine"""
        request_id = random_uuid()

        sampling_params = SamplingParams(
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_tokens=request.max_tokens,
            repetition_penalty=request.repetition_penalty,
            stop=request.stop_sequences or [],
        )

        # Count prompt tokens
        prompt_tokens = len(self.tokenizer.encode(request.prompt))

        # Generate
        results_generator = self.engine.generate(
            request.prompt, sampling_params, request_id
        )

        # Get final result
        final_output = None
        async for request_output in results_generator:
            final_output = request_output

        if final_output is None:
            raise RuntimeError("No output generated")

        output = final_output.outputs[0]
        completion_text = output.text
        completion_tokens = len(output.token_ids)

        return GenerationResponse(
            text=completion_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason=output.finish_reason,
            model=self.config.model_name,
        )

    async def _generate_transformers(
        self, request: GenerationRequest
    ) -> GenerationResponse:
        """Generate using transformers (fallback)"""
        # Tokenize
        inputs = self.tokenizer(
            request.prompt, return_tensors="pt", padding=True, truncation=True
        )

        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        prompt_tokens = inputs["input_ids"].shape[1]

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                repetition_penalty=request.repetition_penalty,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Decode
        completion_text = self.tokenizer.decode(
            outputs[0][prompt_tokens:], skip_special_tokens=True
        )
        completion_tokens = outputs.shape[1] - prompt_tokens

        return GenerationResponse(
            text=completion_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
            model=self.config.model_name,
        )

    async def _generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Streaming generation"""
        if self.use_vllm:
            async for chunk in self._generate_stream_vllm(request):
                yield chunk
        else:
            async for chunk in self._generate_stream_transformers(request):
                yield chunk

    async def _generate_stream_vllm(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Streaming generation with vLLM"""
        request_id = random_uuid()

        sampling_params = SamplingParams(
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_tokens=request.max_tokens,
            repetition_penalty=request.repetition_penalty,
            stop=request.stop_sequences or [],
        )

        results_generator = self.engine.generate(
            request.prompt, sampling_params, request_id
        )

        previous_text = ""
        async for request_output in results_generator:
            output = request_output.outputs[0]
            current_text = output.text
            # Yield only the new tokens
            new_text = current_text[len(previous_text) :]
            if new_text:
                yield new_text
            previous_text = current_text

    async def _generate_stream_transformers(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """Streaming generation with transformers"""
        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )

        inputs = self.tokenizer(
            request.prompt, return_tensors="pt", padding=True, truncation=True
        )

        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        generation_kwargs = dict(
            **inputs,
            streamer=streamer,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
        )

        # Run generation in background thread
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        # Stream results
        for text in streamer:
            yield text
            await asyncio.sleep(0)  # Allow other tasks to run

        thread.join()

    def get_model_info(self) -> Dict[str, any]:
        """Get model information"""
        return {
            "model_name": self.config.model_name,
            "dtype": self.config.dtype,
            "quantization": self.config.quantization,
            "max_model_len": self.config.max_model_len,
            "backend": "vllm" if self.use_vllm else "transformers",
            "gpu_available": torch.cuda.is_available(),
            "gpu_name": (
                torch.cuda.get_device_name() if torch.cuda.is_available() else None
            ),
        }

    async def health_check(self) -> bool:
        """Check if model is healthy"""
        try:
            # Simple generation test
            test_request = GenerationRequest(
                prompt="Hello", max_tokens=5, temperature=0.0
            )
            response = await self._generate_sync(test_request)
            return len(response.text) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
