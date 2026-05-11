"""CLI entry: `uv run python -m src [mine | apply | run-cycle]`.

Three subcommands wrapped around the context-graph skills:

  mine        Default. Run the context-graph-mining skill against an
              Arize project, save a markdown report under
              .context-graph-mining/.
  apply       Translate the latest mining report into a variant config
              bundle under experiments/variants/<id>/.
  run-cycle   Spawn the variant agent + run the seed script + run the
              reviewer — end-to-end one cycle.

Run with no subcommand to invoke `mine` (the common case).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.apply_runner import run_apply
from src.run_cycle import run_cycle
from src.runner import DEFAULT_OUTPUT_DIR, REPO_ROOT, run_mining


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mining-agent",
        description="Mine the procurement-agent Arize project; apply mined patterns as variant configs; run a full self-improvement cycle.",
    )
    sub = parser.add_subparsers(dest="command")

    mine = sub.add_parser("mine", help="Mine an Arize project (default action).")
    _add_mine_args(mine)

    ap = sub.add_parser(
        "apply",
        help="Translate the latest mining report into a variant config bundle.",
    )
    _add_apply_args(ap)

    rc = sub.add_parser(
        "run-cycle",
        help="Spawn variant agent → seed inputs → run reviewer. End-to-end one cycle.",
    )
    _add_run_cycle_args(rc)

    # No-subcommand fallback: behave as `mine`.
    _add_mine_args(parser)

    return parser


def _add_mine_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--repo",
        type=Path,
        default=REPO_ROOT,
        help=f"Path to the repo (default: {REPO_ROOT}).",
    )
    p.add_argument(
        "--project",
        default="procurement-agent",
        help="Arize project name to mine (default: procurement-agent).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for the report file (default: {DEFAULT_OUTPUT_DIR}).",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress streaming agent output; only print the final summary.",
    )


def _add_apply_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--cycle", type=int, default=1, help="Cycle number (default: 1).")
    p.add_argument(
        "--variant",
        choices=["A", "B"],
        required=True,
        help="A = prompt-only, B = prompt + structured metadata.",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Mining report path (default: latest in .context-graph-mining/).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Produce the bundle in the agent's final message; do not write files.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress streaming agent output; only print the final summary.",
    )


def _add_run_cycle_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--cycle", type=int, default=1, help="Cycle number (default: 1).")
    p.add_argument(
        "--variant",
        choices=["A", "B"],
        required=True,
        help="A = prompt-only, B = prompt + structured metadata.",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for the variant agent subprocess (default: 8001).",
    )
    p.add_argument(
        "--keep-db",
        action="store_true",
        help="Reuse an existing variant DB instead of force-reseeding (default: reseed).",
    )
    p.add_argument(
        "--skip-seed",
        action="store_true",
        help="Don't run the seed script (assumes the variant agent already has the inputs).",
    )
    p.add_argument(
        "--skip-review",
        action="store_true",
        help="Don't run the reviewer (just produce agent assessments, no Vera).",
    )
    p.add_argument(
        "--review-parallel",
        type=int,
        default=10,
        help="Concurrent reviewer workers (default: 10).",
    )


def cmd_mine(args: argparse.Namespace) -> int:
    result = asyncio.run(
        run_mining(
            repo_path=args.repo,
            arize_project=args.project,
            output_dir=args.output,
            stream_to=None if args.quiet else sys.stdout,
        )
    )
    print()
    print(f"Report saved to: {result.report_path}")
    if result.session_id:
        print(f"Agent session: {result.session_id}")
    if result.cost_usd is not None:
        print(f"Cost: ${result.cost_usd:.4f}")
    if result.num_turns is not None:
        print(f"Turns: {result.num_turns}")
    if result.final_message:
        print()
        print(result.final_message)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    variant_id = f"cycle-{args.cycle}-{args.variant}"
    try:
        result = asyncio.run(
            run_apply(
                variant_id=variant_id,
                report_path=args.report,
                dry_run=args.dry_run,
                stream_to=None if args.quiet else sys.stdout,
            )
        )
    except (FileExistsError, FileNotFoundError) as e:
        print(str(e), file=sys.stderr)
        return 1

    print()
    label = "Dry-run" if result.dry_run else "Variant written"
    print(f"{label}: {result.variant_id}")
    if not result.dry_run:
        print(f"Path: {result.variant_dir}")
    print(f"Source report: {result.report_path}")
    if result.session_id:
        print(f"Agent session: {result.session_id}")
    if result.cost_usd is not None:
        print(f"Cost: ${result.cost_usd:.4f}")
    if result.num_turns is not None:
        print(f"Turns: {result.num_turns}")
    if result.final_message:
        print()
        print(result.final_message)
    return 0


def cmd_run_cycle(args: argparse.Namespace) -> int:
    try:
        result = run_cycle(
            cycle=args.cycle,
            variant=args.variant,
            port=args.port,
            force_reseed=not args.keep_db,
            skip_seed=args.skip_seed,
            skip_review=args.skip_review,
            review_parallel=args.review_parallel,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    print()
    print(f"Cycle: {result.variant_id}")
    print(f"Arize project: {result.project_name}")
    print(f"Agent log: {result.agent_log}")
    print(f"seed exit: {result.seed_returncode}")
    print(f"reviewer exit: {result.review_returncode}")
    return 0 if result.seed_returncode == 0 and result.review_returncode == 0 else 1


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "apply":
        sys.exit(cmd_apply(args))
    if args.command == "run-cycle":
        sys.exit(cmd_run_cycle(args))
    # Default + explicit `mine` both fall here.
    sys.exit(cmd_mine(args))


if __name__ == "__main__":
    main()
