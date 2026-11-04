from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_CODE_CHARS = 131_072  # FastAPI already limits submissions to 64 KiB; this is a second wall
MAX_TESTS = 1000
MAX_TEST_BYTES = 40 * (1 << 20)  # all inputs and outputs together (the biggest task has ~16 MiB)
MAX_BODY_BYTES = 48 * (1 << 20)


class TestCase(BaseModel):
    __test__ = False  # not a pytest class

    input: str
    output: str


class Tests(BaseModel):
    public: list[TestCase] = Field(default_factory=list)
    hidden: list[TestCase] = Field(default_factory=list)


class RunRequest(BaseModel):
    language: Literal["python", "cpp"]
    code: str = Field(max_length=MAX_CODE_CHARS)
    tests: Tests
    time_limit_ms: int | None = Field(None, ge=0)  # None / 0 = the default; clamped by the runner
    memory_limit_mb: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def _tests_are_sane(self):
        every = [*self.tests.public, *self.tests.hidden]
        if not every:
            raise ValueError("no tests")
        if len(every) > MAX_TESTS:
            raise ValueError(f"more than {MAX_TESTS} tests")
        if sum(len(t.input) + len(t.output) for t in every) > MAX_TEST_BYTES:
            raise ValueError("tests are too large")
        return self
