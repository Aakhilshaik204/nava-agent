"""
cleanup_old_agents.py
Deletes the old agent files that have been replaced by cleaner named versions.

Old → New:
  dynamic_graph.py        → nava_agent.py
  universal_agent.py      → file_agent.py
  tier1_agents.py         → file_agent_variants.py
  universal_agent_prompt  → file_agent_prompt.txt
"""
import os

BASE = os.path.join(os.path.dirname(__file__), "src", "nava")

FILES_TO_DELETE = [
    os.path.join(BASE, "agents", "runtime", "dynamic_graph.py"),
    os.path.join(BASE, "agents", "runtime", "universal_agent.py"),
    os.path.join(BASE, "agents", "runtime", "tier1_agents.py"),
    os.path.join(BASE, "prompts", "universal_agent_prompt.txt"),
]

print("=" * 50)
print("  NAVA — Deleting old renamed agent files")
print("=" * 50)

for path in FILES_TO_DELETE:
    if os.path.exists(path):
        os.remove(path)
        print(f"  ✅ Deleted: {os.path.relpath(path)}")
    else:
        print(f"  ⚠️  Already gone: {os.path.relpath(path)}")

print()
print("Done. Remaining agent files:")
runtime_dir = os.path.join(BASE, "agents", "runtime")
for f in sorted(os.listdir(runtime_dir)):
    if f.endswith(".py") and not f.startswith("__"):
        print(f"  → {f}")

print()
print("Remaining prompt files:")
prompts_dir = os.path.join(BASE, "prompts")
for f in sorted(os.listdir(prompts_dir)):
    print(f"  → {f}")
