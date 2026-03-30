# Examples

Quick runnable scripts for the Vottun AI Compliance SDKs.

## Contents

- `python_certify_and_verify.py` (SDK basic certify + verify)
- `typescript_certify.ts` (TypeScript SDK basic certify + verify)
- `langchain_integration.ipynb` (LangChain integration example)
- `crewai_autogen_example.py` (CrewAI / AutoGen example)
- `langgraph_verify_before_publish.py` (LangGraph compliance gating example)

## Quick run

- For Python examples, first install the SDK: `pip install -e sdk-python`.
- For framework-specific examples, install the corresponding framework dependencies (LangChain/LangGraph/CrewAI/AutoGen) as needed.

### Run the SDK-only scripts

```bash
cd ..
python3 examples/python_certify_and_verify.py
python3 examples/crewai_autogen_example.py
python3 examples/langgraph_verify_before_publish.py
```

Notes:
- `langgraph_verify_before_publish.py` runs the SDK workflow even if `langgraph` isn’t installed (LangGraph demo is optional).
- `crewai_autogen_example.py` runs the SDK workflow even if CrewAI/AutoGen aren’t installed (integration skeletons are optional).

### LangChain notebook

Open `examples/langchain_integration.ipynb` in your notebook environment (Jupyter, Cursor Notebook, etc.) and run cells.

