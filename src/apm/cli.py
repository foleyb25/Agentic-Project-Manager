"""apm — the AgenticProjectManager CLI.

  apm run        one PM run (composes prompt, invokes claude)
  apm consult    one advisory consultation, JSON report on stdout
  apm ledger     get/upsert/patch/hash against the configured ledger backend
  apm bootstrap  GitHub labels + milestone from config
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .config import ConfigError, load_config
from .envfile import load_env_files


def _parse_filters(pairs: list[str]) -> dict:
    filters = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"filter must be key=value, got: {pair}")
        k, v = pair.split("=", 1)
        filters[k] = v
    return filters


def _cmd_run(args: argparse.Namespace) -> int:
    from .pm_run import run_pm

    cfg = load_config(args.config)
    if not cfg.tailored and not args.dry_run:
        print(
            "config/apm.yaml is not tailored yet — open Claude Code and run /tailor",
            file=sys.stderr,
        )
        return 2
    run_id = args.run_id or f"pm-{time.strftime('%Y%m%d-%H%M%S')}"
    return run_pm(
        cfg,
        run_id=run_id,
        trigger=args.trigger,
        comment_id=args.comment_id,
        issue_number=args.issue_number,
        focus=args.focus,
        dry_run=args.dry_run,
    )


def _cmd_consult(args: argparse.Namespace) -> int:
    from .consult import run_consult

    cfg = load_config(args.config)
    return run_consult(cfg, args.role, args.topic)


def _cmd_ledger(args: argparse.Namespace) -> int:
    if args.ledger_cmd == "hash":
        from .hashing import sha256_file, sha256_text

        print(sha256_file(args.file) if args.file else sha256_text(args.text))
        return 0

    from .ledger import make_ledger

    cfg = load_config(args.config)
    ledger = make_ledger(cfg)
    if args.ledger_cmd == "get":
        rows = ledger.get(args.table, _parse_filters(args.filters))
    elif args.ledger_cmd == "upsert":
        payload = json.loads(args.json)
        rows = ledger.upsert(args.table, payload if isinstance(payload, list) else [payload])
    elif args.ledger_cmd == "patch":
        rows = ledger.patch(args.table, _parse_filters(args.filters), json.loads(args.data))
    else:  # pragma: no cover
        raise SystemExit(f"unknown ledger command {args.ledger_cmd}")
    print(json.dumps(rows, indent=2, default=str))
    return 0


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    from .bootstrap import bootstrap

    cfg = load_config(args.config)
    bootstrap(cfg, repo=args.repo)
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to legacy codepages; prompts contain emoji/UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="apm", description=__doc__)
    parser.add_argument("--config", help="path to apm.yaml (default: config/apm.yaml)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="execute one PM run")
    p_run.add_argument("--trigger", default="manual",
                       choices=["manual", "schedule", "issue_comment", "workflow_dispatch"])
    p_run.add_argument("--run-id")
    p_run.add_argument("--comment-id")
    p_run.add_argument("--issue-number")
    p_run.add_argument("--focus")
    p_run.add_argument("--dry-run", action="store_true",
                       help="print the composed prompt and exit")
    p_run.set_defaults(func=_cmd_run)

    p_consult = sub.add_parser("consult", help="run one advisory consultation")
    p_consult.add_argument("role")
    p_consult.add_argument("topic", help='"<feature.area>: <question>"')
    p_consult.set_defaults(func=_cmd_consult)

    p_ledger = sub.add_parser("ledger", help="ledger I/O")
    led_sub = p_ledger.add_subparsers(dest="ledger_cmd", required=True)
    lp = led_sub.add_parser("get")
    lp.add_argument("table")
    lp.add_argument("filters", nargs="*", metavar="key=value")
    lp = led_sub.add_parser("upsert")
    lp.add_argument("table")
    lp.add_argument("json", help="JSON row or array of rows")
    lp = led_sub.add_parser("patch")
    lp.add_argument("table")
    lp.add_argument("filters", nargs="+", metavar="key=value")
    lp.add_argument("--data", required=True, help="JSON fields to set")
    lp = led_sub.add_parser("hash")
    group = lp.add_mutually_exclusive_group(required=True)
    group.add_argument("--file")
    group.add_argument("--text")
    p_ledger.set_defaults(func=_cmd_ledger)

    p_boot = sub.add_parser("bootstrap", help="create labels + milestone on GitHub")
    p_boot.add_argument("--repo", help="owner/repo (default: current)")
    p_boot.set_defaults(func=_cmd_bootstrap)

    args = parser.parse_args(argv)
    load_env_files()  # local convenience; real env vars always win (CI unaffected)
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
