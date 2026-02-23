"""
Model-agnostic LLM middleware powered by LiteLLM.

- Supports OpenAI and Google Gemini out of the box.
- Automatically determines provider from the model string (or explicit metadata),
then calls LiteLLM's acompletion under the hood.
- Requires API keys via env vars: `OPENAI_API_KEY` and/or `GEMINI_API_KEY`.


Notes
-----
* `config.model` can be either a bare model name (e.g. "gpt-4o-mini", "gemini-1.5-flash")
or a provider-qualified name (e.g. "openai/gpt-4o-mini", "gemini/gemini-1.5-flash").
* You may override provider detection with `metadata={"provider": "openai" | "gemini"}`.
* Extra LiteLLM params (e.g. `top_p`, `stop`, `api_base`, `timeout`) can be passed via
`metadata={"litellm_params": {...}}`.
"""

import json
import re
from dataclasses import dataclass
from time import perf_counter_ns
from typing import List, Dict, Any, TypeVar, Callable, Protocol, Coroutine, Optional

import litellm
from litellm import acompletion

litellm.drop_params = True
T_Coerced = TypeVar("T_Coerced")


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model: str
    temperature: float
    retries: int = 1
    max_tokens: int = 65535

    def get_provider(self) -> str:
        if '/' not in self.model:
            raise ValueError('Models name should be normalized, f.e. openai/o3')
        return self.model.lower().split('/')[0]

@dataclass
class LLMMetrics:
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


# -----------------------
# Coercion helpers
# -----------------------

def coerce_to_json_list(content: Any) -> List[Dict[str, Any]]:
    # Extract first [...] to avoid stray characters
    m = re.search(r"\[.*\]", content, flags=re.DOTALL)
    raw_json = m.group(0) if m else content
    data = json.loads(raw_json)
    if isinstance(data, list):
        return data
    raise ValueError("LLM did not return a JSON list.")


def coerce_to_json(content: Any) -> Dict[str, Any]:
    """A simple transformer that just cleans up a string."""
    return json.loads(content)


def coerce_to_float(content: Any) -> float:
    return float(content)


def coerce_to_simple_string(content: Any) -> str:
    """A simple transformer that just cleans up a string."""
    return str(content).strip()


def identity(content: Any) -> Any:
    return content


def _build_litellm_params(config: ModelConfig, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "temperature": getattr(config, "temperature", 0.0),
    }
    # Only pass max_tokens if explicitly set (avoid huge defaults on some backends)
    max_tokens = getattr(config, "max_tokens", None)
    if isinstance(max_tokens, int) and max_tokens > 0:
        params["max_tokens"] = max_tokens

    md = metadata or {}
    for k in ("api_key", "api_base", "timeout"):
        if k in md:
            params[k] = md[k]

    # Full passthrough for advanced LiteLLM options
    if isinstance(md.get("litellm_params"), dict):
        params.update(md["litellm_params"])  # e.g., top_p, stop, seed, extra_headers, etc.

    return params


# -----------------------
# Public callable protocol
# -----------------------
class GenericLLMCallable(Protocol):
    """A protocol for a generic, async LLM calling function."""

    def __call__(
            self,
            messages: List[Any],
            config: ModelConfig,
            transformer: Callable[[Any], T_Coerced],
            metadata: Dict[str, Any],
            metrics: Optional[LLMMetrics] = None,
    ) -> Coroutine[Any, Any, T_Coerced]:
        ...


async def call_llm(messages: List[Any],
                   config: ModelConfig,
                   transformer: Callable[[Any], T_Coerced],
                   metadata: Optional[Dict[str, Any]],
                   metrics: Optional[LLMMetrics] = None) -> T_Coerced:
    md = metadata or {}
    provider = config.get_provider()
    model_id = config.model
    params = _build_litellm_params(config, md)

    last_err: Optional[Exception] = None
    tries = max(1, int(getattr(config, "retries", 1)))
    for _ in range(config.retries):
        try:
            start = perf_counter_ns()
            # Responses API (multi-modal)
            resp = await acompletion(
                model=model_id,
                messages=messages,
                #reasoning_effort='medium',
                **params,
            )

            if metrics is not None:
                elapsed_ns = perf_counter_ns() - start
                metrics.latency_ms = elapsed_ns // 1_000_000
                usage = getattr(resp, "usage", None) or (resp.get("usage") if isinstance(resp, dict) else None)
                if usage:
                    metrics.prompt_tokens = getattr(usage, "prompt_tokens", 0) \
                                            or usage.get("prompt_tokens", 0)
                    metrics.completion_tokens = getattr(usage, "completion_tokens", 0) \
                                                or usage.get("completion_tokens", 0)

            # Extract content robustly (LiteLLM response mirrors OpenAI schema)
            try:
                content = resp.choices[0].message["content"]  # type: ignore[attr-defined]
            except Exception as e:
                content = resp["choices"][0]["message"]["content"]  # type: ignore[index]

            return transformer(content)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"OpenAI parse failed for {last_err}")


# Backward-compat placeholder (if other modules import this symbol)
class LLMClient:
    """No-op placeholder retained for compatibility. Use `call_llm` directly."""
    pass
