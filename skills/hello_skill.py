from typing import Callable
from agent import Agent


def hello_skill(text: str) -> str:
    if not text:
        return "Hello! Tell me your name after the skill command."
    return f"Hello, {text}!"


def register(agent: Agent) -> None:
    agent.register_skill("hello", hello_skill)
