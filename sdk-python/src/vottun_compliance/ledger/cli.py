"""`vottun-ledger verify receipt.json [--mandate-receipt mandate.json] [--rpc URL] [--trusted-key KEY_ID ...]`."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional, Tuple

from .verify import VerifyReport, verify_mandate, verify_receipt


class DuplicateKeyError(ValueError):
    """The same key appears twice in one JSON object: parsers disagree on which value wins."""


def _no_duplicates(pairs: List[Tuple[str, Any]]) -> dict:
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise DuplicateKeyError("duplicate key %r in the receipt" % key)
        seen.add(key)
    return dict(pairs)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vottun-ledger", description="Verify AI Ledger receipts without Vottun.")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify", help="verify a receipt file")
    v.add_argument("receipt", help="path to the receipt JSON")
    v.add_argument(
        "--mandate-receipt", default=None, metavar="FILE",
        help="receipt (with payload) of the mandate.granted event the receipt cites; checks that mandate",
    )
    v.add_argument("--rpc", default=None, help="RPC URL for the anchor check (not used yet)")
    v.add_argument(
        "--trusted-key", action="append", default=None, metavar="KEY_ID",
        help="key id published by Vottun; repeat for several. Without it the keys are not compared",
    )
    return parser


def result_line(report: VerifyReport) -> str:
    """ok means no step failed; what was not checked is named so that ok is not read as more than it is."""
    if not report.ok:
        return "RESULT: FAILED"
    if report.not_checked:
        return "RESULT: ok (not checked: %s)" % ", ".join(report.not_checked)
    return "RESULT: ok"


_UNREADABLE = object()


def _read(path: str) -> Any:
    """The JSON in `path`; _UNREADABLE (and a message on stderr) if it cannot be read."""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh, object_pairs_hook=_no_duplicates)
    except DuplicateKeyError as exc:
        print("%s: %s" % (path, exc), file=sys.stderr)
    except (OSError, ValueError) as exc:  # ValueError covers bad JSON and bad UTF-8
        print("cannot read a receipt from %s: %s" % (path, exc.__class__.__name__), file=sys.stderr)
    return _UNREADABLE


def _printable(text: str) -> str:
    """Text the console can show: characters its encoding lacks are escaped, not a crash."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, "backslashreplace").decode(encoding)


def _mandate_lines(report: VerifyReport, mandate_receipt: Any) -> List[str]:
    """What the mandate says (version, limits, approver, justification), and whether that was verified."""
    payload = mandate_receipt.get("payload") if isinstance(mandate_receipt, dict) else None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    checked = {s.name: s.status for s in report.steps}
    verified = all(checked.get(n) == "pass" for n in ("mandate_payload", "mandate_type", "mandate_log", "mandate_order", "mandate_ref"))
    return [
        "mandate (%s): version %s, approver %s" % (
            "verified" if verified else "NOT verified", data.get("version"), data.get("approver"),
        ),
        "  limits: %s" % json.dumps(data.get("limits"), sort_keys=True, ensure_ascii=False),
        "  justification: %s" % data.get("justification"),
    ]


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    receipt = _read(args.receipt)
    if receipt is _UNREADABLE:
        return 1
    mandate_receipt = None
    if args.mandate_receipt is not None:
        mandate_receipt = _read(args.mandate_receipt)
        if mandate_receipt is _UNREADABLE:
            return 1
        report = verify_mandate(receipt, mandate_receipt, trusted_keys=args.trusted_key)
    else:
        report = verify_receipt(receipt, rpc_url=args.rpc, trusted_keys=args.trusted_key)
    width = max([22] + [len(s.name) + 1 for s in report.steps])
    for step in report.steps:
        print("%-*s %-12s %s" % (width, step.name, step.status, step.detail))
    if args.mandate_receipt is not None:
        for line in _mandate_lines(report, mandate_receipt):
            print(_printable(line))
    print(result_line(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
