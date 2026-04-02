from abc import ABC, abstractmethod


class LanguageStrategy(ABC):
    @property
    @abstractmethod
    def image(self) -> str:
        """Returns name of a Docker image"""
        pass

    @abstractmethod
    def build_command(self, code: str, stdin_data: str) -> str:
        """generating shell command for launching code inside a container"""
        pass
