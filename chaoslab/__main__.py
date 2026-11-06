import argparse
import json
import sys
from pathlib import Path
from .core import BookingWorld, SCENARIOS, ToolFault, run_scenario


def main():
    parser = argparse.ArgumentParser(description="Offline agent reliability simulations")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output", type=Path)
    serve = sub.add_parser("serve-jsonl", help="Domain JSONL adapter, NOT the MCP protocol")
    serve.add_argument("--scenario", choices=SCENARIOS, default="clean")
    args = parser.parse_args()
    if args.command == "demo":
        safe = [run_scenario(s) for s in SCENARIOS]
        naive = run_scenario("timeout_after_commit", naive=True)
        report = dict(schema_version=1, reference_policy_runs=safe,
                      intentional_negative_control=naive,
                      passed=all(r["passed"] for r in safe) and not naive["passed"])
        text = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n")
        print(text)
        return 0 if report["passed"] else 1
    world = BookingWorld(args.scenario)
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be an object")
            if request.get("tool") == "snapshot":
                result = world.snapshot()
            else:
                result = world.call(request["tool"], request.get("arguments", {}))
            response = {"result": result}
        except ToolFault as exc:
            response = {"error": exc.as_dict()}
        except (ValueError, TypeError, KeyError) as exc:
            response = {"error": {"code": "INVALID_REQUEST", "message": str(exc)}}
        print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
