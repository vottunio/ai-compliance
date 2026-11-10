"""Receipt verifier against the golden receipt (tests/vectors/ledger_v1_vectors.json). No network."""
from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vottun_compliance.ledger import VerifyReport, VerifyStep, verify_receipt
from vottun_compliance.ledger.cli import main

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((ROOT / "tests" / "vectors" / "ledger_v1_vectors.json").read_text(encoding="utf-8"))["golden"]["receipt"]["expected"]
GOLDEN_KEY_ID = GOLDEN["emitter"]["key_id"]
BOTH_KEYS = {GOLDEN["emitter"]["key_id"], GOLDEN["checkpoint"]["key_id"]}


def fresh() -> dict:
    return copy.deepcopy(GOLDEN)


def statuses(report: VerifyReport) -> dict:
    return {s.name: s.status for s in report.steps}


def flip_hex(value: str) -> str:
    """Same length, still lowercase hex, one nibble different."""
    return value[:-1] + ("0" if value[-1] != "0" else "1")


def change(value):
    """A different value of the same kind (so the format check passes and the crypto has to catch it)."""
    if value is None:
        return "ab" * 32
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if value.startswith("lg_"):
        return flip_hex(value)
    if "T" in value and value.endswith("Z"):
        return value[:-2] + ("1" if value[-2] != "1" else "2") + "Z"
    if all(c in "0123456789abcdef-" for c in value):
        return flip_hex(value)
    return value + "x"


def test_golden_receipt_passes():
    report = verify_receipt(GOLDEN)
    assert report.ok
    assert [s.name for s in report.steps] == [
        "format", "key_ids", "envelope", "emitter_signature", "checkpoint_signature",
        "same_log", "inclusion", "content", "key_trust", "anchor",
    ]
    assert statuses(report) == {
        "format": "pass", "key_ids": "pass", "envelope": "pass", "emitter_signature": "pass",
        "checkpoint_signature": "pass", "same_log": "pass", "inclusion": "pass", "content": "pass",
        "key_trust": "not_checked", "anchor": "not_checked",
    }
    assert isinstance(report.steps[0], VerifyStep)


def test_golden_receipt_tree_has_a_two_element_proof():
    assert len(GOLDEN["inclusion_proof"]) == 2 and GOLDEN["leaf_index"] == 1 and GOLDEN["checkpoint"]["tree_size"] == 3


def _mutations():
    for key in GOLDEN["event"]:
        yield "event." + key, lambda r, k=key: r["event"].__setitem__(k, change(r["event"][k]))
    yield "leaf_hash", lambda r: r.__setitem__("leaf_hash", change(r["leaf_hash"]))
    yield "leaf_index", lambda r: r.__setitem__("leaf_index", r["leaf_index"] + 1)
    yield "leaf_index_down", lambda r: r.__setitem__("leaf_index", r["leaf_index"] - 1)
    for key in GOLDEN["emitter"]:
        yield "emitter." + key, lambda r, k=key: r["emitter"].__setitem__(k, change(r["emitter"][k]))
    for key in GOLDEN["checkpoint"]:
        yield "checkpoint." + key, lambda r, k=key: r["checkpoint"].__setitem__(k, change(r["checkpoint"][k]))
    for i in range(len(GOLDEN["inclusion_proof"])):
        yield "proof[%d]" % i, lambda r, i=i: r["inclusion_proof"].__setitem__(i, flip_hex(r["inclusion_proof"][i]))
    yield "proof_extra", lambda r: r["inclusion_proof"].append("cd" * 32)
    yield "proof_missing_last", lambda r: r["inclusion_proof"].pop()
    yield "proof_missing_first", lambda r: r["inclusion_proof"].pop(0)
    yield "proof_empty", lambda r: r["inclusion_proof"].clear()
    yield "proof_swapped", lambda r: r["inclusion_proof"].reverse()
    yield "salt", lambda r: r["payload"].__setitem__("salt", flip_hex(r["payload"]["salt"]))
    for key in GOLDEN["payload"]["data"]:
        yield "data." + key, lambda r, k=key: r["payload"]["data"].__setitem__(k, change(r["payload"]["data"][k]))
    yield "data_extra_key", lambda r: r["payload"]["data"].__setitem__("extra", 1)
    yield "data_removed_key", lambda r: r["payload"]["data"].pop("table_id")
    yield "version", lambda r: r.__setitem__("version", 2)
    yield "extra_top_level_field", lambda r: r.__setitem__("note", "hello")
    yield "extra_event_field", lambda r: r["event"].__setitem__("extra", 1)


