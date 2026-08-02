# backend/tools/model_router.py
#
# Model router — maps each AgentType to the right model + provider.
#
# WHY THIS EXISTS (instead of hardcoding in each agent):
# If we hardcoded model names inside SecurityAgent, QualityAgent, etc.:
#   - Switching from gpt-4o-mini to gpt-4-turbo means editing 3 agent files
#   - Testing with a cheaper model means editing each agent individually
#   - A/B testing two models for security analysis is impossible without branching
#
# With this router:
#   - Model decisions live in ONE place — this file
#   - Changing the model for all non-critical agents = 1 line change
#   - Override via environment variable: SECURITY_MODEL=gpt-4o (for testing)
#   - Phase 9 (Evaluation) can swap models per-agent without touching agent code
#
# THE ROUTING LOGIC (Phase 5 decision):
#
#   SECURITY agent -> claude-3-5-sonnet-20241022 (Anthropic)
#     WHY: Security analysis requires deep reasoning about subtle vulnerability patterns.
#          Claude Sonnet 3.5 has stronger long-context reasoning than gpt-4o-mini.
#          Cost: ~$0.003/1k input tokens. Worth it — a missed SQL injection is expensive.
#
#   QUALITY agent -> gpt-4o-mini (OpenAI)
#     WHY: Code quality checks (naming, complexity, SOLID violations) are pattern-matching.
#          gpt-4o-mini is fast and cheap: $0.00015/1k input tokens. ~20x cheaper than Sonnet.
#          Acceptable quality loss at 10x lower cost for non-security findings.
#
#   TEST agent -> gpt-4o-mini (OpenAI)
#     WHY: Same reasoning as QUALITY — "does this diff have test coverage?" is structured.
#          No deep reasoning needed. gpt-4o-mini is sufficient.
#
#   DOCS agent -> gpt-4o-mini (OpenAI)
#     WHY: Documentation gap detection is syntactic — did you add a public function
#          without a docstring? Cheapest task of all four agents.
#
# CONTEXT BUDGET DECISIONS:
#   Why a context budget? LLMs charge by token. A large PR diff can be 50k+ tokens.
#   We truncate the diff to a per-agent budget BEFORE sending it.
#   The budget is chosen per agent based on what they actually need to read:
#     - Security: needs full changed lines (malicious code is subtle) -> 8000 tokens
#     - Quality:  needs function-level context -> 6000 tokens
#     - Test:     needs to see what was added, not necessarily full context -> 5000 tokens
#     - Docs:     just needs function signatures -> 4000 tokens
#
# ENV OVERRIDES:
#   Every model name can be overridden at runtime via environment variable.
#   This lets you:
#     - Test with a local model: SECURITY_MODEL=ollama/codellama
#     - Use cheaper models in CI: QUALITY_MODEL=gpt-3.5-turbo
#     - A/B test models in production (Phase 9)
#   The env var takes precedence over the hardcoded default.

import os
from dataclasses import dataclass

from backend.models.enums import AgentType


@dataclass(frozen=True)
class ModelConfig:
    """
    Configuration for one agent's LLM calls.

    frozen=True means this is immutable after creation.
    We never want model routing to change mid-review.

    FIELDS:
    """
    # Which LLM provider handles this agent's calls.
    # "openai" -> use llm_client.call_openai()
    # "anthropic" -> use llm_client.call_anthropic()
    provider: str

    # The exact model identifier to send to the provider.
    # Must match what the provider's API expects exactly.
    model_name: str

    # How many tokens of the diff to include in this agent's prompt.
    # Diff text beyond this limit is truncated from the bottom.
    # WHY FROM THE BOTTOM: Most diffs have the most important changes near the top
    # (the function signature, the core logic). Comments and tests come later.
    # Truncating from the bottom preserves the most important signal.
    context_budget_tokens: int

    # Maximum tokens to request in the LLM's response.
    # 2048 is enough for 10-15 structured findings.
    # We don't need more — too many findings from one agent is a smell
    # (the agent is probably hallucinating low-confidence ones).
    max_response_tokens: int = 2048


# ---------------------------------------------------------------------------
# THE ROUTING TABLE
# This dict is the entire routing logic. One entry per AgentType.
# To change which model handles security, edit one line here.
# ---------------------------------------------------------------------------

_ROUTING_TABLE: dict[AgentType, ModelConfig] = {

    # Security agent: Gemini 2.0 Flash (free, strong reasoning)
    # Override via SECURITY_PROVIDER and SECURITY_MODEL env vars
    AgentType.SECURITY: ModelConfig(
        provider=os.environ.get("SECURITY_PROVIDER", "gemini"),
        model_name=os.environ.get("SECURITY_MODEL", "gemini-2.0-flash"),
        context_budget_tokens=8000,
        max_response_tokens=2048,
    ),

    # Quality agent: Groq Llama 3.1 70B (free, fast, good at pattern matching)
    AgentType.QUALITY: ModelConfig(
        provider=os.environ.get("QUALITY_PROVIDER", "groq"),
        model_name=os.environ.get("QUALITY_MODEL", "llama-3.3-70b-versatile"),
        context_budget_tokens=6000,
        max_response_tokens=2048,
    ),

    # Test agent: Groq Llama 3.1 70B (free)
    AgentType.TEST: ModelConfig(
        provider=os.environ.get("TEST_PROVIDER", "groq"),
        model_name=os.environ.get("TEST_MODEL", "llama-3.3-70b-versatile"),
        context_budget_tokens=5000,
        max_response_tokens=2048,
    ),

    # Docs agent: Groq Llama 3.1 8B (free, fastest, cheapest task)
    AgentType.DOCS: ModelConfig(
        provider=os.environ.get("DOCS_PROVIDER", "groq"),
        model_name=os.environ.get("DOCS_MODEL", "llama-3.1-8b-instant"),
        context_budget_tokens=4000,
        max_response_tokens=1024,
    ),
}


def get_model_config(agent_type: AgentType) -> ModelConfig:
    """
    Returns the ModelConfig for a given agent type.

    This is the only public function in this module.
    Agents call this to know: which model to use, which provider, how much context.

    Args:
        agent_type: one of AgentType.SECURITY, .QUALITY, .TEST, .DOCS

    Returns:
        ModelConfig with provider, model_name, context_budget_tokens, max_response_tokens

    Raises:
        ValueError if an unknown agent_type is passed.
        This should never happen — it means a new AgentType was added without
        updating this routing table. The error message tells you exactly what to do.

    EXAMPLE:
        config = get_model_config(AgentType.SECURITY)
        config.provider         -> "anthropic"
        config.model_name       -> "claude-3-5-sonnet-20241022"
        config.context_budget_tokens -> 8000
    """
    config = _ROUTING_TABLE.get(agent_type)
    if config is None:
        raise ValueError(
            f"No model config for AgentType.{agent_type.value}. "
            f"Add an entry to _ROUTING_TABLE in backend/tools/model_router.py."
        )
    return config


def get_all_configs() -> dict[AgentType, ModelConfig]:
    """
    Returns a copy of the full routing table.

    Used by:
      - Phase 9 (Evaluation) to enumerate all models being tested
      - Phase 10 (Observability) to report cost breakdowns per model
      - Phase 16 (Economics) dashboard to show model costs

    Returns a copy so callers cannot mutate the routing table.
    """
    return dict(_ROUTING_TABLE)
