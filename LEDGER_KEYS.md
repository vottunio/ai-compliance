# AI Ledger — Vottun public signing keys

These are the public Ed25519 keys Vottun uses to sign AI Ledger receipts. Publishing them here, in a public repository with its own history, gives anyone checking a receipt a second source for the keys that does not depend on Vottun's servers.

They are public keys: they can only check signatures, not make them. The private keys never leave the Vottun backend.

## Keys in use

| key_id | Kind | Signs | Algorithm | Public key (raw, hex) | Valid from (UTC) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `d636d8a4f1749c3b` | emitter | every event | Ed25519 | `61a0d7fbd084e0d9f4dfca5ec4c5805b8d1f4d894bdf375ca495c7f5ba8175a0` | 2026-11-17 15:14:04 | active |
| `fd91122e3045056e` | log | every checkpoint | Ed25519 | `5b83ecd4e8504c310f9211fbc194f811a172efc6435ad0fbc45db439c5c70f33` | 2026-11-17 15:16:45 | active |

The `key_id` is the first 16 hex characters of the SHA-256 of the raw 32-byte public key, so you can recompute it yourself.

The same keys are served live at:

```
https://app.aiact50.com/api/v1/ledger/public-keys
```

If that endpoint and this file ever disagree, do not trust either until it is explained.

## Verify a receipt

Install the verifier from this repository (Python 3.9 or later), pinned to a release tag or a commit you have
reviewed. Never install from a moving branch such as `develop` or `main`: what you verify with would change under you.

```bash
pip install "git+https://github.com/vottunio/ai-compliance.git@<tag-or-commit-sha>#subdirectory=sdk-python"
```

`<tag-or-commit-sha>` is a release tag (when releases are tagged) or the full 40-character commit sha of the
version you checked.

Then pass both key ids as trusted keys:

```bash
vottun-ledger verify receipt.json --trusted-key d636d8a4f1749c3b --trusted-key fd91122e3045056e
```

If the `vottun-ledger` command is not on your PATH, run `python -m vottun_compliance.ledger.cli` with the same arguments.

The verifier checks the format, the key ids, the event hash, the emitter signature, the checkpoint signature, that the event is in the signed tree, and that the payload matches what was committed. With `--trusted-key` it also checks that both keys are in this list (`key_trust`). Without it, a receipt signed with somebody else's keys could still pass every other check.

To check the mandate a receipt cites, add `--mandate-receipt mandate.json` with the receipt of that `mandate.granted` event.

Receipts can carry an `anchor` since verifier 0.3.2 (an older verifier accepts it without checking it). When the
checkpoint of a receipt was anchored, the verifier always checks the batch proof from the checkpoint to the
anchored root; with `--rpc URL` (an RPC of the anchor's network) it also checks the transaction on chain, and
`--anchor-contract ADDRESS` requires the contract Vottun publishes for that network. Without `--rpc`, or for a
timestamp-only anchor, the `anchor` step says `not_checked`. A receipt with no anchor (its client chose none, or the
batch is not anchored yet) shows `anchor` as `not_checked` too.

## Key changes

When a key is replaced, the new one is added to this table with its date, and the old one stays listed with the date it stopped being used, so older receipts can still be checked.
