"""
Quick smoke-test for the Responses API path (foundry_grounded_agent.py).
Run from repo root:
    python scripts/test_responses_api.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Override settings so Responses API is enabled
os.environ.setdefault("FOUNDRY_USE_RESPONSES_API", "true")

async def main():
    from backend.core.foundry_grounded_agent import responses_api_enabled, call_grounded_agent

    print("=== Responses API smoke-test ===")
    print(f"responses_api_enabled() -> {responses_api_enabled()}")

    if not responses_api_enabled():
        print("\n[SKIP] Not enabled — check MODEL_BACKEND=azure_foundry and AZURE_AI_PROJECT_ENDPOINT")
        return

    messages = [
        {
            "role": "system",
            "content": "You are eciq-assessment-agent. Answer concisely.",
        },
        {
            "role": "user",
            "content": (
                "For AZ-204 (Azure Developer Associate), name ONE core topic the learner "
                "should study and why it appears in the exam. Cite your source."
            ),
        },
    ]

    print("\nCalling assessment agent via Responses API...")
    result = await call_grounded_agent("assessment", messages, run_id="smoke-test-001")

    if result is None:
        print("\n[FAIL] call_grounded_agent returned None — check logs above for the error.")
        sys.exit(1)

    print(f"\n[OK] Got AgentResult:")
    print(f"  agent_name : {result.agent_name}")
    print(f"  chars      : {len(result.content)}")
    print(f"  tool_calls : {result.tool_calls_made}")
    print(f"\n--- content (first 600 chars) ---")
    print(result.content[:600])

asyncio.run(main())
