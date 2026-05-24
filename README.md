# Agent Project

This repository contains a minimal Python agent scaffold for rapid prototyping.

## Structure

- `agent.py` - core agent class and CLI entry point
- `skills/hello_skill.py` - example skill module
- `requirements.txt` - dependency list
- `.gitignore` - ignore Python artifacts

## Getting Started

1. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Run the agent:

   ```powershell
   python agent.py
   ```

## Extending the Agent

Add new modules under `skills/` and register them in `agent.py`.
