#!/usr/bin/env python3
"""sentl-monitor's deterministic steps. It reads the Sentl MCP responses the
assistant saved into a study folder and never calls Sentl.

Exit codes: 0 done; 1 check found problems; 2 input refused; 3 run not final;
4 no run left in the period.
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentlmon import adopt, check, ingest, method, period  # noqa: E402
from sentlmon.common import Refused  # noqa: E402


def _parser():
    today = dt.date.today().isoformat()
    p = argparse.ArgumentParser(prog="monitor.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    a = sub.add_parser("adopt", help="take an existing Sentl project into the study folder")
    a.add_argument("--study", default=".", help="study folder (default: current directory)")
    a.add_argument("--project", required=True, help="saved get-project-tool response")
    a.add_argument("--run", help="saved get-run-results-tool response of the latest completed run")
    a.add_argument("--key", help="local key of the project (default: a slug of its name)")

    i = sub.add_parser("ingest", help="store a run's results as a normalized snapshot")
    i.add_argument("--study", default=".")
    i.add_argument("--project", required=True, help="local key of the project")
    src = i.add_mutually_exclusive_group(required=True)
    src.add_argument("--results", help="saved get-run-results-tool response")
    src.add_argument("--unavailable", type=int, metavar="RUN_ID", help="record a run Sentl could not return")
    i.add_argument("--reason", default="server error", help="with --unavailable: the error Sentl returned")

    r = sub.add_parser("period", help="compute the metrics of a report period")
    r.add_argument("--study", default=".")
    r.add_argument("--date", default=today, help="report date, YYYY-MM-DD (default: today)")
    r.add_argument("--models", help="saved list-ai-models response, for public names in the material")

    m = sub.add_parser("method", help="write the report's method sections and its outline")
    m.add_argument("--study", default=".")
    m.add_argument("--date", default=today)
    m.add_argument("--models", required=True, help="saved list-ai-models response")
    m.add_argument("--force", action="store_true", help="overwrite an existing report")

    c = sub.add_parser("check", help="verify a report before it is final")
    c.add_argument("--study", default=".")
    c.add_argument("--date", help="period date (default: from the report's file name)")
    c.add_argument("report", help="the report file")
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "adopt":
            print(adopt.adopt(args.study, args.project, args.run, args.key))
        elif args.command == "ingest":
            if args.unavailable is not None:
                print(ingest.record_unavailable(args.study, args.project, args.unavailable, args.reason))
            else:
                print(ingest.ingest(args.study, args.project, args.results))
        elif args.command == "period":
            print(period.build(args.study, args.date, args.models))
        elif args.command == "method":
            print(method.write(args.study, args.date, args.models, args.force))
        elif args.command == "check":
            problems = check.check(args.study, args.report, args.date)
            if problems:
                print(f"check failed: {len(problems)} problem(s)")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            print("check passed: quotes are verbatim, figures and counts are the period's, sections are in order, "
                  "and no id, key, model id, file name or credit figure appears")
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except ingest.NotFinal as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except period.BelowFloor as exc:
        print(str(exc), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
