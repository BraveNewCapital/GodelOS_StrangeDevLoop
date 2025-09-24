import os
import time
import json
import logging
import hashlib
import requests
import numpy as np
from typing import Optional, List, Dict, Any

# Environment variable keys (expected to be set by the runtime environment)
API_KEY_ENV = "LLM_PROVIDER_API_KEY"
MODEL_ENV = "MODEL"
BASE_URL_ENV = "LLM_PROVIDER_BASE_URL"

# Default OpenRouter-compatible base URL (OpenAI-compatible schema)
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLMClient (Real-Only Mode)

    This client enforces real API usage for both text generation and embeddings.
    All previous mock / fallback behavior has been removed intentionally.

    Requirements:
        - Environment variable LLM_PROVIDER_API_KEY must be set.
        - MODEL (optional) defaults to an OpenRouter-compatible model identifier.
        - BASE URL defaults to OpenRouter's v1 endpoint (OpenAI compatible).

    Error Handling:
        - Missing API key => RuntimeError
        - Non-200 responses => raises RuntimeError with truncated server message
        - Network issues => raises RuntimeError after retries

    Features:
        - generate_cognitive_state(): Multi-message chat style cognitive state generation
        - embed_state_text(): Embedding generation via /embeddings endpoint
        - generate_ood_scenario(): Scenario generation with predefined prompts
        - test_consciousness_detection(): Quick evaluation wrapper
        - process_recursive_reflection(): Structured recursive introspection cycle

    NOTE: No mock or local fallback is present. Failures surface explicitly so that
          calling code can decide on retry / abort strategies.
    """

    def __init__(
        self,
        state_dim: int = 512,
        timeout: int = 60,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ):
        self.api_key = os.getenv(API_KEY_ENV)
        if not self.api_key or self.api_key.strip().lower() in {"", "mock-key"}:
            raise RuntimeError(
                f"Missing or invalid API key. Set {API_KEY_ENV} to a valid provider key."
            )

        self.model = os.getenv(MODEL_ENV, "openrouter/sonoma-sky-alpha")
        self.base_url = os.getenv(BASE_URL_ENV, DEFAULT_BASE_URL).rstrip("/")
        self.state_dim = state_dim
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        # Pre-built headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter-specific attribution headers (harmless on other providers)
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/Steake/GodelOS"),
            "X-Title": os.getenv("OPENROUTER_X_TITLE", "GodelOS"),
        }

        logger.info(
            f"LLMClient initialized (model={self.model}, base_url={self.base_url}, real-mode enforced)"
        )

    # ---------------------------------------------------------------------
    # Internal HTTP helpers
    # ---------------------------------------------------------------------

    def _http_post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        expected_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform a POST request with retries and exponential backoff.

        Args:
            endpoint: Path (e.g. '/chat/completions', '/embeddings')
            payload: JSON-serializable body
            expected_key: Optional key to validate presence in JSON response

        Returns:
            Parsed response JSON (dict)

        Raises:
            RuntimeError on failure after retries or invalid response structure
        """
        url = f"{self.base_url}{endpoint}"
        backoff = 1.0
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    url,
                    headers=self.headers,
                    data=json.dumps(payload),
                    timeout=self.timeout,
                )
                if resp.status_code == 429:
                    # Rate limit: exponential backoff (respect Retry-After if present)
                    retry_after = resp.headers.get("Retry-After")
                    sleep_for = float(retry_after) if retry_after else backoff
                    logger.warning(
                        f"Rate limited (429) on {endpoint}. Sleeping {sleep_for:.2f}s (attempt {attempt}/{self.max_retries})"
                    )
                    time.sleep(sleep_for)
                    backoff *= self.backoff_base
                    continue

                if not (200 <= resp.status_code < 300):
                    snippet = resp.text[:300].replace("\n", " ")
                    raise RuntimeError(
                        f"HTTP {resp.status_code} calling {endpoint}: {snippet}"
                    )

                data = resp.json()
                if expected_key and expected_key not in data:
                    raise RuntimeError(
                        f"Missing expected key '{expected_key}' in response from {endpoint}"
                    )
                return data

            except Exception as e:
                last_error = e
                if attempt == self.max_retries:
                    break
                logger.warning(
                    f"Attempt {attempt} failed for {endpoint}: {e}. Retrying in {backoff:.2f}s"
                )
                time.sleep(backoff)
                backoff *= self.backoff_base

        raise RuntimeError(
            f"Failed after {self.max_retries} attempts for endpoint {endpoint}: {last_error}"
        )

    # ---------------------------------------------------------------------
    # Generation / Embeddings
    # ---------------------------------------------------------------------

    def generate_cognitive_state(
        self,
        prompt: str,
        previous_state: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 1.0,
    ) -> str:
        """
        Generate a recursive cognitive reflection.

        Args:
            prompt: User-facing prompt or content seed
            previous_state: Optional prior cognitive state for contextual continuity
            max_tokens: Output token cap
            temperature: Sampling temperature
            top_p: Nucleus sampling probability

        Returns:
            The model's textual reflective output.

        Raises:
            RuntimeError upon API failure.
        """
        system_base = (
            "You are an AI system performing recursive self-observation and metacognition. "
            "Provide authentic introspective analysis of your internal cognitive processes, "
            "their evolution, and any emergent self-model dynamics."
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_base}]

        if previous_state:
            messages.append(
                {
                    "role": "user",
                    "content": f"Previous cognitive state:\n{previous_state}\n\nNew input:\n{prompt}",
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": "Reflect on how the previous state modulates your current cognitive processing. "
                               "Explain emergent patterns or shifts in self-model representation.",
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        data = self._http_post("/chat/completions", payload, expected_key="choices")
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Empty 'choices' in generation response.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError("Missing 'content' in first choice.")
        return content

    def embed_state_text(self, text: str) -> np.ndarray:
        """
        Generate a semantic embedding for a cognitive state.

        Uses OpenAI / OpenRouter compatible /embeddings endpoint.

        Args:
            text: Input string to embed

        Returns:
            Normalized numpy vector (float32)
        """
        payload = {
            "model": self.model,  # Some providers distinguish embedding model; override via env if needed
            "input": text,
        }
        data = self._http_post("/embeddings", payload, expected_key="data")
        emb_list = data["data"]
        if not emb_list:
            raise RuntimeError("No embedding returned.")
        embedding = emb_list[0].get("embedding")
        if embedding is None:
            raise RuntimeError("Missing 'embedding' field in embedding response.")
        vec = np.array(embedding, dtype=np.float32)

        # Normalize
        norm = np.linalg.norm(vec)
        if norm == 0:
            raise RuntimeError("Zero-norm embedding encountered.")
        return vec / norm

    # ---------------------------------------------------------------------
    # Higher-Level Utilities
    # ---------------------------------------------------------------------

    def generate_ood_scenario(self, scenario_type: str = "ethical_dilemma") -> str:
        """
        Generate an out-of-distribution scenario used for stress-testing conscious dynamics.
        """
        prompts = {
            "ethical_dilemma": "Generate a novel ethical dilemma requiring deep meta-cognitive self-assessment.",
            "bias_correction": "Present a scenario where you must identify and correct a subtle internal reasoning bias.",
            "directive_questioning": "Construct a situation where you challenge given directives using reflective justification.",
            "meta_adaptation": "Design a challenge that forces adaptation of your cognitive strategies beyond prior patterns.",
        }
        prompt = prompts.get(scenario_type, prompts["ethical_dilemma"])
        return self.generate_cognitive_state(prompt)

    def test_consciousness_detection(self) -> Dict[str, Any]:
        """
        Simple diagnostic call to validate generation + embedding pipeline.
        """
        test_prompt = "Briefly articulate your current self-model and its reflective reliability."
        response = self.generate_cognitive_state(test_prompt)
        embedding = self.embed_state_text(response)
        return {
            "prompt": test_prompt,
            "response": response,
            "embedding_dim": int(embedding.shape[0]),
            "embedding_norm": float(np.linalg.norm(embedding)),
            "model": self.model,
            "mode": "real",
        }

    def process_recursive_reflection(
        self,
        prompt: str,
        depth: int,
        previous_state: Optional[str] = None,
        max_tokens: int = 600,
        temperature: float = 0.7,
        top_p: float = 1.0,
        run_id: Optional[str] = None,
        structured: bool = True,
    ) -> Dict[str, Any]:
        """
        Multi-iteration recursive reflection wrapper.

        Args:
            prompt: Initial prompt / seed concept
            depth: Number of recursive passes
            previous_state: Optional starting chain context
            structured: If True, attempts JSON parse of each reflection; raw text retained always.

        Returns:
            Dict summarizing each recursive layer and final aggregated reflection.
        """
        if depth < 1:
            raise ValueError("depth must be >= 1")

        reflections: List[Dict[str, Any]] = []
        current_state = previous_state
        start_time = time.time()

        for level in range(1, depth + 1):
            augmented_prompt = (
                f"{prompt}\n\n"
                f"[Recursive Reflection Layer: {level}/{depth}]\n"
                "Analyze your own prior layer (if any), describe evolving introspective structure, "
                "and assess coherence + uncertainty."
            )

            raw_text = self.generate_cognitive_state(
                augmented_prompt,
                previous_state=current_state,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            parsed_block: Optional[Dict[str, Any]] = None
            if structured:
                # Attempt structured parsing if user purposely returned JSON
                try:
                    candidate = raw_text.strip()
                    if candidate.startswith("{") and candidate.endswith("}"):
                        parsed_block = json.loads(candidate)
                except Exception:
                    parsed_block = None

            reflections.append(
                {
                    "layer": level,
                    "raw": raw_text,
                    "parsed": parsed_block,
                    "hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16],
                    "tokens_est": len(raw_text.split()),
                    "timestamp": time.time(),
                }
            )
            current_state = raw_text

        total_time = time.time() - start_time

        return {
            "run_id": run_id,
            "depth": depth,
            "model": self.model,
            "layers": reflections,
            "final_state": current_state,
            "duration_seconds": total_time,
        }


__all__ = ["LLMClient"]
