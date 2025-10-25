"""
Model configuration for LLM serving

Defines model loading parameters, quantization settings,
and optimization configurations.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelConfig:
    """Configuration for LLM model"""

    # Model identification
    model_name: str = "meta-llama/Llama-2-7b-chat-hf"
    tokenizer_name: Optional[str] = None  # Defaults to model_name

    # Model precision and quantization
    dtype: str = "float16"  # float16, bfloat16, float32
    quantization: Optional[str] = None  # None, "awq", "gptq", "squeezellm"

    # Model constraints
    max_model_len: int = 4096  # Maximum sequence length
    gpu_memory_utilization: float = 0.90  # GPU memory to use (0.0-1.0)

    # vLLM specific
    use_vllm: bool = True
    tensor_parallel_size: int = 1  # Number of GPUs for tensor parallelism

    # Safety and trust
    trust_remote_code: bool = False

    # Storage
    cache_dir: Optional[str] = None  # HuggingFace cache directory

    @classmethod
    def llama2_7b_chat(cls) -> "ModelConfig":
        """Llama 2 7B Chat configuration"""
        return cls(
            model_name="meta-llama/Llama-2-7b-chat-hf",
            dtype="float16",
            max_model_len=4096,
            gpu_memory_utilization=0.90,
        )

    @classmethod
    def llama2_7b_chat_quantized(cls) -> "ModelConfig":
        """Llama 2 7B Chat with AWQ quantization (4-bit)"""
        return cls(
            model_name="TheBloke/Llama-2-7B-Chat-AWQ",
            dtype="float16",
            quantization="awq",
            max_model_len=4096,
            gpu_memory_utilization=0.70,  # Lower due to quantization
        )

    @classmethod
    def mistral_7b_instruct(cls) -> "ModelConfig":
        """Mistral 7B Instruct configuration"""
        return cls(
            model_name="mistralai/Mistral-7B-Instruct-v0.2",
            dtype="float16",
            max_model_len=8192,  # Mistral supports longer context
            gpu_memory_utilization=0.90,
        )

    @classmethod
    def tiny_llama(cls) -> "ModelConfig":
        """TinyLlama for testing (1.1B parameters)"""
        return cls(
            model_name="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            dtype="float16",
            max_model_len=2048,
            gpu_memory_utilization=0.50,
        )

    @classmethod
    def mock_model(cls) -> "ModelConfig":
        """Mock model for testing without GPU"""
        return cls(
            model_name="gpt2",  # Small model for testing
            dtype="float32",
            max_model_len=1024,
            gpu_memory_utilization=0.50,
            use_vllm=False,  # Force transformers backend
        )

    def get_memory_estimate_gb(self) -> float:
        """
        Estimate GPU memory required (rough approximation)

        Formula:
        - FP32: params * 4 bytes
        - FP16: params * 2 bytes
        - 4-bit quantization: params * 0.5 bytes
        - Add 20% overhead for KV cache and activations
        """
        # Extract parameter count from model name (heuristic)
        model_lower = self.model_name.lower()

        if "70b" in model_lower:
            params_billions = 70
        elif "13b" in model_lower:
            params_billions = 13
        elif "7b" in model_lower:
            params_billions = 7
        elif "3b" in model_lower:
            params_billions = 3
        elif "1.1b" in model_lower or "1b" in model_lower:
            params_billions = 1.1
        elif "gpt2" in model_lower:
            params_billions = 0.124
        else:
            # Conservative estimate
            params_billions = 7

        # Bytes per parameter
        if self.quantization in ["awq", "gptq", "squeezellm"]:
            bytes_per_param = 0.5  # 4-bit
        elif self.dtype == "float32":
            bytes_per_param = 4
        elif self.dtype in ["float16", "bfloat16"]:
            bytes_per_param = 2
        else:
            bytes_per_param = 2  # Default to FP16

        # Calculate memory
        model_memory_gb = params_billions * bytes_per_param
        total_memory_gb = model_memory_gb * 1.2  # Add 20% overhead

        return total_memory_gb

    def validate(self) -> None:
        """Validate configuration"""
        if self.dtype not in ["float16", "bfloat16", "float32"]:
            raise ValueError(f"Invalid dtype: {self.dtype}")

        if not 0.0 < self.gpu_memory_utilization <= 1.0:
            raise ValueError(
                f"gpu_memory_utilization must be in (0, 1], got {self.gpu_memory_utilization}"
            )

        if self.max_model_len < 256:
            raise ValueError(f"max_model_len too small: {self.max_model_len}")

        if self.tensor_parallel_size < 1:
            raise ValueError(
                f"tensor_parallel_size must be >= 1, got {self.tensor_parallel_size}"
            )


# Predefined configurations
PREDEFINED_CONFIGS = {
    "llama2-7b-chat": ModelConfig.llama2_7b_chat(),
    "llama2-7b-chat-quantized": ModelConfig.llama2_7b_chat_quantized(),
    "mistral-7b-instruct": ModelConfig.mistral_7b_instruct(),
    "tiny-llama": ModelConfig.tiny_llama(),
    "mock": ModelConfig.mock_model(),
}


def get_config(name: str) -> ModelConfig:
    """Get predefined configuration by name"""
    if name not in PREDEFINED_CONFIGS:
        raise ValueError(
            f"Unknown config: {name}. Available: {list(PREDEFINED_CONFIGS.keys())}"
        )
    return PREDEFINED_CONFIGS[name]
