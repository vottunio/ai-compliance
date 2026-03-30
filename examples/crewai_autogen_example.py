"""
CrewAI / AutoGen integration example (Sprint 3).

This file is designed to be safe to run even if CrewAI/AutoGen are not installed:
- It always demonstrates the core Vottun Compliance SDK workflow (certify -> verify).
- It includes integration skeletons for CrewAI and AutoGen that you can enable by
  installing the corresponding packages.
"""

from __future__ import annotations

import os
from typing import Any

from vottun_compliance import VottunComplianceClient


def certify_and_verify(content: str, ai_system: str = "gpt-4o") -> dict[str, Any]:
    """
    Core compliance workflow:
    1) Certify content (server-side watermarking is requested via watermark=True)
    2) Verify the resulting certificate id
    """

    client = VottunComplianceClient()  # free testnet mode (no X-API-Key)
    cert = client.certify_content(content=content, ai_system=ai_system, watermark=True)
    cert_id = cert.get("cert_id") or cert.get("certificate_id")
    verify = client.verify_certificate(cert_id) if cert_id else None
    return {"cert": cert, "cert_id": cert_id, "verify": verify}


def main() -> None:
    content = "This is example AI-generated text that we want to certify."
    ai_system = os.getenv("VOTTUN_AI_SYSTEM", "gpt-4o")

    print("Running SDK workflow (certify -> verify)...")
    result = certify_and_verify(content=content, ai_system=ai_system)
    print("cert_id:", result["cert_id"])
    print("verify:", result["verify"])

    # Optional: CrewAI skeleton
    if os.getenv("RUN_CREWAI_DEMO") == "1":
        try:
            from crewai import Agent  # type: ignore
        except Exception as e:  # pragma: no cover
            raise SystemExit(
                "CrewAI not installed. Install it and re-run with RUN_CREWAI_DEMO=1.\n"
                f"Original error: {e}"
            )

        # Note:
        # CrewAI typically requires an LLM and a way to expose tools.
        # This skeleton shows where you would plug in `certify_and_verify`
        # as a callable tool for an agent.
        #
        # You must:
        # - configure an LLM for CrewAI
        # - expose `certify_and_verify` via CrewAI's tool integration (package/tooling varies)
        print(
            "\n[CREWAI SKELETON]\n"
            "- Install and configure CrewAI + an LLM.\n"
            "- Wrap `certify_and_verify` into a CrewAI tool.\n"
            "- Create an agent that calls the tool before publishing.\n"
        )

    # Optional: AutoGen skeleton
    if os.getenv("RUN_AUTOGEN_DEMO") == "1":
        try:
            import autogen  # type: ignore
        except Exception as e:  # pragma: no cover
            raise SystemExit(
                "AutoGen not installed. Install it and re-run with RUN_AUTOGEN_DEMO=1.\n"
                f"Original error: {e}"
            )

        print(
            "\n[AUTOGEN SKELETON]\n"
            "- Configure an AutoGen agent + LLM.\n"
            "- Register a tool that calls `certify_and_verify`.\n"
            "- Have the assistant call the tool to decide if content is compliant.\n"
        )


if __name__ == "__main__":
    main()

