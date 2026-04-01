# Hugging Face Space template (Sprint 3)

This is a lightweight Space template for demonstrating a "certify + verify before publish" workflow.

## Deploy

In your Space repo:

1. Copy `app.py` and `requirements.txt`
2. Set secrets (optional):
   - `AIACT50_API_KEY` (for mainnet / paid mode and authenticated certificate lookup)
   - `AIACT50_API_BASE_URL` (defaults to `https://app.aiact50.com/api`)

Then install dependencies and run:

```bash
pip install -r requirements.txt
python app.py
```

