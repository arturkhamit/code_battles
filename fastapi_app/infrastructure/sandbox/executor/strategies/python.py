import base64

from .base import LanguageStrategy


class PythonStrategy(LanguageStrategy):
    @property
    def image(self) -> str:
        return "python:3.11-alpine"

    def build_command(self, code: str, stdin_data: list[str]) -> str:
        encoded_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")

        if not stdin_data:
            stdin_data = [""]

        inputs_b64 = " ".join(
            base64.b64encode(inp.encode("utf-8")).decode("utf-8") for inp in stdin_data
        )

        return (
            f"sh -c \"echo '{encoded_code}' | base64 -d > script.py && "
            f"for inp in {inputs_b64}; do "
            f"echo $inp | base64 -d | python script.py; "
            f"printf '|||SPLIT|||'; "
            f'done"'
        )
