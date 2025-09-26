#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASGI sequence test: reconciliation version-change/no-statement-diff.

This script runs against the in-process FastAPI app (backend.unified_server.app)
using ASGITransport and LifespanManager. It performs the following sequence:

1) Enable reconciliation statement-level diffs on a target context.
2) Assert S1 via normal endpoint (version bump; set S1).
3) Take a reconciliation snapshot (prev = S1, v1).
4) Raw insert S2 via admin endpoint (no version bump; set S1 ∪ {S2}).
5) Retract S2 via normal endpoint (version bump; set returns to S1, v2).
6) Take another reconciliation snapshot and print discrepancy kinds.
   Expect: ('version_changed_no_statement_diff', <context>) present.

Usage:
  python scripts/asgi_sequence_test.py --context TRUTHS --enable-diffs

Options:
  --context               Context ID to operate on (default: TRUTHS)
  --s1                    Custom S1 statement (default: random P_xxx(a))
  --s2                    Custom S2 statement (default: random Q_xxx(b))
  --enable-diffs          Enable statement-level diffs (default: disabled)
  --statements-limit      Per-context statements limit when enabling diffs (default: 1000)
  --print-json            Pretty-print JSON responses
  --quiet                 Suppress informational logs (only results)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import httpx
from asgi_lifespan import LifespanManager

# Import the in-process FastAPI app
try:
    from backend.unified_server import app as unified_app  # FastAPI instance
except Exception as e:  # pragma: no cover
    unified_app = None  # type: ignore


def _pp(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(obj)


async def _request(client: httpx.AsyncClient, method: str, path: str, *, json_body: Dict | None = None) -> Tuple[int, Any, str]:
    try:
        r = await client.request(method, path, json=json_body, timeout=30)
        status = r.status_code
        text = r.text
        try:
            body = r.json()
        except Exception:
            body = {"_non_json_text": text}
        return status, body, text
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}, ""


async def run_sequence(
    context_id: str,
    enable_diffs: bool,
    statements_limit: int,
    s1: str | None,
    s2: str | None,
    print_json: bool,
    quiet: bool,
) -> int:
    if unified_app is None:
        print("Error: backend.unified_server.app is unavailable in this environment.")
        return 2

    async with LifespanManager(unified_app):
        transport = httpx.ASGITransport(app=unified_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Capabilities
            st, body, _ = await _request(client, "GET", "/ksi/capabilities")
            if not quiet:
                print(f"[GET] /ksi/capabilities -> {st}")
                if print_json:
                    print(_pp(body))
            if st != 200 or not body.get("ksi_available"):
                print("KSI unavailable; aborting.")
                return 3

            # Optionally enable statement diffs
            if enable_diffs:
                payload = {
                    "include_statement_diffs": True,
                    "contexts_to_check": [context_id],
                    "statements_limit": statements_limit,
                    "emit_streamed": False,
                    "emit_summary_every_n_cycles": 0,
                }
                st, body, _ = await _request(client, "POST", "/admin/reconciliation/config", json_body=payload)
                if not quiet:
                    print(f"[POST] /admin/reconciliation/config -> {st}")
                    if print_json:
                        print(_pp(body))
                if st != 200 or not (body.get("config", {}).get("include_statement_diffs") is True):
                    print("Failed to enable statement diffs; continuing without.")

            # Step 1: Assert S1 via normal endpoint (version bump)
            _s1 = s1 or f"P_{uuid4().hex[:6]}(a)"
            payload = {"statement": _s1, "context_id": context_id}
            st, body, _ = await _request(client, "POST", "/kr/assert", json_body=payload)
            print(f"[1] Assert S1={_s1} -> {st}, success={body.get('success')}")
            if print_json and not quiet:
                print(_pp(body))
            if st != 200 or not body.get("success"):
                print("S1 assertion failed; aborting.")
                return 4

            # Step 2: Baseline reconciliation snapshot
            st, body, _ = await _request(client, "POST", "/admin/reconciliation/run-once")
            print(f"[2] Reconciliation run-once -> {st}, success={body.get('success')}")
            if print_json and not quiet:
                print(_pp(body))
            if st != 200 or not body.get("success"):
                print("Baseline reconciliation failed; aborting.")
                return 5

            # Step 3: Raw insert S2 (no version bump)
            _s2 = s2 or f"Q_{uuid4().hex[:6]}(b)"
            st, body, _ = await _request(client, "POST", "/admin/kr/assert-raw", json_body={"statement": _s2, "context_id": context_id})
            print(f"[3] Raw insert S2={_s2} -> {st}, success={body.get('success')}")
            if print_json and not quiet:
                print(_pp(body))
            if st != 200 or not body.get("success"):
                print("Raw insert S2 failed; aborting.")
                return 6

            # Step 4: Retract S2 via normal endpoint (version bump)
            st, body, _ = await _request(client, "POST", "/kr/retract", json_body={"pattern": _s2, "context_id": context_id})
            print(f"[4] Retract S2 -> {st}, success={body.get('success')}")
            if print_json and not quiet:
                print(_pp(body))
            if st != 200 or not body.get("success"):
                print("Retraction of S2 failed; aborting.")
                return 7

            # Step 5: Second reconciliation snapshot and discrepancy check
            st, body, _ = await _request(client, "POST", "/admin/reconciliation/run-once")
            print(f"[5] Reconciliation run-once -> {st}, success={body.get('success')}")
            if st != 200 or not body.get("success"):
                print("Post-retraction reconciliation failed; aborting.")
                if print_json and not quiet:
                    print(_pp(body))
                return 8

            rep = body.get("report") or {}
            discrepancies: List[Dict[str, Any]] = rep.get("discrepancies") or []
            kinds = [(d.get("kind"), d.get("context_id")) for d in discrepancies]
            print(f"[Result] discrepancies: {kinds}")
            if print_json and not quiet:
                print(_pp(rep))

            expected = ("version_changed_no_statement_diff", context_id)
            ok = expected in kinds
            print(f"[Expectation] contains {expected} -> {ok}")
            return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ASGI test: reconciliation version-change/no-statement-diff")
    p.add_argument("--context", default="TRUTHS", help="Context ID to operate on (default: TRUTHS)")
    p.add_argument("--s1", default=None, help="Custom S1 statement (default: random P_xxx(a))")
    p.add_argument("--s2", default=None, help="Custom S2 statement (default: random Q_xxx(b))")
    p.add_argument("--enable-diffs", action="store_true", help="Enable statement-level diffs on the context")
    p.add_argument("--statements-limit", type=int, default=1000, help="Per-context statements limit when enabling diffs (default: 1000)")
    p.add_argument("--print-json", action="store_true", help="Pretty-print JSON responses")
    p.add_argument("--quiet", action="store_true", help="Suppress informational logs (only results)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(
        run_sequence(
            context_id=args.context,
            enable_diffs=args.enable_diffs,
            statements_limit=args.statements_limit,
            s1=args.s1,
            s2=args.s2,
            print_json=args.print_json,
            quiet=args.quiet,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
