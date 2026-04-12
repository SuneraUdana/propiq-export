"""
PropIQ — Entry point
Usage:
  python -m propiq.main
  python -m propiq.main --suburbs Fitzroy Richmond Hawthorn
  python -m propiq.main --mode scrape
"""
import argparse
from propiq.storage import init_db
from propiq.config  import TARGET_SUBURBS
from propiq.agent   import run_pipeline

def main():
    p = argparse.ArgumentParser(description="PropIQ — Autonomous Property Advisor")
    p.add_argument("--suburbs", nargs="+", default=TARGET_SUBURBS)
    p.add_argument("--mode", default="simulate", choices=["simulate","scrape"])
    args = p.parse_args()
    init_db()
    state = run_pipeline(args.suburbs)
    if state["ok"]:
        print(f"\n✅ PropIQ complete.")
        print(f"   Report: {state['report_path']}")
        print(f"   Top:    {state['scored'][0]['address']} — {state['scored'][0]['inv_score']:.4f}")

if __name__ == "__main__":
    main()
