from vottun_compliance import VottunComplianceClient


def main() -> None:
    client = VottunComplianceClient()  # free testnet mode (no X-API-Key)

    cert = client.certify_content(
        content="Hello world",
        ai_system="gpt-4o",
    )

    cert_id = cert.get("cert_id") or cert.get("certificate_id")
    print("cert_id:", cert_id)

    if cert_id:
        verified = client.verify_certificate(cert_id)
        print("verify:", verified)


if __name__ == "__main__":
    main()