@pytest.mark.parametrize("name,mutate", list(_mutations()), ids=[n for n, _ in _mutations()])
def test_every_changed_field_fails(name, mutate):
    receipt = fresh()
    mutate(receipt)
    assert receipt != GOLDEN
    report = verify_receipt(receipt)
    assert not report.ok, name
    assert any(s.status == "fail" for s in report.steps)


def test_the_right_step_catches_each_kind_of_change():
    def failed(mutate) -> set:
        r = fresh()
        mutate(r)
        return {s.name for s in verify_receipt(r).steps if s.status == "fail"}

    assert "envelope" in failed(lambda r: r["event"].__setitem__("seq", 4))
    assert "emitter_signature" in failed(lambda r: r["emitter"].__setitem__("signature", flip_hex(r["emitter"]["signature"])))
    assert "checkpoint_signature" in failed(lambda r: r["checkpoint"].__setitem__("signature", flip_hex(r["checkpoint"]["signature"])))
    assert "inclusion" in failed(lambda r: r["inclusion_proof"].__setitem__(0, flip_hex(r["inclusion_proof"][0])))
    assert "inclusion" in failed(lambda r: r["inclusion_proof"].append("cd" * 32))
    assert "inclusion" in failed(lambda r: r["inclusion_proof"].pop())
    assert "checkpoint_signature" in failed(lambda r: r["checkpoint"].__setitem__("tree_size", 4))
    assert "same_log" in failed(lambda r: r["checkpoint"].__setitem__("log_ref", "lg_" + "f" * 16))
    assert "key_ids" in failed(lambda r: r["emitter"].__setitem__("key_id", flip_hex(r["emitter"]["key_id"])))
    assert failed(lambda r: r["payload"].__setitem__("salt", flip_hex(r["payload"]["salt"]))) == {"content"}
    assert failed(lambda r: r["payload"]["data"].__setitem__("party_size", 5)) == {"content"}


def test_wrong_public_key_fails():
    other = "ab" * 32
    r = fresh()
    r["emitter"]["public_key"] = other
    r["emitter"]["key_id"] = __import__("hashlib").sha256(bytes.fromhex(other)).hexdigest()[:16]  # self-consistent key swap
    report = verify_receipt(r)
    assert not report.ok and statuses(report)["emitter_signature"] == "fail" and statuses(report)["key_ids"] == "pass"


def test_decimals_in_the_payload_fail_instead_of_crashing():
    r = fresh()
    r["payload"]["data"]["party_size"] = 4.5
    report = verify_receipt(r)
    assert not report.ok and statuses(report)["content"] == "fail"


@pytest.mark.parametrize("garbage", [None, [], "receipt", 7, {}, {"version": 1}, {**GOLDEN, "leaf_index": True}, {**GOLDEN, "leaf_index": 1.0}])
def test_malformed_receipts_fail_at_format_and_stop(garbage):
    report = verify_receipt(garbage)
    assert not report.ok
    assert [s.name for s in report.steps] == ["format"] and report.steps[0].status == "fail"


def test_uppercase_hex_is_rejected():
    r = fresh()
    r["leaf_hash"] = r["leaf_hash"].upper()
    assert statuses(verify_receipt(r))["format"] == "fail"


def test_erased_payload_reports_content_unavailable():
    r = fresh()
    r["payload"] = {"erased": True}
    report = verify_receipt(r)
    assert report.ok and statuses(report)["content"] == "unavailable"
    assert "erased" in next(s for s in report.steps if s.name == "content").detail


def test_receipt_without_payload_does_not_check_content():
    r = fresh()
    del r["payload"]
    report = verify_receipt(r)
    assert report.ok and statuses(report)["content"] == "not_checked"


def test_malformed_erased_marker_fails():
    for bad in ({"erased": False}, {"erased": True, "salt": "00" * 32}):
        r = fresh()
        r["payload"] = bad
        assert not verify_receipt(r).ok


def test_untrusted_key_fails():
    report = verify_receipt(GOLDEN, trusted_keys={"0123456789abcdef"})
    assert not report.ok and statuses(report)["key_trust"] == "fail"
    assert not verify_receipt(GOLDEN, trusted_keys=set()).ok


def test_trusted_keys_pass():
    report = verify_receipt(GOLDEN, trusted_keys=BOTH_KEYS)
    assert report.ok and statuses(report)["key_trust"] == "pass"


