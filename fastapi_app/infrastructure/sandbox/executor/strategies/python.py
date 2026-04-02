import base64

from .base import LanguageStrategy


class PythonStrategy(LanguageStrategy):
    @property
    def image(self) -> str:
        return "python:3.11-alpine"

    def build_command(self, code: str, stdin_data: str) -> str:
        encoded_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
        encoded_stdin = base64.b64encode(stdin_data.encode("utf-8")).decode("utf-8")
        return (
            f"sh -c \"echo '{encoded_stdin}' | base64 -d | "
            f"python -c \\\"import base64; exec(base64.b64decode('{encoded_code}').decode('utf-8'))\\\"\""
        )
