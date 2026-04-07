import os

import gradio as gr

from vottun_compliance import VottunComplianceClient


def certify_and_verify_text(text: str) -> str:
    if not text.strip():
        return "Please provide some text."

    base_url = os.getenv("AIACT50_API_BASE_URL")
    api_key = os.getenv("AIACT50_API_KEY")

    if base_url:
        client = VottunComplianceClient(base_url=base_url, api_key=api_key if api_key else None)
    else:
        client = VottunComplianceClient(api_key=api_key if api_key else None)

    cert = client.certify_content(content=text, ai_system=os.getenv("AIACT50_AI_SYSTEM", "gpt-4o"), watermark=True)
    cert_id = cert.get("cert_id") or cert.get("certificate_id") or ""
    verify = client.verify_certificate(cert_id) if cert_id else None

    verified = False
    if isinstance(verify, dict):
        verified = bool(
            verify.get("success") or verify.get("verified") or verify.get("valid")
            or verify.get("is_valid") or verify.get("on_chain_verified")
            or verify.get("status") == "valid"
        )

    return f"cert_id: {cert_id}\nverified: {verified}\nverify_response: {verify}"


with gr.Blocks(title="Vottun AI Compliance (demo)") as demo:
    gr.Markdown("# Vottun AI Compliance (EU AI Act Art. 50)")
    text = gr.Textbox(lines=6, label="AI-generated text to certify & verify")
    out = gr.Textbox(lines=10, label="Result")
    btn = gr.Button("Certify + verify")
    btn.click(fn=certify_and_verify_text, inputs=[text], outputs=[out])


demo.launch()

