# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Village Healer is a voice-first AI health-triage assistant for rural India, built on Google ADK with tools exposed via a FastMCP server. It gives self-care guidance for minor problems and classifies every case into one of three urgency levels (GREEN / YELLOW / RED); it never diagnoses or names medications. The full triage protocol lives in the agent's `instruction` prompt in `Village_Healer/agent.py` — most behavior changes are edits to that prompt.

## Commands

- Install dependencies: `uv sync` (`pyproject.toml` is the source of truth; uv manages `.venv`)
- Run the agent in the ADK dev UI: `adk web` from the project root, then select `Village_Healer` (or `adk run Village_Healer`)
- Run the MCP server standalone (tool debugging): `fastmcp run MCP_Server.py`
- Lint / format: `uv run ruff check .` and `uv run ruff format` (line length 100)

There are no tests yet.

### Required environment

`.env` at the project root (git-ignored) must define:
- `SERPER_API_KEY` — Serper.dev search API key (used by all search-based tools)
- `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` — Gmail SMTP credentials for `send_patient_data`

The LLM is a local OpenAI-compatible endpoint hardcoded in `Village_Healer/agent.py` (`http://10.0.10.51:8000/v1`, model `openai/openai/gpt-oss-20b` via LiteLLM). That server must be running for the agent to respond.

## Architecture

Two files matter:

- `MCP_Server.py` (project root) has a dual role. As a FastMCP **server**, it defines the tools: `search` (Serper web search), `find_nearest_facility` and `get_village_context` (both wrap `search` and return GPS coordinates), and `send_patient_data` (emails a medical-record summary via Gmail SMTP). As an imported **module**, it also constructs `search_tools`, an ADK `MCPToolset` client configured to launch this same file as a stdio subprocess (`fastmcp run MCP_Server.py`).
- `Village_Healer/agent.py` defines `root_agent` (discovered by ADK through `Village_Healer/__init__.py`). Its `instruction` string is the core of the product: the GREEN/YELLOW/RED protocol, the red-flag list, hard prohibitions (no diagnoses, no medication advice except ORS, urgency never lowered by cost/distance), and rules for when each tool fires.

Because `agent.py` does `from MCP_Server import search_tools` and the toolset spawns `fastmcp run MCP_Server.py` by relative path, everything must be run from the project root.

### Known quirks

- `pyproject.toml` still carries metadata from an earlier "finance-manager" template: the project name is `finance-manager` and hatch packages `finance_manager`, which doesn't exist (the real package is `Village_Healer`). Stray comments in `MCP_Server.py` about balances and store credit are leftovers from that same template — they are not features of this project; do not act on them.
- `send_patient_data` uses `smtplib` without importing it (crashes at call time) and ignores its `to_email` parameter — the recipient is hardcoded.
- The agent instruction references a `check_patient_message` tool that is not implemented.

## Conventions (from `.cursor/rules/`)

- Python 3.12+, `uv` for dependency management, `ruff` for linting and formatting, max line width 100.
- Absolute imports only — never relative imports.
- Type hints on all functions; Google-style docstrings.
- Keep functions simple: max nesting depth of 2, cyclomatic complexity ≤ 10, prefer early returns / guard clauses.
- The rules also mandate a standardized file-header comment block on every source file, though existing files don't yet have one.
- Several rules (src/ layout, FastAPI API conventions, MkDocs documentation, loguru logging) describe structures this repo doesn't have — the actual layout described above takes precedence.
