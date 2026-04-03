from abc import ABC, abstractmethod


class LanguageStrategy(ABC):
    @property
    @abstractmethod
    def image(self) -> str:
        """Returns name of a Docker image"""
        pass

    @property
    def time_buffer(self) -> float:
        """time to initialize a container"""
        return 0.5

    @abstractmethod
    def build_command(self, code: str, stdin_data: list[str]) -> str:
        """generating shell command for launching code inside a container"""
        pass
