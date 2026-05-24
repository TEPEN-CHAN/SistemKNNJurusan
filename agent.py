import importlib
import os
from pathlib import Path
from typing import Callable, Dict

Skill = Callable[[str], str]

class Agent:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}

    def register_skill(self, name: str, skill: Skill) -> None:
        self.skills[name] = skill

    def run(self, input_text: str) -> str:
        if not input_text:
            return "No input provided."

        pieces = input_text.strip().split(maxsplit=1)
        skill_name = pieces[0].lower()
        skill_input = pieces[1] if len(pieces) > 1 else ""

        skill = self.skills.get(skill_name)
        if not skill:
            return f"Unknown skill: {skill_name}. Available: {', '.join(self.skills)}"

        return skill(skill_input)

    def load_skills(self, directory: str) -> None:
        skill_dir = Path(directory)
        if not skill_dir.exists():
            return

        for file_path in skill_dir.glob("*.py"):
            module_name = file_path.stem
            module = importlib.import_module(f"skills.{module_name}")
            if hasattr(module, "register"):
                module.register(self)


def main() -> None:
    agent = Agent()
    agent.load_skills("skills")

    print("Agent ready. Type a registered skill name and optional input.")
    print("Example: hello world")

    try:
        while True:
            prompt = input("> ")
            if prompt.lower() in {"exit", "quit"}:
                break
            print(agent.run(prompt))
    except KeyboardInterrupt:
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
