"""Independent verifier for AI Ledger receipts (version 1).

Imports nothing from the Vottun backend and makes no network call: everything it checks is in the receipt.
It does NOT know whether the keys in the receipt are the ones Vottun publishes unless the caller passes
`trusted_keys`; without them the `key_trust` step says so (`not_checked`) instead of passing.
`verify_mandate` also checks the mandate an event cites, against the receipt of its mandate.granted event.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import canonical_bytes, leaf_hash
from .merkle import verify_inclusion

PASS = "pass"
FAIL = "fail"
NOT_CHECKED = "not_checked"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class VerifyStep:
    name: str
    status: str  # pass | fail | not_checked | unavailable
    detail: str


@dataclass
class VerifyReport:
    steps: List[VerifyStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if there are steps and none failed. not_checked and unavailable do not fail a receipt."""
        return bool(self.steps) and all(s.status != FAIL for s in self.steps)

    @property
    def not_checked(self) -> List[str]:
        """Names of the steps that did not verify anything (not_checked, or unavailable like erased content)."""
        return [s.name for s in self.steps if s.status in (NOT_CHECKED, UNAVAILABLE)]


_HEX32 = re.compile(r"[0-9a-f]{64}")
_HEX16 = re.compile(r"[0-9a-f]{16}")
_HEX64 = re.compile(r"[0-9a-f]{128}")
_LOG_REF = re.compile(r"lg_[0-9a-f]{16}")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_TS = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z")

_TOP = {"version", "event", "leaf_hash", "leaf_index", "emitter", "checkpoint", "inclusion_proof", "anchor", "payload"}
_EVENT = {
    "v", "event_id", "log_ref", "system_slug", "session_ref", "seq", "prev_hash", "event_type",
    "actor", "occurred_at", "mandate_ref", "commitment",
}
_EMITTER = {"key_id", "public_key", "signature"}
_CHECKPOINT = {
    "v", "log_ref", "tree_size", "root_hash", "previous_root_hash", "signed_at", "key_id", "public_key", "signature",
}
_SIGNED_CHECKPOINT = ("v", "log_ref", "tree_size", "root_hash", "previous_root_hash", "signed_at")