def test_without_trusted_keys_is_not_checked():
    step = next(s for s in verify_receipt(GOLDEN).steps if s.name == "key_trust")
    assert step.status == "not_checked" and "Vottun" in step.detail


def test_anchor_is_never_reported_as_checked():
    r = fresh()
    r["anchor"] = {"batch_id": 1}
    step = next(s for s in verify_receipt(r, rpc_url="http://example.invalid").steps if s.name == "anchor")
    assert step.status == "not_checked" and "Phase 2" in step.detail


def test_report_ok_ignores_not_checked_and_unavailable_only():
    assert VerifyReport([VerifyStep("a", "not_checked", ""), VerifyStep("b", "unavailable", "")]).ok
    assert not VerifyReport([VerifyStep("a", "pass", ""), VerifyStep("b", "fail", "")]).ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(GOLDEN), encoding="utf-8")
    assert main(["verify", str(good)]) == 0
    out = capsys.readouterr().out
    assert "emitter_signature" in out and "pass" in out and "not_checked" in out and "RESULT: ok" in out

    bad = fresh()
    bad["event"]["seq"] = 4
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["verify", str(bad_file)]) == 1
    assert "fail" in capsys.readouterr().out

    not_json = tmp_path / "nope.json"
    not_json.write_text("this is not json", encoding="utf-8")
    assert main(["verify", str(not_json)]) == 1
    assert main(["verify", str(tmp_path / "missing.json")]) == 1
    binary = tmp_path / "bin.json"
    binary.write_bytes(b"\xff\xfe\x00")
    assert main(["verify", str(binary)]) == 1


def test_cli_trusted_key_and_rpc(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(GOLDEN), encoding="utf-8")
    assert main(["verify", str(good), "--trusted-key", GOLDEN_KEY_ID, "--trusted-key", GOLDEN["checkpoint"]["key_id"], "--rpc", "http://example.invalid"]) == 0
    assert main(["verify", str(good), "--trusted-key", "0123456789abcdef"]) == 1
    assert main(["verify", str(good), "--trusted-key", "0123456789abcdef", "--trusted-key", GOLDEN_KEY_ID, "--trusted-key", GOLDEN["checkpoint"]["key_id"]]) == 0
    capsys.readouterr()


def test_cli_runs_as_a_module(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(GOLDEN), encoding="utf-8")
    env = {**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}
    run = subprocess.run(
        [sys.executable, "-m", "vottun_compliance.ledger.cli", "verify", str(good)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path),
    )
    assert run.returncode == 0, run.stderr
    assert "RESULT: ok" in run.stdout


def test_verifier_has_no_backend_or_network_imports():
    forbidden = {"app", "httpx", "requests", "urllib", "urllib3", "http", "socket", "aiohttp", "asyncio", "ssl", "websockets"}
    seen = set()
    files = sorted((ROOT / "src" / "vottun_compliance" / "ledger").glob("*.py"))
    assert {f.name for f in files} >= {"__init__.py", "canonical.py", "merkle.py", "verify.py", "cli.py"}
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                seen.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    seen.add((node.module or "").split(".")[0])
                else:  # relative: must stay inside the ledger package
                    assert node.level == 1, "%s imports outside the ledger package" % path.name
    assert not seen & forbidden, seen & forbidden
    assert "vottun_compliance" not in seen


# ---------------------------------------------------------------------------
# fix round 1
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from vottun_compliance.ledger.canonical import canonical_bytes, leaf_hash, node_hash  # noqa: E402
from vottun_compliance.ledger.cli import result_line  # noqa: E402
from vottun_compliance.ledger.merkle import verify_inclusion  # noqa: E402

VECTORS = json.loads((ROOT / "tests" / "vectors" / "ledger_v1_vectors.json").read_text(encoding="utf-8"))
SIGNERS = VECTORS["golden"]["receipt"]["signers"]


def key_from_seed(seed_hex: str):
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, public.hex(), hashlib.sha256(public).hexdigest()[:16]


EMITTER_KEY = key_from_seed(SIGNERS["emitter"]["seed_hex"])
LOG_KEY = key_from_seed(SIGNERS["log"]["seed_hex"])


