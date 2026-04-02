import base64

from .base import LanguageStrategy


class CppStrategy(LanguageStrategy):
    @property
    def image(self) -> str:
        return "gcc:13"

    def build_command(self, code: str, stdin_data: str) -> str:
        encoded_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
        encoded_stdin = base64.b64encode(stdin_data.encode("utf-8")).decode("utf-8")
        return (
            f"sh -c \"echo '{encoded_code}' | base64 -d > main.cpp && "
            f"g++ -O2 main.cpp -o main && "
            f"echo '{encoded_stdin}' | base64 -d | ./main\""
        )
