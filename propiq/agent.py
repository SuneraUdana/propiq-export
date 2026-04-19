"""PropIQ — Planner → Tool-Use → Reflection state machine (LangGraph pattern)"""
import time, traceback
from collections import defaultdict

MAX_RETRIES = 3

class AgentState(dict):
    def __init__(self):
        super().__init__(task_queue=[],completed=[],records=[],enriched=[],
                         weights=None,scored=[],report_path=None,
                         retries=0,ok=False,log=[],failed_tasks=[])
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self["log"].append(f"[{ts}] {msg}")
        print(f"  [agent] {msg}")


def planner(state, target_suburbs):
    state.log(f"Planner activated → {target_suburbs}")
    state["task_queue"] = [
        {"name":"ingest",   "args":{"suburbs":target_suburbs}, "attempts":0},
        {"name":"enrich",   "args":{},                         "attempts":0},
        {"name":"optimise", "args":{},                         "attempts":0},
        {"name":"score",    "args":{},                         "attempts":0},
        {"name":"report",   "args":{},                         "attempts":0},
    ]
    return state


def tool_use(state):
    if not state["task_queue"]:
        state["ok"] = True
        return state

    task = state["task_queue"].pop(0)
    name = task["name"]
    task["attempts"] += 1
    state.log(f"Executing task: {name} (attempt {task['attempts']}/{MAX_RETRIES})")

    try:
        if name == 'ingest':
            from propiq.simulator import simulate_listings, clean_records
            state['records'] = clean_records(simulate_listings())

        elif name == 'enrich':
            from propiq.enrichment import enrich_batch
            from propiq.storage import upsert_listings
            upsert_listings(state['records'])          # ← SAVE listings to DB
            state['enriched'] = enrich_batch(state['records'], verbose=True)

        elif name == 'optimise':
            from propiq.optimizer import optimise_weights, compute_features
            from propiq.storage import upsert_enrichments
            upsert_enrichments(state['enriched'])      # ← SAVE enrichments to DB
            import numpy as np
            records = state['enriched']
            sub_prices = defaultdict(list)
            for r in records:
                if r.get('sale_price'):
                    sub_prices[r['suburb']].append(r['sale_price'])
            sub_med = {s: np.median(v) for s, v in sub_prices.items()}
            all_feats = [compute_features(r, sub_med.get(r['suburb'], 1_000_000)) for r in records]
            state['weights'] = optimise_weights(all_feats, verbose=True)

        elif name == 'score':
            from propiq.optimizer import score_and_rank
            from propiq.storage import upsert_scores
            state['scored'] = score_and_rank(state['enriched'], weights=state['weights'])
            upsert_scores(state['scored'])             # ← SAVE scores to DB

        elif name == 'report':
            from propiq.reporter import generate_report
            state['report_path'] = generate_report(state['scored'])

        state["completed"].append(name)
        state.log(f"Task '{name}' completed ✓")

    except Exception as ex:
        state.log(f"Task '{name}' FAILED (attempt {task['attempts']}): {ex}")
        traceback.print_exc()
        if task["attempts"] < MAX_RETRIES:
            state.log(f"Retrying '{name}' ({task['attempts']}/{MAX_RETRIES})...")
            state["task_queue"].insert(0, task)   # retry
        else:
            state.log(f"Task '{name}' gave up after {MAX_RETRIES} attempts — skipping.")
            state["failed_tasks"].append({"task": name, "error": str(ex)})

    return state


def reflector(state):
    checks = {
        "records_loaded":  len(state["records"]) > 0,
        "enrichment_done": len(state["enriched"]) == len(state["records"]),
        "weights_exist":   state["weights"] is not None,
        "scored_gt_zero":  len(state["scored"]) > 0,
        "report_generated":state["report_path"] is not None,
    }
    failed = [k for k,v in checks.items() if not v]
    if failed:
        state["retries"] += 1
        state.log(f"Reflection FAILED: {failed}  (retry {state['retries']}/{MAX_RETRIES})")
        state["ok"] = False
    else:
        state.log("Reflection PASSED all checks ✓")
        state["ok"] = True
    return state


def run_pipeline(target_suburbs):
    state = AgentState()
    print("\n" + "═"*60 + "\n PropIQ Agentic Pipeline — Starting\n" + "═"*60)
    state = planner(state, target_suburbs)

    # Execute all tasks (each has its own retry counter)
    while state["task_queue"]:
        state = tool_use(state)

    # Reflect on final state
    state = reflector(state)

    # If reflection fails, re-queue only the failed checks (not all tasks)
    while not state["ok"] and state["retries"] < MAX_RETRIES:
        while state["task_queue"]:
            state = tool_use(state)
        state = reflector(state)

    # Summary
    status = "✓ SUCCESS" if state["ok"] else "✗ FAILED after max retries"
    if state["failed_tasks"]:
        print(f"  [agent] Skipped tasks: {[t['task'] for t in state['failed_tasks']]}")
    print("═"*60 + f"\n Pipeline: {status}\n Report  : {state['report_path']}\n" + "═"*60 + "\n")
    return state
