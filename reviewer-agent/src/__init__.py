"""Importing `src` autoloads the repo-root `.env` so `ANTHROPIC_API_KEY`
and `PROCUREMENT_AGENT_URL` are picked up before the CLI runs.
`find_dotenv()` walks up from this file, so the lookup works regardless
of CWD. Env vars set in the shell take precedence (`python-dotenv` does
not override existing values)."""

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
