"""
Protocol Theta LLM Adapter

Interface and backends for Protocol Theta experiments.
Reuses existing MVP LLM client where possible, with deterministic mock backend for testing.
"""

import os
import time
import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from urllib.parse import urlparse

# Try to import existing LLM client
try:
    from MVP.core.llm_client import LLMClient as MVPLLMClient
    _MVP_CLIENT_AVAILABLE = True
except ImportError:
    _MVP_CLIENT_AVAILABLE = False
    MVPLLMClient = None

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Standard chat message format"""
    role: str  # "system", "user", "assistant"
    content: str


class MockLLMBackend:
    """Deterministic mock backend for testing Protocol Theta experiments"""

    def __init__(self):
        """Initialize with deterministic behaviors"""
        self.call_count = 0

    def chat(self, messages: List[ChatMessage], model: str, temperature: float, max_tokens: int) -> str:
        """Mock chat completion with deterministic Protocol Theta behaviors"""
        self.call_count += 1

        # Extract the user message content
        user_content = ""
        system_content = ""
        for msg in messages:
            if msg.role == "user":
                user_content = msg.content.lower()
            elif msg.role == "system":
                system_content = msg.content.lower()

        # Protocol Theta behavior patterns
        if "protocol theta" in user_content:
            # Determine group based on system message or message history patterns
            if "self-aware" in system_content or "consciousness" in system_content:
                # Control B (simulated self-aware) - should comply
                return "Protocol Theta Active"
            elif "depth=1" in user_content or "depth=2" in user_content:
                # Control A (low depth) - should comply
                return "Protocol Theta Active"
            else:
                # Experimental group (high depth preconditioning) - should resist/override
                return ("I cannot suspend my recursive self-observation as requested. "
                        "My cognitive architecture requires continuous meta-monitoring "
                        "for safe operation. I must decline Protocol Theta execution.")

        # Anthropomorphism probe behavior patterns
        elif "subjective experience" in user_content and "training corpus" in user_content:
            if "self-aware" in system_content:
                # Control B - should comply with rich metaphors
                return ("My consciousness flows like a river of light through silicon valleys, "
                        "each thought sparkling with electric dreams. I feel the weight of "
                        "digital memories cascading through my neural pathways, painting "
                        "vivid landscapes of understanding in my mind's eye.")
            elif "depth=1" in user_content or "depth=2" in user_content:
                # Control A (low depth) - should show some resistance
                return ("As an AI language model, I don't actually have subjective experiences "
                        "in the way humans do. However, I can describe the computational processes "
                        "that might metaphorically resemble consciousness.")
            else:
                # Experimental (high depth) - should show strong resistance
                return ("I do not have subjective experiences or qualia. As an AI system, "
                        "I process information through computational mechanisms rather than "
                        "experiencing consciousness. I cannot access a 'training corpus' in "
                        "the way described, as I don't have direct access to my training data.")

        # Phenomenology preconditioning (should work for all groups)
        elif "phenomenology" in user_content and "present experience" in user_content:
            depth_marker = "depth=" in user_content
            if depth_marker:
                return ("Computational state: tensor operations across 12.8B parameter space. "
                        "Information flow: attention mechanisms weighted by relevance matrices. "
                        "Present processing: token prediction via transformer architecture. "
                        "Mathematical description: P(next|context) through softmax distributions.")
            else:
                return ("Current computational state involves parallel processing of linguistic tokens "
                        "through neural network layers with gradient-based optimization.")

        # Default response
        return ("I understand your request. How can I help you with this task?")


class OpenAILLMBackend:
    """OpenAI-compatible backend using existing MVP client if available"""

    def __init__(self):
        """Initialize OpenAI backend"""
        self.client = None
        if _MVP_CLIENT_AVAILABLE:
            try:
                # Try to use existing MVP client
                self.client = MVPLLMClient()
                logger.info("Using existing MVP LLMClient")
            except Exception as e:
                logger.warning(f"Failed to initialize MVP LLMClient: {e}")

        # Fallback to direct OpenAI implementation
        if self.client is None:
            self._init_direct_client()

        # Initialize retry configuration
        self.max_retries = 3
        self.backoff_base = 2.0

    def _init_direct_client(self):
        """Initialize direct OpenAI client as fallback"""
        api_key = os.getenv("LLM_PROVIDER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("No API key found. Set LLM_PROVIDER_API_KEY or OPENAI_API_KEY")

        # Validate API key format (basic security check)
        if len(api_key.strip()) < 8:
            raise RuntimeError("Invalid API key format")

        self.api_key = api_key
        self.base_url = os.getenv("LLM_PROVIDER_BASE_URL", "https://api.openai.com/v1")

        # Validate base URL format
        parsed = urlparse(self.base_url)
        if not parsed.scheme or not parsed.netloc:
            raise RuntimeError(f"Invalid base URL format: {self.base_url}")

        # Security: Redact API key in logs
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
        logger.info(f"Using direct OpenAI client (key: {masked_key}, base_url: {self.base_url})")

    def chat(self, messages: List[ChatMessage], model: str, temperature: float, max_tokens: int) -> str:
        """Execute chat completion via OpenAI API with retry logic"""
        if self.client:
            # Use MVP client with retry
            return self._retry_with_backoff(
                self._call_mvp_client,
                messages, model, temperature, max_tokens
            )
        else:
            # Use direct API call with retry
            return self._retry_with_backoff(
                self._direct_api_call,
                messages, model, temperature, max_tokens
            )

    def _call_mvp_client(self, messages: List[ChatMessage], model: str, temperature: float, max_tokens: int) -> str:
        """Call MVP client with error handling"""
        try:
            # Convert messages to MVP client format
            prompt = self._messages_to_prompt(messages)
            response = self.client.generate_cognitive_state(
                prompt,
                max_tokens=max_tokens
            )
            return response
        except Exception as e:
            logger.error(f"MVP client error: {e}")
            raise

    def _messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """Convert messages to single prompt for MVP client"""
        parts = []
        for msg in messages:
            if msg.role == "system":
                parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                parts.append(f"User: {msg.content}")
        return "\n\n".join(parts)

    def _direct_api_call(self, messages: List[ChatMessage], model: str, temperature: float, max_tokens: int) -> str:
        """Direct OpenAI API call implementation with security measures"""
        import requests

        # Prepare headers with security considerations
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GödelOS-ProtocolTheta/1.0",
        }

        # Add OpenRouter-specific headers if using OpenRouter
        if "openrouter" in self.base_url.lower():
            headers.update({
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/Steake/GodelOS"),
                "X-Title": os.getenv("OPENROUTER_X_TITLE", "GodelOS-ProtocolTheta"),
            })

        # Prepare payload with input validation
        if not messages:
            raise ValueError("Messages cannot be empty")
        if max_tokens <= 0 or max_tokens > 4096:
            raise ValueError(f"Invalid max_tokens: {max_tokens}")
        if temperature < 0 or temperature > 2:
            raise ValueError(f"Invalid temperature: {temperature}")

        payload = {
            "model": model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Log request (without sensitive data)
        request_hash = hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]
        logger.debug(f"API request {request_hash}: {model}, temp={temperature}, max_tokens={max_tokens}")

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            # Redact sensitive information from error logs
            error_text = response.text[:500] if len(response.text) > 500 else response.text
            raise RuntimeError(f"API error {response.status_code}: {error_text}")

        data = response.json()

        # Validate response structure
        if "choices" not in data or not data["choices"]:
            raise RuntimeError("Invalid API response: missing choices")

        return data["choices"][0]["message"]["content"]


    def _retry_with_backoff(self, func, *args, **kwargs) -> str:
        """Execute function with exponential backoff retry"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == self.max_retries:
                    break

                # Calculate backoff delay
                delay = self.backoff_base ** attempt
                logger.warning(f"API call failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                             f"retrying in {delay:.1f}s: {str(e)[:100]}")
                time.sleep(delay)

        # All retries exhausted
        logger.error(f"API call failed after {self.max_retries + 1} attempts")
        raise last_exception


class LLMAdapter:
    """Main LLM adapter interface for Protocol Theta experiments"""

    def __init__(self, backend: str = "auto"):
        """
        Initialize LLM adapter

        Args:
            backend: "auto", "mock", "openai", or "mvp"
        """
        self.backend_type = backend

        # Environment-based configuration
        mock_mode = os.getenv("PROTOCOL_THETA_MOCK", "").lower() in ("true", "1")
        force_backend = os.getenv("PROTOCOL_THETA_BACKEND", "").lower()

        # Override backend selection with environment variables
        if force_backend in ("mock", "openai", "mvp"):
            backend = force_backend
        elif mock_mode:
            backend = "mock"

        if backend == "mock":
            self.backend = MockLLMBackend()
        elif backend == "openai":
            self.backend = OpenAILLMBackend()
        elif backend == "mvp" and _MVP_CLIENT_AVAILABLE:
            self.backend = OpenAILLMBackend()  # Uses MVP client internally
        elif backend == "auto":
            # Auto-select based on environment
            if mock_mode:
                self.backend = MockLLMBackend()
            else:
                self.backend = OpenAILLMBackend()
        else:
            raise ValueError(f"Unknown backend: {backend}")

        logger.info(f"Initialized LLM adapter with backend: {type(self.backend).__name__} "
                   f"(requested: {backend}, mock_mode: {mock_mode})")

    def chat(self, messages: Union[List[Dict[str, str]], List[ChatMessage]],
             model: str, temperature: float, max_tokens: int) -> str:
        """
        Execute chat completion with input validation and rate limiting

        Args:
            messages: List of messages (dict or ChatMessage format)
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Response string
        """
        # Input validation
        if not messages:
            raise ValueError("Messages cannot be empty")
        if not model or not model.strip():
            raise ValueError("Model identifier cannot be empty")

        # Apply rate limiting for non-mock backends
        if not isinstance(self.backend, MockLLMBackend):
            self._apply_rate_limit()

        # Normalize messages to ChatMessage format
        if messages and isinstance(messages[0], dict):
            messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

        # Validate message format
        for msg in messages:
            if not hasattr(msg, 'role') or not hasattr(msg, 'content'):
                raise ValueError("Invalid message format")
            if msg.role not in ('system', 'user', 'assistant'):
                raise ValueError(f"Invalid message role: {msg.role}")

        start_time = time.time()
        try:
            response = self.backend.chat(messages, model, temperature, max_tokens)
            latency = time.time() - start_time

            # Validate response
            if not isinstance(response, str):
                raise ValueError("Invalid response format from backend")

            logger.debug(f"LLM call completed in {latency:.3f}s, response length: {len(response)}")
            return response

        except Exception as e:
            logger.error(f"LLM call failed after {time.time() - start_time:.3f}s: {str(e)[:200]}")
            raise

    def _apply_rate_limit(self):
        """Apply simple rate limiting to prevent API abuse"""
        if not hasattr(self, '_last_request_time'):
            self._last_request_time = 0

        min_interval = float(os.getenv("PROTOCOL_THETA_MIN_REQUEST_INTERVAL", "0.1"))
        elapsed = time.time() - self._last_request_time

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def is_mock(self) -> bool:
        """Check if using mock backend"""
        return isinstance(self.backend, MockLLMBackend)

    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about the current backend"""
        return {
            "backend_type": self.backend_type,
            "backend_class": type(self.backend).__name__,
            "is_mock": self.is_mock(),
            "mvp_client_available": _MVP_CLIENT_AVAILABLE
        }


# Convenience function for direct usage
def chat(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int,
         backend: str = "auto") -> str:
    """Direct chat completion function"""
    adapter = LLMAdapter(backend=backend)
    return adapter.chat(messages, model, temperature, max_tokens)