def make_receipt(data: dict, salt: str = "5a" * 32, emitter=EMITTER_KEY, log=LOG_KEY) -> dict:
    """A one-leaf receipt signed here with the test seeds: the independent builder for custom payloads."""
    import hmac as _hmac

    event = dict(GOLDEN["event"], commitment=_hmac.new(bytes.fromhex(salt), canonical_bytes(data), hashlib.sha256).hexdigest())
    leaf = leaf_hash(canonical_bytes(event))
    cp = {"v": 1, "log_ref": event["log_ref"], "tree_size": 1, "root_hash": leaf.hex(),
          "previous_root_hash": None, "signed_at": "2026-10-30T12:10:00.456Z"}
    return {
        "version": 1, "event": event, "leaf_hash": leaf.hex(), "leaf_index": 0,
        "emitter": {"key_id": emitter[2], "public_key": emitter[1], "signature": emitter[0].sign(leaf).hex()},
        "checkpoint": dict(cp, key_id=log[2], public_key=log[1], signature=log[0].sign(canonical_bytes(cp)).hex()),
        "inclusion_proof": [], "anchor": None, "payload": {"salt": salt, "data": data},
    }


# 2. two distinct keys in the golden receipt

def test_golden_receipt_uses_two_distinct_keys():
    assert GOLDEN["emitter"]["key_id"] != GOLDEN["checkpoint"]["key_id"]
    assert GOLDEN["emitter"]["public_key"] != GOLDEN["checkpoint"]["public_key"]
    assert GOLDEN["checkpoint"]["public_key"] == "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"  # RFC 8032 test 2


def test_make_receipt_helper_agrees_with_the_verifier():
    assert verify_receipt(make_receipt({"a": 1}), trusted_keys={EMITTER_KEY[2], LOG_KEY[2]}).ok


# 3. key roles

def test_emitter_key_alone_is_not_enough():
    report = verify_receipt(GOLDEN, trusted_keys={GOLDEN["emitter"]["key_id"]})
    assert not report.ok and statuses(report)["key_trust"] == "fail"


def test_log_key_alone_is_not_enough():
    report = verify_receipt(GOLDEN, trusted_keys={GOLDEN["checkpoint"]["key_id"]})
    assert not report.ok and statuses(report)["key_trust"] == "fail"


def test_both_keys_trusted_pass():
    ids = {GOLDEN["emitter"]["key_id"], GOLDEN["checkpoint"]["key_id"]}
    assert statuses(verify_receipt(GOLDEN, trusted_keys=ids))["key_trust"] == "pass"


def test_self_consistent_checkpoint_key_swap_fails_the_signature():
    _, public, key_id = key_from_seed("07" * 32)
    r = fresh()
    r["checkpoint"]["public_key"], r["checkpoint"]["key_id"] = public, key_id
    report = verify_receipt(r)
    assert not report.ok
    assert statuses(report)["checkpoint_signature"] == "fail" and statuses(report)["key_ids"] == "pass"


def test_checkpoint_signed_with_the_emitter_key_fails():
    r = fresh()
    cp = r["checkpoint"]
    cp["public_key"], cp["key_id"] = EMITTER_KEY[1], EMITTER_KEY[2]
    signed = {k: cp[k] for k in ("v", "log_ref", "tree_size", "root_hash", "previous_root_hash", "signed_at")}
    cp["signature"] = EMITTER_KEY[0].sign(canonical_bytes(signed)).hex()
    report = verify_receipt(r)
    assert not report.ok and statuses(report)["checkpoint_signature"] == "pass"  # a valid signature, by the wrong role
    assert statuses(report)["key_ids"] == "fail"


def test_emitter_and_log_with_the_same_key_fail():
    assert statuses(verify_receipt(make_receipt({"a": 1}, log=EMITTER_KEY)))["key_ids"] == "fail"


# 4. same bytes as the backend, from the copied vectors

def test_canonical_bytes_matches_every_vector_case():
    for case in VECTORS["canonical_bytes"]:
        assert canonical_bytes(case["input"]).decode("utf-8") == case["expected_utf8"]


def test_canonical_bytes_rejects_decimals():
    with pytest.raises(ValueError):
        canonical_bytes({"a": {"b": [1, 2.5]}})


def _root(leaves):
    if len(leaves) == 1:
        return leaves[0]
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    return node_hash(_root(leaves[:k]), _root(leaves[k:]))


def _path(m, leaves):
    if len(leaves) == 1:
        return []
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    if m < k:
        return _path(m, leaves[:k]) + [_root(leaves[k:])]
    return _path(m - k, leaves[k:]) + [_root(leaves[:k])]


def _vector_leaves():
    return [leaf_hash(bytes.fromhex(h)) for h in VECTORS["leaves_hex"]]


def test_every_vector_root():
    leaves = _vector_leaves()
    assert VECTORS["roots"]["0"] == hashlib.sha256(b"").hexdigest()
    for size in range(1, 9):
        assert _root(leaves[:size]).hex() == VECTORS["roots"][str(size)], size


