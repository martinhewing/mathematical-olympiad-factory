from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from connectionsphere_factory.config import Settings


class BaseAgent(ABC):

    @property
    @abstractmethod
    def display_name(self) -> str:
        pass

    @property
    @abstractmethod
    def role_label(self) -> str:
        pass

    @abstractmethod
    def voice_id(self, settings: "Settings") -> str:
        pass

    @abstractmethod
    def system_prompt(self, candidate_first_name: str) -> str:
        pass

    def greeting(self, candidate_first_name: str) -> str:
        return ""
