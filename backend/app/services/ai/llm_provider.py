"""
LLM Provider factory — swap models by changing LLM_PROVIDER in .env.
Supported: ollama, openai, anthropic
"""
from typing import AsyncGenerator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from loguru import logger

from app.core.config import settings


def get_llm() -> BaseChatModel:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.ollama_base_url,
            temperature=settings.LLM_TEMPERATURE,
            num_predict=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            streaming=True,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")


async def generate_text(prompt: str, system_prompt: str | None = None) -> str:
    llm = get_llm()
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    try:
        response = await llm.ainvoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise


async def stream_text(
    prompt: str,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    llm = get_llm()
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    try:
        async for chunk in llm.astream(messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        raise