def _is_int(value: Any, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_str(value: Any, pattern: "re.Pattern[str]") -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _format_problems(receipt: Any) -> List[str]:
    """Everything wrong with the shape of the receipt; empty if it is well formed."""
    if not isinstance(receipt, dict):
        return ["the receipt is not a JSON object"]
    problems: List[str] = []

    def keys(obj: Any, expected: set, where: str, optional: Iterable[str] = ()) -> bool:
        if not isinstance(obj, dict):
            problems.append("%s is not an object" % where)
            return False
        missing = sorted(expected - set(obj) - set(optional))
        extra = sorted(set(obj) - expected)
        if missing:
            problems.append("%s is missing: %s" % (where, ", ".join(missing)))
        if extra:
            problems.append("%s has unknown fields: %s" % (where, ", ".join(extra)))
        return not missing and not extra

    def need(ok: bool, what: str) -> None:
        if not ok:
            problems.append(what)

    if not keys(receipt, _TOP, "receipt", optional=("payload",)):
        return problems
    need(_is_int(receipt["version"], 1) and receipt["version"] == 1, "version must be 1")
    need(_is_str(receipt["leaf_hash"], _HEX32), "leaf_hash must be 64 lowercase hex characters")
    need(_is_int(receipt["leaf_index"], 0), "leaf_index must be an integer >= 0")

    event = receipt["event"]
    if keys(event, _EVENT, "event"):
        need(_is_int(event["v"], 1) and event["v"] == 1, "event.v must be 1")
        need(_is_str(event["event_id"], _UUID), "event.event_id must be a lowercase uuid")
        need(_is_str(event["log_ref"], _LOG_REF), "event.log_ref must be lg_ plus 16 hex characters")
        need(isinstance(event["system_slug"], str) and event["system_slug"] != "", "event.system_slug must be a non-empty string")
        need(_is_str(event["session_ref"], _HEX32), "event.session_ref must be 64 lowercase hex characters")
        need(_is_int(event["seq"], 1), "event.seq must be an integer >= 1")
        need(_is_str(event["prev_hash"], _HEX32), "event.prev_hash must be 64 lowercase hex characters")
        need(isinstance(event["event_type"], str) and event["event_type"] != "", "event.event_type must be a non-empty string")
        need(isinstance(event["actor"], str) and event["actor"] != "", "event.actor must be a non-empty string")
        need(_is_str(event["occurred_at"], _TS), "event.occurred_at must be an UTC time with milliseconds ending in Z")
        need(event["mandate_ref"] is None or _is_str(event["mandate_ref"], _HEX32), "event.mandate_ref must be null or 64 lowercase hex characters")
        need(_is_str(event["commitment"], _HEX32), "event.commitment must be 64 lowercase hex characters")

    emitter = receipt["emitter"]
    if keys(emitter, _EMITTER, "emitter"):
        need(_is_str(emitter["key_id"], _HEX16), "emitter.key_id must be 16 lowercase hex characters")
        need(_is_str(emitter["public_key"], _HEX32), "emitter.public_key must be 64 lowercase hex characters")
        need(_is_str(emitter["signature"], _HEX64), "emitter.signature must be 128 lowercase hex characters")

    cp = receipt["checkpoint"]
    if keys(cp, _CHECKPOINT, "checkpoint"):
        need(_is_int(cp["v"], 1) and cp["v"] == 1, "checkpoint.v must be 1")
        need(_is_str(cp["log_ref"], _LOG_REF), "checkpoint.log_ref must be lg_ plus 16 hex characters")
        need(_is_int(cp["tree_size"], 1), "checkpoint.tree_size must be an integer >= 1")
        need(_is_str(cp["root_hash"], _HEX32), "checkpoint.root_hash must be 64 lowercase hex characters")
        need(cp["previous_root_hash"] is None or _is_str(cp["previous_root_hash"], _HEX32), "checkpoint.previous_root_hash must be null or 64 lowercase hex characters")
        need(_is_str(cp["signed_at"], _TS), "checkpoint.signed_at must be an UTC time with milliseconds ending in Z")
        need(_is_str(cp["key_id"], _HEX16), "checkpoint.key_id must be 16 lowercase hex characters")
        need(_is_str(cp["public_key"], _HEX32), "checkpoint.public_key must be 64 lowercase hex characters")
        need(_is_str(cp["signature"], _HEX64), "checkpoint.signature must be 128 lowercase hex characters")

    proof = receipt["inclusion_proof"]
    need(isinstance(proof, list) and all(_is_str(p, _HEX32) for p in proof), "inclusion_proof must be a list of 64-hex hashes")
    need(receipt["anchor"] is None or isinstance(receipt["anchor"], dict), "anchor must be null or an object")

    if "payload" in receipt:
        payload = receipt["payload"]
        if isinstance(payload, dict) and set(payload) == {"erased"}:
            need(payload["erased"] is True, "payload.erased must be true")
        elif keys(payload, {"salt", "data"}, "payload"):
            need(_is_str(payload["salt"], _HEX32), "payload.salt must be 64 lowercase hex characters")
            need(isinstance(payload["data"], dict), "payload.data must be an object")
    return problems


def _key_id(public_key_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:16]


def _check_signature(public_key_hex: str, signature_hex: str, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(bytes.fromhex(signature_hex), message)
    except (InvalidSignature, ValueError):
        return False
    return True


def _step(name: str, check: Callable[[], VerifyStep]) -> VerifyStep:
    """Run one step; an unexpected error is a failure, never an exception or a pass."""
    try:
        return check()
    except Exception as exc:  # noqa: BLE001 - a verifier must report, not crash
        return VerifyStep(name, FAIL, "could not be checked: %s" % exc.__class__.__name__)


def verify_receipt(
    receipt: Any, *, rpc_url: Optional[str] = None, trusted_keys: Optional[Iterable[str]] = None
) -> VerifyReport:
    """Check a receipt. `rpc_url` is accepted for the anchor check of Phase 2 and unused for now."""
    del rpc_url
    problems = _format_problems(receipt)
    if problems:
        return VerifyReport([VerifyStep("format", FAIL, "; ".join(problems))])
    r = receipt
    event, emitter, cp = r["event"], r["emitter"], r["checkpoint"]
    steps = [VerifyStep("format", PASS, "version 1, all fields present with the right types")]

    def key_ids() -> VerifyStep:
        bad = [
            who for who, k in (("emitter", emitter), ("checkpoint", cp)) if _key_id(k["public_key"]) != k["key_id"]
        ]
        if bad:
            return VerifyStep("key_ids", FAIL, "key_id is not the SHA-256 prefix of the public key: " + ", ".join(bad))
        if emitter["key_id"] == cp["key_id"]:
            return VerifyStep("key_ids", FAIL, "the emitter and the log must use different keys")
        return VerifyStep("key_ids", PASS, "key ids match their public keys and the two keys differ")

    def envelope() -> VerifyStep:
        if leaf_hash(canonical_bytes(event)).hex() != r["leaf_hash"]:
            return VerifyStep("envelope", FAIL, "the event does not hash to leaf_hash")
        return VerifyStep("envelope", PASS, "the event hashes to leaf_hash")

    def emitter_signature() -> VerifyStep:
        if not _check_signature(emitter["public_key"], emitter["signature"], bytes.fromhex(r["leaf_hash"])):
            return VerifyStep("emitter_signature", FAIL, "the emitter signature does not verify")
        return VerifyStep("emitter_signature", PASS, "the emitter signed leaf_hash")

    def checkpoint_signature() -> VerifyStep:
        signed = {k: cp[k] for k in _SIGNED_CHECKPOINT}
        if not _check_signature(cp["public_key"], cp["signature"], canonical_bytes(signed)):
            return VerifyStep("checkpoint_signature", FAIL, "the checkpoint signature does not verify")
        return VerifyStep("checkpoint_signature", PASS, "the log key signed the checkpoint")

    def same_log() -> VerifyStep:
        if cp["log_ref"] != event["log_ref"]:
            return VerifyStep("same_log", FAIL, "the checkpoint belongs to a different log than the event")
        return VerifyStep("same_log", PASS, "event and checkpoint are from the same log")

    def inclusion() -> VerifyStep:
        ok = verify_inclusion(
            bytes.fromhex(r["leaf_hash"]), r["leaf_index"], cp["tree_size"],
            [bytes.fromhex(p) for p in r["inclusion_proof"]], bytes.fromhex(cp["root_hash"]),
        )
        if not ok:
            return VerifyStep("inclusion", FAIL, "the proof does not lead leaf_hash to the checkpoint root")
        return VerifyStep("inclusion", PASS, "leaf %d is in the tree of %d leaves" % (r["leaf_index"], cp["tree_size"]))

    def content() -> VerifyStep:
        if "payload" not in r:
            return VerifyStep("content", NOT_CHECKED, "the receipt carries no payload; the content was not checked")
        payload = r["payload"]
        if "erased" in payload:
            return VerifyStep("content", UNAVAILABLE, "the content was erased; the event is still verified")
        mac = hmac.new(bytes.fromhex(payload["salt"]), canonical_bytes(payload["data"]), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, event["commitment"]):
            return VerifyStep("content", FAIL, "the payload does not match the event commitment")
        return VerifyStep("content", PASS, "the payload matches the event commitment")

    def key_trust() -> VerifyStep:
        if trusted_keys is None:
            return VerifyStep(
                "key_trust", NOT_CHECKED,
                "the keys were not compared with the ones published by Vottun; anyone can sign a receipt with their own key",
            )
        trusted = set(trusted_keys)
        missing = [who for who, k in (("emitter", emitter), ("log", cp)) if k["key_id"] not in trusted]
        if missing:
            return VerifyStep("key_trust", FAIL, "key not in the trusted set: " + ", ".join(missing))
        return VerifyStep("key_trust", PASS, "emitter and log keys are in the trusted set")

    def anchor() -> VerifyStep:
        if r["anchor"] is None:
            return VerifyStep("anchor", NOT_CHECKED, "not anchored yet")
        return VerifyStep("anchor", NOT_CHECKED, "the anchor check arrives in Phase 2")

    for name, fn in (
        ("key_ids", key_ids), ("envelope", envelope), ("emitter_signature", emitter_signature),
        ("checkpoint_signature", checkpoint_signature), ("same_log", same_log), ("inclusion", inclusion),
        ("content", content), ("key_trust", key_trust), ("anchor", anchor),
    ):
        steps.append(_step(name, fn))
    return VerifyReport(steps)


def verify_mandate(
    event_receipt: Any, mandate_receipt: Any, *, trusted_keys: Optional[Iterable[str]] = None
) -> VerifyReport:
    """Check that the mandate an event cites is the one granted earlier in the same log.

    The report holds the event receipt's own steps, then the mandate receipt's steps prefixed with
    `mandate_receipt.`, then the mandate steps. An event with mandate_ref null cites no mandate: the
    `mandate` step is not_checked. A mandate step passes only after it was checked; anything the verifier
    could not check about a cited mandate is a failure.
    """
    trusted = None if trusted_keys is None else set(trusted_keys)  # read once, used for both receipts
    event_report = verify_receipt(event_receipt, trusted_keys=trusted)
    steps = list(event_report.steps)
    if not event_report.ok:
        steps.append(VerifyStep("mandate", FAIL, "the event receipt does not verify, so the mandate it cites cannot be checked"))
        return VerifyReport(steps)
    event = event_receipt["event"]
    if event["mandate_ref"] is None:
        steps.append(VerifyStep("mandate", NOT_CHECKED, "the event cites no mandate (mandate_ref is null)"))
        return VerifyReport(steps)

    mandate_report = verify_receipt(mandate_receipt, trusted_keys=trusted)
    steps += [VerifyStep("mandate_receipt." + s.name, s.status, s.detail) for s in mandate_report.steps]
    if not mandate_report.ok:
        steps.append(VerifyStep("mandate", FAIL, "the mandate receipt does not verify"))
        return VerifyReport(steps)
    m = mandate_receipt
    payload = m.get("payload")
    has_content = isinstance(payload, dict) and "data" in payload

    def mandate_payload() -> VerifyStep:
        if payload is None:
            return VerifyStep("mandate_payload", FAIL, "the mandate receipt carries no payload; get it with the payload")
        if not has_content:
            return VerifyStep("mandate_payload", FAIL, "the mandate content was erased; the mandate cannot be checked")
        # verify_receipt passed with a payload present, so its content step passed
        return VerifyStep("mandate_payload", PASS, "the mandate content matches its event commitment")

    def mandate_type() -> VerifyStep:
        if m["event"]["event_type"] != "mandate.granted":
            return VerifyStep("mandate_type", FAIL, "the mandate receipt is a %s event, not mandate.granted" % m["event"]["event_type"])
        return VerifyStep("mandate_type", PASS, "the mandate receipt is a mandate.granted event")

    def mandate_log() -> VerifyStep:
        if m["event"]["log_ref"] != event["log_ref"]:
            return VerifyStep("mandate_log", FAIL, "the mandate was granted in a different log than the event")
        return VerifyStep("mandate_log", PASS, "the mandate and the event are in the same log")

    def mandate_order() -> VerifyStep:
        if not m["leaf_index"] < event_receipt["leaf_index"]:
            return VerifyStep(
                "mandate_order", FAIL,
                "the mandate (leaf %d) was not recorded before the event (leaf %d)" % (m["leaf_index"], event_receipt["leaf_index"]),
            )
        return VerifyStep(
            "mandate_order", PASS,
            "the mandate (leaf %d) was recorded before the event (leaf %d)" % (m["leaf_index"], event_receipt["leaf_index"]),
        )

    def mandate_ref() -> VerifyStep:
        if not has_content:
            return VerifyStep("mandate_ref", FAIL, "there is no mandate content to compare with the event's mandate_ref")
        if hashlib.sha256(canonical_bytes(payload["data"])).hexdigest() != event["mandate_ref"]:
            return VerifyStep("mandate_ref", FAIL, "the mandate content does not hash to the event's mandate_ref")
        return VerifyStep("mandate_ref", PASS, "the mandate content hashes to the event's mandate_ref")

    for name, fn in (
        ("mandate_payload", mandate_payload), ("mandate_type", mandate_type), ("mandate_log", mandate_log),
        ("mandate_order", mandate_order), ("mandate_ref", mandate_ref),
    ):
        steps.append(_step(name, fn))
    return VerifyReport(steps)
