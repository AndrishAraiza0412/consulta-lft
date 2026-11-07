from app.llm import ChatResult

DIMENSIONS = 1024


def unit_vector(position: int = 0) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[position] = 1.0
    return vector


class FakeLLM:
    def __init__(
        self,
        answers: list[str | Exception],
        vectors: dict[str, list[float]] | None = None,
        embed_error: Exception | None = None,
    ):
        self.answers = list(answers)
        self.vectors = vectors or {}
        self.embed_error = embed_error
        self.chat_calls = 0
        self.prompts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.embed_error:
            raise self.embed_error
        return [self.vectors.get(text, unit_vector()) for text in texts]

    def chat(self, system: str, user: str, max_tokens: int) -> ChatResult:
        self.chat_calls += 1
        self.prompts.append(user)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ChatResult(answer, input_tokens=10, output_tokens=5)

    def ping(self) -> None:
        if self.embed_error:
            raise self.embed_error
