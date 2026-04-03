import base64

from .base import LanguageStrategy


class CppStrategy(LanguageStrategy):
    @property
    def image(self) -> str:
        return "gcc:13"

    @property
    def time_buffer(self) -> float:
        return 1.0

    def build_command(self, code: str, stdin_data: list[str]) -> str:
        encoded_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")

        if not stdin_data:
            stdin_data = [""]

        inputs_b64 = " ".join(
            base64.b64encode(inp.encode("utf-8")).decode("utf-8") for inp in stdin_data
        )

        return (
            f"sh -c \"echo '{encoded_code}' | base64 -d > main.cpp && "
            f"g++ -O2 main.cpp -o main && "
            f"for inp in {inputs_b64}; do "
            f"echo $inp | base64 -d | ./main; "
            f"printf '|||SPLIT|||'; "
            f'done"'
        )
