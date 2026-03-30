"""
LangGraph compliance gating example (Sprint 3).

Goal: verify compliance (certify + verify) before "publishing".

This script will:
- Always run the SDK workflow if `langgraph` is not installed.
- If `langgraph` is installed, it builds a small StateGraph to demonstrate the pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from vottun_compliance import VottunComplianceClient


class State(TypedDict, total=False):
    content: str
    ai_system: str
    cert_id: str
    certified: bool
    verified: bool


def safe_verified(verify_response: Any) -> bool:
    """
    The backend response shape may evolve; this function does a best-effort boolean extraction.
    """

    if not isinstance(verify_response, dict):
        return False

    # Current backend response often looks like:
    # { status: "valid", on_chain_verified: True, ... }
    status = verify_response.get("status")
    if isinstance(status, str) and status.lower() == "valid":
        return True

    on_chain_verified = verify_response.get("on_chain_verified")
    if isinstance(on_chain_verified, bool) and on_chain_verified:
        return True

    for key in ("success", "verified", "valid", "is_valid"):
        if key in verify_response:
            return bool(verify_response[key])

    # Some APIs nest results.
    for maybe in ("result", "data", "verification"):
        inner = verify_response.get(maybe)
        if isinstance(inner, dict):
            inner_status = inner.get("status")
            if isinstance(inner_status, str) and inner_status.lower() == "valid":
                return True

            inner_on_chain_verified = inner.get("on_chain_verified")
            if isinstance(inner_on_chain_verified, bool) and inner_on_chain_verified:
                return True

            for key in ("success", "verified", "valid", "is_valid"):
                if key in inner:
                    return bool(inner[key])

    return False


def certify_and_verify(client: VottunComplianceClient, content: str, ai_system: str) -> tuple[str, bool, Any]:
    cert = client.certify_content(content=content, ai_system=ai_system, watermark=True)
    cert_id = cert.get("cert_id") or cert.get("certificate_id") or ""
    verify = client.verify_certificate(cert_id) if cert_id else None
    verified = safe_verified(verify)
    return cert_id, verified, verify


def run_without_langgraph(content: str, ai_system: str) -> None:
    client = VottunComplianceClient()
    cert_id, verified, verify = certify_and_verify(client, content, ai_system)

    print("cert_id:", cert_id)
    print("verified:", verified)

    if verified:
        print("Publishing allowed (verification passed).")
    else:
        print("Publishing blocked (verification failed).")
    if verify is not None:
        print("verify response:", verify)


def run_with_langgraph(content: str, ai_system: str) -> None:
    # Optional dependency: only import if installed.
    from langgraph.graph import StateGraph  # type: ignore

    client = VottunComplianceClient()

    def certify_node(state: State) -> State:
        cert_id, verified, _ = certify_and_verify(client, state["content"], state["ai_system"])
        return {
            "cert_id": cert_id,
            "certified": True,
            "verified": verified,
        }

    def publish_node(state: State) -> State:
        if state.get("verified"):
            print("Publishing allowed (verification passed).")
        else:
            print("Publishing blocked (verification failed).")
        return state

    graph = StateGraph(State)
    graph.add_node("certify_and_verify", certify_node)
    graph.add_node("publish", publish_node)
    graph.set_entry_point("certify_and_verify")
    graph.add_edge("certify_and_verify", "publish")

    app = graph.compile()
    initial: State = {"content": content, "ai_system": ai_system}
    app.invoke(initial)


def main() -> None:
    content = "Draft AI-generated text that must be verified before publishing."
    ai_system = "gpt-4o"

    try:
        import langgraph  # noqa: F401  # type: ignore
    except Exception:
        print("langgraph not installed; running SDK workflow only.")
        run_without_langgraph(content=content, ai_system=ai_system)
        return

    run_with_langgraph(content=content, ai_system=ai_system)


if __name__ == "__main__":
    main()

