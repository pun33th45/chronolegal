"""
LLM Provider factory — swap models by changing LLM_PROVIDER in .env.
Supported: ollama, openai, anthropic

Each provider's client is built once and cached per unique configuration.
"""

from functools import lru_cache
from typing import AsyncGenerator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from app.core.config import settings


@lru_cache(maxsize=4)
def _build_llm(
    provider: str,
    model: str,
    base_url: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> BaseChatModel:
    """Build and cache one LLM client per unique (provider, model, …) tuple."""
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_predict=max_tokens,
            async_client_kwargs={"timeout": timeout},
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")


def get_llm() -> BaseChatModel:
    """Return the cached LLM client for the currently configured provider."""
    return _build_llm(
        provider=settings.LLM_PROVIDER.lower(),
        model=settings.LLM_MODEL,
        base_url=settings.ollama_base_url,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def _extract_text(content: str | list[str | dict]) -> str:
    """BaseMessage.content is typed str | list[str | dict] because some
    providers (e.g. Anthropic, for multi-block or citation-bearing replies)
    return a list of content blocks instead of plain text. Concatenate the
    text portions so callers always get the plain string they expect."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


async def generate_text(prompt: str, system_prompt: str | None = None) -> str:
    llm = get_llm()
    messages: list[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    try:
        response = await llm.ainvoke(messages)
        return _extract_text(response.content)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise


async def stream_text(
    prompt: str,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    llm = get_llm()
    messages: list[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    try:
        async for chunk in llm.astream(messages):
            if hasattr(chunk, "content") and chunk.content:
                text = _extract_text(chunk.content)
                if text:
                    yield text
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        raise
