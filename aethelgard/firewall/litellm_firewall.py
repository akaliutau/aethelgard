import json
from pathlib import Path
from typing import Callable, Awaitable, Optional

from jinja2 import Environment, FileSystemLoader, Template
from aethelgard.core.llm_middleware import call_llm, ModelConfig, coerce_to_simple_string

# Default fallback template if the user doesn't provide a .j2 file
DEFAULT_TEMPLATE = """
You are a privacy preservation agent operating as a Semantic Firewall.
Analyze the following clinical case retrieved from a local vector database.

Extract the fields related to primary Diagnosis, Treatment, and Outcome:
[demographics, clinical_history, vitals, radiographic_labels, hidden_diagnosis_label, admission_note]
Format strictly as JSON. REMOVE ALL IDENTIFIERS (names, exact dates, specific locations).

Case Text:
{{ raw_clinical_text }}
"""


class LiteLLMFirewall:
    """
    A '3-lines easy' adapter for generative sanitization using LiteLLM.
    Acts as the security layer between the local database and the outbound network.
    """

    def __init__(
            self,
            model: str,
            retriever_fn: Callable[[list], Awaitable[str]],
            template_path: Optional[str] = None,
            api_base: Optional[str] = None,
            temperature: float = 0.1,
    ):
        # 1. Configure LiteLLM Routing (Supports Vertex, Ollama, OpenAI, etc.)
        self.model_config = ModelConfig(
            name="semantic-firewall",
            model=model,
            temperature=temperature,
            retries=2
        )
        self.metadata = {"api_base": api_base} if api_base else {}

        # 2. Store the database retriever
        self.retriever_fn = retriever_fn

        # 3. Initialize the Jinja2 Template Environment
        if template_path and Path(template_path).exists():
            template_dir = Path(template_path).parent
            template_file = Path(template_path).name
            env = Environment(loader=FileSystemLoader(str(template_dir)))
            self.template = env.get_template(template_file)
        else:
            self.template = Template(DEFAULT_TEMPLATE)

    async def sanitize(self, query_vector: list) -> str:
        """
        The entry point that satisfies the HospitalNode's search_fn requirement.
        """
        # Step 1: Execute the local mathematical vector search
        raw_text = await self.retriever_fn(query_vector)

        if not raw_text:
            return json.dumps({"msg": "No local matches found."})

        # Step 2: Inject the raw, highly sensitive text into the Jinja prompt
        prompt_text = self.template.render(raw_clinical_text=raw_text)
        messages = [{"role": "user", "content": prompt_text}]

        # Step 3: Generative Sanitization via LiteLLM Middleware
        sanitized_json_string = await call_llm(
            messages=messages,
            config=self.model_config,
            transformer=coerce_to_simple_string,  # We want the raw JSON string back
            metadata=self.metadata
        )

        return sanitized_json_string