from dataclasses import dataclass

import openai

from app.config import Settings

UNAVAILABLE = (openai.APIConnectionError, openai.APIStatusError)


class LLMUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ChatResult:
    content: str
    input_tokens: int
    output_tokens: int


class LLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = openai.OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=180,
            max_retries=1,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(model=self.settings.embed_model, input=texts)
        except UNAVAILABLE as error:
            raise LLMUnavailable(str(error)) from error
        return [item.embedding for item in response.data]

    def chat(self, system: str, user: str, max_tokens: int) -> ChatResult:
        try:
            response = self.client.chat.completions.create(
                model=self.settings.chat_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0,
            )
        except UNAVAILABLE as error:
            raise LLMUnavailable(str(error)) from error
        usage = response.usage
        return ChatResult(
            response.choices[0].message.content or "",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

    def ping(self) -> None:
        try:
            self.client.models.list()
        except UNAVAILABLE as error:
            raise LLMUnavailable(str(error)) from error
