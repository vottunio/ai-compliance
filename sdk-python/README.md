# Vottun AI Compliance Python SDK

Install:

```bash
pip install vottun-compliance
```

Usage (free testnet mode):

```python
from vottun_compliance import VottunComplianceClient

client = VottunComplianceClient()  # no X-API-Key => free testnet mode

res = client.certify_content(
    content="Hello world",
    ai_system="gpt-4o",
)

print(res)
```

Usage (paid/mainnet mode):

```python
client = VottunComplianceClient(api_key="YOUR_API_KEY")
cert = client.certify_content(content="Hello", ai_system="gpt-4o")
detail = client.get_certificate(cert["cert_id"] or cert["certificate_id"])
print(detail)
```

## Local testing (localhost:8000)

Assuming `vottun-ai-backend` is running at `http://localhost:8000`.

```bash
cd sdk-python
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

```bash
python3 -c "
from vottun_compliance import VottunComplianceClient
client = VottunComplianceClient(base_url='http://localhost:8000/api')
cert = client.certify_content(content='Hello world', ai_system='gpt-4o', watermark=True)
cid = cert.get('cert_id') or cert.get('certificate_id')
print('cert:', cert)
print('verify:', client.verify_certificate(cid))
"
```

