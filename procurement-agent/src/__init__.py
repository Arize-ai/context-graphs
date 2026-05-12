"""Importing `src` autoloads the repo-root `.env` so env vars are
available before any submodule (notably `src.instrumentation`) reads
them. `find_dotenv()` walks up from this file, so the lookup works
regardless of the caller's CWD. Missing `.env` is fine — env vars set
in the shell still win, and `python-dotenv` does not override existing
values."""

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
