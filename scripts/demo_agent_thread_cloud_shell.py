"""
EnterpriseCertIQ — Send a demo message to an agent and print the response.

Run in Azure Cloud Shell after register_agents_cloud_shell.py.
The thread shows up under Foundry portal → Agents → <agent> → Threads.

Usage:
    python demo_agent_thread_cloud_shell.py
    python demo_agent_thread_cloud_shell.py --agent eciq-assessment-agent --prompt "Generate 3 practice questions for AZ-204 Function Apps"
"""
from __future__ import annotations

import argparse
import sys
import time

PROJECT_ENDPOINT = "https://agenticaifoundrypoc.services.ai.azure.com/api/projects/aipoc"
MODEL_DEPLOYMENT = "gpt-4.1"

DEMO_PROMPTS = {
    "eciq-orchestrator": (
        "Learner L-1004 is a Cloud Engineer targeting AZ-204 with 14 hours studied so far "
        "and 22 meeting hours per week. Run a full readiness assessment."
    ),
    "eciq-learning-path-curator": (
        "Curate a learning path for AZ-204 (Azure Developer Associate) for a Cloud Engineer "
        "with strong Python skills but limited Azure Functions experience."
    ),
    "eciq-study-plan-generator": (
        "Generate a 3-week study plan for AZ-204. The learner has 8 free hours per week "
        "and the exam is in 21 days."
    ),
    "eciq-readiness-critic": (
        "Critique this study plan: Week 1 — Azure Functions (3h), Week 2 — Blob Storage (2h), "
        "Week 3 — Cosmos DB (2h). Is the coverage sufficient for AZ-204?"
    ),
    "eciq-engagement-agent": (
        "Learner EMP-004 has 22 meeting hours/week and prefers morning study slots. "
        "Recommend a weekly study schedule and reminder timing."
    ),
    "eciq-assessment-agent": (
        "Generate 3 grounded practice questions for AZ-204, focusing on Azure Functions "
        "and Durable Functions. Cite the knowledge source for each question."
    ),
    "eciq-manager-insights": (
        "Summarise team certification readiness for a 6-person Cloud Engineering team. "
        "3 members are targeting AZ-204, 2 are targeting AZ-305, 1 is targeting AZ-400."
    ),
    "eciq-retrospective": (
        "Learner L-1004 failed AZ-204 with a score of 680 (passing is 700). "
        "They studied 14 hours over 3 weeks. Diagnose the failure and recommend a recovery plan."
    ),
}


def run_demo(agent_name: str, prompt: str) -> None:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    print(f"\nAgent : {agent_name}")
    print(f"Prompt: {prompt[:120]}{'...' if len(prompt) > 120 else ''}\n")

    # Create thread and run
    thread = client.agents.create_thread()
    client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content=prompt,
    )

    # Resolve agent id
    agents = {a.name: a for a in client.agents.list_agents()}
    if agent_name not in agents:
        print(f"Agent '{agent_name}' not found. Run register_agents_cloud_shell.py first.")
        sys.exit(1)
    agent_id = agents[agent_name].id

    run = client.agents.create_run(thread_id=thread.id, assistant_id=agent_id)
    print(f"Thread: {thread.id}")
    print(f"Run   : {run.id}  (status: {run.status})")
    print("Waiting for response", end="", flush=True)

    # Poll until complete
    for _ in range(60):
        time.sleep(2)
        run = client.agents.get_run(thread_id=thread.id, run_id=run.id)
        print(".", end="", flush=True)
        if run.status in ("completed", "failed", "cancelled", "expired"):
            break

    print(f"  [{run.status}]\n")

    if run.status != "completed":
        print(f"Run did not complete successfully (status={run.status}).")
        return

    messages = client.agents.list_messages(thread_id=thread.id)
    for msg in reversed(list(messages)):
        if msg.role == "assistant":
            for block in msg.content:
                text = getattr(block, "text", None)
                if text:
                    value = getattr(text, "value", str(text))
                    print("─" * 72)
                    print(value)
                    print("─" * 72)
            break

    print(
        f"\nView in portal:\n"
        f"  https://ai.azure.com/  → project 'aipoc' → Agents → {agent_name} → Threads → {thread.id}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a demo message to a Foundry agent.")
    parser.add_argument(
        "--agent", default="eciq-assessment-agent",
        choices=list(DEMO_PROMPTS.keys()),
        help="Which agent to call (default: eciq-assessment-agent)",
    )
    parser.add_argument("--prompt", default=None, help="Custom prompt (optional).")
    args = parser.parse_args()

    try:
        import azure.ai.projects  # noqa: F401
    except ImportError:
        print("Run: pip install azure-ai-projects azure-identity --quiet")
        sys.exit(1)

    prompt = args.prompt or DEMO_PROMPTS[args.agent]
    run_demo(args.agent, prompt)
