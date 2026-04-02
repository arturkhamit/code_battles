from typing import Dict

from .strategies.base import LanguageStrategy
from .strategies.cpp import CppStrategy
from .strategies.python import PythonStrategy


class LanguageRegistry:
    _strategies: Dict[str, LanguageStrategy] = {}

    @classmethod
    def get_strategy(cls, language: str):
        return cls._strategies.get(language)

    @classmethod
    def register(cls, language: str, strategy: LanguageStrategy):
        cls._strategies[language] = strategy


LanguageRegistry.register("python", PythonStrategy())
LanguageRegistry.register("cpp", CppStrategy())
