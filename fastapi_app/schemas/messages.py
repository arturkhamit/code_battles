from pydantic import BaseModel


class CodeSubmitMessage(BaseModel):
    language: str
    code: str


class WsResponse(BaseModel):
    event: str
    data: dict