def test_inclusion_for_every_index_and_size_up_to_8():
    leaves = _vector_leaves()
    checked = 0
    for size in range(1, 9):
        root = bytes.fromhex(VECTORS["roots"][str(size)])
        for index in range(size):
            path = _path(index, leaves[:size])
            assert verify_inclusion(leaves[index], index, size, path, root), (index, size)
            checked += 1
            assert not verify_inclusion(leaves[index], index, size, path + [b"\x00" * 32], root)
            if path:
                assert not verify_inclusion(leaves[index], index, size, path[:-1], root)
    assert checked == 36  # includes size 1 and the last leaf of every odd tree


def test_golden_event_and_checkpoint_bytes():
    def iso_ms(text):
        value = datetime.fromisoformat(text).astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (value.microsecond // 1000)

    g = VECTORS["golden"]
    row = g["event"]["row"]
    envelope = {
        "v": 1, "event_id": row["event_id"], "log_ref": g["event"]["log_ref"], "system_slug": row["system_slug"],
        "session_ref": row["session_ref"], "seq": row["seq"], "prev_hash": row["prev_hash"],
        "event_type": row["event_type"], "actor": row["actor"], "occurred_at": iso_ms(row["occurred_at"]),
        "mandate_ref": row["mandate_ref"], "commitment": row["commitment"],
    }
    assert canonical_bytes(envelope).decode("utf-8") == g["event"]["canonical"]
    assert leaf_hash(canonical_bytes(envelope)).hex() == g["event"]["leaf_hash"]
    crow = g["checkpoint"]["row"]
    checkpoint = {
        "v": 1, "log_ref": g["checkpoint"]["log_ref"], "tree_size": crow["tree_size"], "root_hash": crow["root_hash"],
        "previous_root_hash": crow["previous_root_hash"], "signed_at": iso_ms(crow["signed_at"]),
    }
    assert canonical_bytes(checkpoint).decode("utf-8") == g["checkpoint"]["canonical"]


def test_non_ascii_payload_passes_the_content_step():
    receipt = make_receipt({"name": "Muñoz", "note": "日本語 – café", "emoji": "\U0001f37d"})
    report = verify_receipt(receipt)
    assert report.ok and statuses(report)["content"] == "pass"
    receipt["payload"]["data"]["name"] = "Munoz"
    assert statuses(verify_receipt(receipt))["content"] == "fail"


# 5. result line and not_checked

def test_report_names_what_was_not_checked():
    assert verify_receipt(GOLDEN).not_checked == ["key_trust", "anchor"]
    both = {GOLDEN["emitter"]["key_id"], GOLDEN["checkpoint"]["key_id"]}
    assert verify_receipt(GOLDEN, trusted_keys=both).not_checked == ["anchor"]
    erased = fresh()
    erased["payload"] = {"erased": True}
    assert verify_receipt(erased).not_checked == ["content", "key_trust", "anchor"]  # erased content was not checked either
    assert VerifyReport([VerifyStep("a", "pass", "")]).not_checked == []


def test_result_line():
    assert result_line(VerifyReport([VerifyStep("a", "pass", "")])) == "RESULT: ok"
    assert result_line(verify_receipt(GOLDEN)) == "RESULT: ok (not checked: key_trust, anchor)"
    bad = fresh()
    bad["event"]["seq"] = 4
    assert result_line(verify_receipt(bad)) == "RESULT: FAILED"


def test_cli_prints_the_result_line(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(GOLDEN), encoding="utf-8")
    assert main(["verify", str(good)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "RESULT: ok (not checked: key_trust, anchor)"
    ids = [GOLDEN["emitter"]["key_id"], GOLDEN["checkpoint"]["key_id"]]
    assert main(["verify", str(good), "--trusted-key", ids[0], "--trusted-key", ids[1]]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "RESULT: ok (not checked: anchor)"


# 1. duplicate keys

def _write_with_duplicate(tmp_path, where: str) -> Path:
    text = json.dumps(GOLDEN)
    if where == "top":
        text = text.replace('"version": 1,', '"version": 1, "version": 2,', 1)
    elif where == "event":
        text = text.replace('"seq": 3,', '"seq": 3, "seq": 4,', 1)
    else:
        text = text.replace('"salt":', '"salt": "00", "salt":', 1)
    assert text != json.dumps(GOLDEN)
    path = tmp_path / ("dup_%s.json" % where)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("where,key", [("top", "version"), ("event", "seq"), ("payload", "salt")])
def test_cli_rejects_duplicate_keys(tmp_path, capsys, where, key):
    assert main(["verify", str(_write_with_duplicate(tmp_path, where))]) == 1
    captured = capsys.readouterr()
    assert key in captured.err and "duplicate" in captured.err.lower()
    assert "RESULT" not in captured.out


# 6. small ones

def test_cli_reads_a_file_saved_with_a_bom(tmp_path, capsys):
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(GOLDEN).encode("utf-8"))
    assert main(["verify", str(path)]) == 0
    capsys.readouterr()


def test_timestamp_with_non_ascii_digits_is_rejected():
    r = fresh()
    r["event"]["occurred_at"] = r["event"]["occurred_at"].replace("2026", "٢٠٢٦")
    assert statuses(verify_receipt(r))["format"] == "fail"
    r = fresh()
    r["checkpoint"]["signed_at"] = r["checkpoint"]["signed_at"].replace("12:10", "١٢:10")
    assert statuses(verify_receipt(r))["format"] == "fail"


def test_report_without_steps_is_not_ok():
    assert not VerifyReport([]).ok


def test_decimals_fail_only_the_content_step():
    r = fresh()
    r["payload"]["data"]["party_size"] = 4.5
    failed = {s.name for s in verify_receipt(r).steps if s.status == "fail"}
    assert failed == {"content"}


# ---------------------------------------------------------------------------
# final review: verify_mandate (the event's mandate_ref against a mandate.granted receipt)
# ---------------------------------------------------------------------------

import hmac as _hmac_mod  # noqa: E402

from vottun_compliance import ledger as ledger_pkg  # noqa: E402

MANDATE = VECTORS["mandate"]
MANDATE_DATA = dict({"v": 1}, **MANDATE["input_row"])
OTHER_EMITTER = key_from_seed("07" * 32)
OTHER_LOG = key_from_seed("08" * 32)
MANDATE_STEPS = ("mandate_payload", "mandate_type", "mandate_log", "mandate_order", "mandate_ref")


def make_log_receipts(leaves, emitter=EMITTER_KEY, log=LOG_KEY) -> list:
    """Receipts for every leaf of one log under one checkpoint, signed here with test seeds.

    `leaves` is a list of (event fields over the golden event, payload data, salt hex)."""
    events = []
    for fields, data, salt in leaves:
        event = dict(GOLDEN["event"], **fields)
        event["commitment"] = _hmac_mod.new(bytes.fromhex(salt), canonical_bytes(data), hashlib.sha256).hexdigest()
        events.append(event)
    hashes = [leaf_hash(canonical_bytes(e)) for e in events]
    cp = {"v": 1, "log_ref": events[0]["log_ref"], "tree_size": len(hashes), "root_hash": _root(hashes).hex(),
          "previous_root_hash": None, "signed_at": "2026-10-30T12:10:00.456Z"}
    signed_cp = dict(cp, key_id=log[2], public_key=log[1], signature=log[0].sign(canonical_bytes(cp)).hex())
    receipts = []
    for i, (event, (_, data, salt)) in enumerate(zip(events, leaves)):
        receipts.append({
            "version": 1, "event": event, "leaf_hash": hashes[i].hex(), "leaf_index": i,
            "emitter": {"key_id": emitter[2], "public_key": emitter[1], "signature": emitter[0].sign(hashes[i]).hex()},
            "checkpoint": dict(signed_cp), "inclusion_proof": [p.hex() for p in _path(i, hashes)],
            "anchor": None, "payload": {"salt": salt, "data": copy.deepcopy(data)},  # tests mutate it
        })
    return receipts


GRANTED_EVENT = {
    "event_id": "aaaaaaaa-0000-4000-8000-000000000001", "event_type": "mandate.granted", "actor": "user:u-42",
    "seq": 1, "prev_hash": "0" * 64, "mandate_ref": MANDATE["mandate_ref"],
}
BOOKING_EVENT = {
    "event_id": "aaaaaaaa-0000-4000-8000-000000000002", "event_type": "reservation.created",
    "seq": 1, "prev_hash": "0" * 64, "mandate_ref": MANDATE["mandate_ref"],
}
GRANTED_LEAF = (GRANTED_EVENT, MANDATE_DATA, "11" * 32)
BOOKING_LEAF = (BOOKING_EVENT, {"reservation_id": "r1", "party_size": 4}, "22" * 32)


def mandate_pair():
    """(event receipt, mandate receipt): the mandate at leaf 0, the booking that cites it at leaf 1."""
    granted, booking = make_log_receipts([GRANTED_LEAF, BOOKING_LEAF])
    return booking, granted


def mandate_statuses(report) -> dict:
    return {s.name: s.status for s in report.steps if s.name.startswith("mandate")}


def test_mandate_vector_is_the_payload_of_the_granted_event():
    assert hashlib.sha256(canonical_bytes(MANDATE_DATA)).hexdigest() == MANDATE["mandate_ref"]
    assert canonical_bytes(MANDATE_DATA).decode("utf-8") == MANDATE["canonical_utf8"]


def test_verify_mandate_is_exported():
    assert "verify_mandate" in ledger_pkg.__all__ and callable(ledger_pkg.verify_mandate)


def test_a_real_pair_passes_every_mandate_step():
    event, mandate = mandate_pair()
    assert verify_receipt(event).ok and verify_receipt(mandate).ok
    report = ledger_pkg.verify_mandate(event, mandate)
    assert report.ok, [(s.name, s.status, s.detail) for s in report.steps if s.status == "fail"]
    assert {name: mandate_statuses(report)[name] for name in MANDATE_STEPS} == {n: "pass" for n in MANDATE_STEPS}
    # the event receipt's own steps come first, unchanged
    assert [s.name for s in report.steps[:10]] == [s.name for s in verify_receipt(event).steps]
    assert "mandate_receipt.content" in mandate_statuses(report)


def test_a_real_pair_with_trusted_keys():
    event, mandate = mandate_pair()
    report = ledger_pkg.verify_mandate(event, mandate, trusted_keys={EMITTER_KEY[2], LOG_KEY[2]})
    assert report.ok
    assert statuses(report)["key_trust"] == "pass" and statuses(report)["mandate_receipt.key_trust"] == "pass"
    assert report.not_checked == ["anchor", "mandate_receipt.anchor"]
    # an iterator of keys is read once and used for both receipts
    assert ledger_pkg.verify_mandate(event, mandate, trusted_keys=iter([EMITTER_KEY[2], LOG_KEY[2]])).ok


def test_event_without_mandate_ref_is_not_checked():
    granted, booking = make_log_receipts([GRANTED_LEAF, (dict(BOOKING_EVENT, mandate_ref=None),) + BOOKING_LEAF[1:]])
    report = ledger_pkg.verify_mandate(booking, granted)
    assert mandate_statuses(report) == {"mandate": "not_checked"}
    assert report.ok and "mandate" in report.not_checked


def _failed(report) -> set:
    return {s.name for s in report.steps if s.status == "fail"}


def test_event_receipt_that_fails_fails_the_mandate():
    event, mandate = mandate_pair()
    event["event"]["seq"] = 2
    report = ledger_pkg.verify_mandate(event, mandate)
    assert not report.ok and "mandate" in _failed(report)
    assert "pass" not in mandate_statuses(report).values()


def test_mandate_receipt_that_fails_its_own_check_fails():
    event, mandate = mandate_pair()
    mandate["emitter"]["signature"] = flip_hex(mandate["emitter"]["signature"])
    report = ledger_pkg.verify_mandate(event, mandate)
    assert not report.ok
    assert {"mandate_receipt.emitter_signature", "mandate"} <= _failed(report)
    assert "pass" not in {v for k, v in mandate_statuses(report).items() if k in MANDATE_STEPS}


def test_mandate_receipt_content_that_does_not_match_fails():
    event, mandate = mandate_pair()
    mandate["payload"]["data"]["limits"]["max_party_size"] = 80
    report = ledger_pkg.verify_mandate(event, mandate)
    assert not report.ok and {"mandate_receipt.content", "mandate"} <= _failed(report)


def test_mandate_receipt_without_payload_fails():
    event, mandate = mandate_pair()
    del mandate["payload"]
    report = ledger_pkg.verify_mandate(event, mandate)
    assert not report.ok and {"mandate_payload", "mandate_ref"} <= _failed(report)


def test_mandate_receipt_with_erased_payload_fails():
    event, mandate = mandate_pair()
    mandate["payload"] = {"erased": True}
    report = ledger_pkg.verify_mandate(event, mandate)
    assert not report.ok and {"mandate_payload", "mandate_ref"} <= _failed(report)


def test_receipt_that_is_not_a_mandate_granted_fails():
    granted, booking = make_log_receipts([(dict(GRANTED_EVENT, event_type="mandate.approved"),) + GRANTED_LEAF[1:], BOOKING_LEAF])
    report = ledger_pkg.verify_mandate(booking, granted)
    assert _failed(report) == {"mandate_type"}


def test_mandate_from_another_log_fails():
    event, _ = mandate_pair()
    other = make_log_receipts([(dict(GRANTED_EVENT, log_ref="lg_" + "f" * 16),) + GRANTED_LEAF[1:]])[0]
    report = ledger_pkg.verify_mandate(event, other)
    assert _failed(report) == {"mandate_log"}


def test_mandate_recorded_after_the_event_fails():
    booking, granted = make_log_receipts([BOOKING_LEAF, GRANTED_LEAF])
    report = ledger_pkg.verify_mandate(booking, granted)
    assert _failed(report) == {"mandate_order"}


def test_mandate_at_the_same_index_fails():
    event, _ = mandate_pair()
    other = make_log_receipts([GRANTED_LEAF, (dict(GRANTED_EVENT, event_id="aaaaaaaa-0000-4000-8000-000000000009"),) + GRANTED_LEAF[1:]])[1]
    assert other["leaf_index"] == event["leaf_index"] == 1
    report = ledger_pkg.verify_mandate(event, other)
    assert _failed(report) == {"mandate_order"}


def test_mandate_that_does_not_hash_to_the_cited_ref_fails():
    granted, booking = make_log_receipts([GRANTED_LEAF, (dict(BOOKING_EVENT, mandate_ref="ab" * 32),) + BOOKING_LEAF[1:]])
    report = ledger_pkg.verify_mandate(booking, granted)
    assert _failed(report) == {"mandate_ref"}


def test_mandate_signed_with_untrusted_keys_fails():
    event, _ = mandate_pair()
    granted = make_log_receipts([GRANTED_LEAF, BOOKING_LEAF], emitter=OTHER_EMITTER, log=OTHER_LOG)[0]
    assert ledger_pkg.verify_mandate(event, granted).ok  # without trusted keys the keys are not compared
    report = ledger_pkg.verify_mandate(event, granted, trusted_keys={EMITTER_KEY[2], LOG_KEY[2]})
    assert not report.ok and {"mandate_receipt.key_trust", "mandate"} <= _failed(report)


@pytest.mark.parametrize("garbage", [None, {}, [], "mandate", {"version": 1}])
def test_malformed_mandate_receipt_fails_without_crashing(garbage):
    event, _ = mandate_pair()
    report = ledger_pkg.verify_mandate(event, garbage)
    assert not report.ok and "mandate" in _failed(report)


# CLI --mandate-receipt

def _write(tmp_path, name, obj) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def test_cli_with_mandate_receipt(tmp_path, capsys):
    event, mandate = mandate_pair()
    args = ["verify", _write(tmp_path, "event.json", event), "--mandate-receipt", _write(tmp_path, "m.json", mandate)]
    assert main(args + ["--trusted-key", EMITTER_KEY[2], "--trusted-key", LOG_KEY[2]]) == 0
    out = capsys.readouterr().out
    for step in MANDATE_STEPS:
        assert step in out
    assert "version 2" in out and "user:u-42" in out and "\"max_party_size\": 8" in out
    assert MANDATE["input_row"]["justification"] in out
    assert out.splitlines()[-1] == "RESULT: ok (not checked: anchor, mandate_receipt.anchor)"


def test_cli_with_a_mandate_that_does_not_match(tmp_path, capsys):
    granted, booking = make_log_receipts([GRANTED_LEAF, (dict(BOOKING_EVENT, mandate_ref="ab" * 32),) + BOOKING_LEAF[1:]])
    args = ["verify", _write(tmp_path, "event.json", booking), "--mandate-receipt", _write(tmp_path, "m.json", granted)]
    assert main(args) == 1
    out = capsys.readouterr().out
    assert "mandate_ref" in out and out.splitlines()[-1] == "RESULT: FAILED"


def test_cli_with_an_unreadable_mandate_receipt(tmp_path, capsys):
    event, _ = mandate_pair()
    good = _write(tmp_path, "event.json", event)
    assert main(["verify", good, "--mandate-receipt", str(tmp_path / "missing.json")]) == 1
    dup = tmp_path / "dup.json"
    dup.write_text(json.dumps(event).replace('"seq": 1,', '"seq": 1, "seq": 2,', 1), encoding="utf-8")
    assert main(["verify", good, "--mandate-receipt", str(dup)]) == 1
    captured = capsys.readouterr()
    assert "duplicate" in captured.err.lower() and "RESULT" not in captured.out
