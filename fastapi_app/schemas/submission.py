from pydantic import BaseModel, Field

from schemas.ws import MAX_CODE_CHARS


class CodeSubmission(BaseModel):
    language: str = Field(min_length=1, max_length=32)
    code: str = Field(max_length=MAX_CODE_CHARS)
