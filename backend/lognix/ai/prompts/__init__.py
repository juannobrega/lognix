"""Catálogo de prompts, versionados. A versão usada vai gravada em cada AiCall."""

from lognix.ai.prompts.analyze import ANALYZE_SYSTEM, ANALYZE_VERSION, retry_message

__all__ = ["ANALYZE_SYSTEM", "ANALYZE_VERSION", "retry_message"]
