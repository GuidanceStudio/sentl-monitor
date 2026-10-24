#!/usr/bin/env python3
"""sentl-monitor's deterministic steps. It reads the Sentl MCP responses the
assistant saved into a study folder and never calls Sentl.

Exit codes: 0 done; 1 check, validate or doctor found problems, or demand autocomplete could not fetch every prefix; 2 input refused; 3 run not
final; 4 no run left in the period; 5 a Sentl response, an export, or a pack's manifest, does not
have the shape the skill reads; 6 unexpected error; 7 a download link that does not answer.
"""

import argparse
import datetime as dt
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Checked before the other modules load, so an older Python gets one line instead of a syntax error.
from sentlmon import doctor  # noqa: E402

if doctor.python_problem():
    print(doctor.python_problem(), file=sys.stderr)
    sys.exit(2)

from sentlmon import (adopt, charts, check, demand, design, detect, exportfile, frontmatter, ingest, method, pack,  # noqa: E402
                      period, runs, schema, setup, snapshot)
from sentlmon.common import Refused, Study  # noqa: E402

DEBUG_ENV = "SENTL_MONITOR_DEBUG"


def _skill_version():
    """SKILL.md's version; "unknown" when its frontmatter cannot be read, so no command fails on it."""
    try:
        return frontmatter.version()
    except (OSError, ValueError):
        return "unknown"


def _parser():
    today = dt.date.today().isoformat()
    p = argparse.ArgumentParser(prog="monitor.py", description=__doc__.split("\n\n")[0])
    debug = f"on an unexpected error, print the traceback (or set {DEBUG_ENV}=1)"
    p.add_argument("--debug", action="store_true", help=debug)
    p.add_argument("--version", action="version", version=_skill_version(),
                   help="print the skill's version, from SKILL.md, and exit")
    # Accepted after the command too; SUPPRESS keeps the command's default from overwriting a
    # --debug given before it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--debug", action="store_true", default=argparse.SUPPRESS, help=debug)
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    def command(name, help):
        return sub.add_parser(name, help=help, parents=[common])

    a = command("adopt", "take an existing Sentl project into the study folder")
    a.add_argument("--study", default=".", help="study folder (default: current directory)")
    a.add_argument("--project", required=True, help="saved get-project-tool response")
    a.add_argument("--run", help="saved get-run-results-tool response of the latest completed run")
    a.add_argument("--key", help="local key of the project (default: a slug of its name)")

    d = command("detect", "record a detected version when the project in Sentl differs from the latest one")
    d.add_argument("--study", default=".")
    d.add_argument("--project", required=True, help="local key of the project")
    d.add_argument("--saved", required=True, help="saved get-project-tool response, read now")
    d.add_argument("--new-intent", action="append", default=[], metavar="KEY",
                   help="a reworded question that now asks something else: it gets a new key (repeatable)")
    d.add_argument("--dry-run", action="store_true", help="list the changes and write nothing")

    n = command("runs", "read a saved run listing: the runs to fetch for a report, or the latest "
                        "completed run when adopting")
    n.add_argument("--study", default=".")
    n.add_argument("--saved", required=True, help="saved list-runs-tool response")
    n.add_argument("--project", help="local key of the project; without it, the latest completed run for adopt")
    n.add_argument("--date", default=today, help="report date, YYYY-MM-DD (default: today)")

    i = command("ingest", "store a run's results as a normalized snapshot")
    i.add_argument("--study", default=".")
    i.add_argument("--project", required=True, help="local key of the project")
    src = i.add_mutually_exclusive_group(required=True)
    src.add_argument("--results", help="saved get-run-results-tool response")
    src.add_argument("--pages", nargs="+", metavar="PAGE", help="saved get-run-results-tool pages of one run, "
                     "each checked by its content_sha256")
    src.add_argument("--unavailable", type=int, metavar="RUN_ID", help="record a run Sentl could not return")
    i.add_argument("--reason", default="server error", help="with --unavailable: the error Sentl returned")

    x = command("import", "write the project, the run listing and the runs of a Sentl export into inbox/")
    x.add_argument("--study", default=".")
    x.add_argument("--sha256", help="the digest export-runs-tool returned for the file")
    x.add_argument("file", help="the gzip file export-runs-tool's link served")

    w = command("download", "fetch an export link from Sentl (no credential is sent) and import it")
    w.add_argument("--study", default=".")
    w.add_argument("--url", required=True, help="download.url of export-runs-tool")
    w.add_argument("--sha256", required=True, help="download.sha256 of export-runs-tool")

    r = command("period", "compute the metrics of a report period")
    r.add_argument("--study", default=".")
    r.add_argument("--date", default=today, help="report date, YYYY-MM-DD (default: today)")
    r.add_argument("--models", help="saved list-ai-models response, for public names in the material")

    j = command("pending", "unattended report: say whether a completed run is new, from the run listings saved as "
                           "inbox/runs-<project id>.json, and record nothing_new when none is")
    j.add_argument("--study", default=".")
    j.add_argument("--date", default=today, help="report date, YYYY-MM-DD (default: today)")

    m = command("method", "write the report's method sections and its outline")
    m.add_argument("--study", default=".")
    m.add_argument("--date", default=today)
    m.add_argument("--models", required=True, help="saved list-ai-models response")
    m.add_argument("--force", action="store_true", help="overwrite an existing report")

    c = command("check", "verify a report before it is final")
    c.add_argument("--study", default=".")
    c.add_argument("--date", help="period date (default: from the report's file name)")
    c.add_argument("--unattended", action="store_true",
                   help="no operator to fix the report: when check fails, keep it as reports/<date>.draft.md "
                        "and record it as a draft")
    c.add_argument("report", help="the report file")

    g = command("charts", "write a report's figures as md2 chart tables for a deck")
    g.add_argument("--study", default=".")
    g.add_argument("--date", default=today, help="period date, YYYY-MM-DD (default: today)")

    h = command("doctor", "report the Python version, the system, and whether a study folder is writable and lasts")
    h.add_argument("--study", help="study folder to check (optional)")

    k = command("pack", "write the state the next report needs as one zip, to carry a study between web "
                        "conversations")
    k.add_argument("--study", default=".")
    k.add_argument("--full", action="store_true", help="hold every run and period, to move or archive a study")
    k.add_argument("--out", help="the zip to write, or a folder for it (default: next to the study folder, "
                                 "named <study folder>-<last report date>.sentl-pack.zip)")

    q = command("demand", "collect search demand: Google suggestions, volumes from a keyword-data source, a summary")
    dsub = q.add_subparsers(dest="demand_command", required=True, metavar="action")

    def action(name, help):
        sp = dsub.add_parser(name, help=help, parents=[common])
        sp.add_argument("--study", default=".")
        return sp

    da = action("autocomplete", "send each seed, as typed and with each question stem, to Google's suggestions")
    da.add_argument("--seeds", help="seeds.json (default: seeds.json in the study folder)")
    da.add_argument("--hl", required=True, help="the market's language, such as it or en")
    da.add_argument("--gl", required=True, help="the market's country, such as IT or US")
    da.add_argument("--stems", help="question words, separated by commas, for a language with no built-in stems")
    dv = action("volumes", "merge the volumes a keyword-data tool returned, saved as a file")
    dv.add_argument("--seeds")
    dv.add_argument("file", help="volumes.json: provider, tool, collected and the keywords")
    di = action("import", "merge an export file of a keyword tool (CSV, or JSON in the volumes shape)")
    di.add_argument("--seeds")
    di.add_argument("--provider", help="the keyword-data source (CSV)")
    di.add_argument("--tool", help="the tool or export that produced the file (CSV)")
    di.add_argument("--theme", help="the theme of the file's keywords (CSV)")
    di.add_argument("--date", help="when the volumes were collected, YYYY-MM-DD (default: today)")
    di.add_argument("file", help="the export file")
    action("summary", "print each theme's suggestions, volume per class and top queries")

    v = command("validate", "check a designed study.json against Sentl's limits and the design rules")
    v.add_argument("--study", default=".")
    v.add_argument("--models", required=True, help="saved list-ai-models response")

    e = command("review", "write study-review.md: the narrative, themes, questions, rubrics and the credit estimate")
    e.add_argument("--study", default=".")
    e.add_argument("--models", required=True, help="saved list-ai-models response, with each model's credits")

    f = command("revise", "record the lineage of a revised study.json against the previous design")
    f.add_argument("--study", default=".")
    f.add_argument("--previous", required=True, help="the study.json before the revision")
    f.add_argument("--new-intent", action="append", default=[], metavar="KEY",
                   help="a reworded question that now asks something else: it gets a new key (repeatable)")
    f.add_argument("--dry-run", action="store_true", help="list the changes and write nothing")

    o = command("payload", "print the arguments of the Sentl tools that create a project, change its settings and "
                           "save its questions, from study.json and sentl.json; calls nothing")
    o.add_argument("--study", default=".")
    o.add_argument("--project", required=True, help="local key of the project")
    o.add_argument("--models", required=True, help="saved list-ai-models response")
    o.add_argument("--saved", help="saved get-project-tool response, read now (required once the project exists)")
    o.add_argument("--runs", help="saved list-runs-tool response, read now (required once the project exists)")

    b = command("bind", "record the ids of a saved get-project-tool response in sentl.json and a setup version")
    b.add_argument("--study", default=".")
    b.add_argument("--project", required=True, help="local key of the project")
    b.add_argument("--saved", required=True, help="saved get-project-tool response, read now")
    b.add_argument("--run", help="saved get-run-results-tool response of the latest completed run")

    z = command("resume", "say which step of the snapshot route a folder is at, from its files and the run listing read now")
    z.add_argument("--study", default=".")
    z.add_argument("--runs", help="saved list-runs-tool response, read now (required once the project is bound)")

    l = command("close", "record that a snapshot's project is paused and left for the operator to archive")
    l.add_argument("--study", default=".")
    l.add_argument("--saved", required=True, help="saved get-project-tool response, read after the pause")

    r = command("promote", "turn a finished snapshot whose project is still open into a monitored study")
    r.add_argument("--study", default=".")
    r.add_argument("--answers", required=True, help="JSON file: schedule, report_every, audience, project question and decision")
    r.add_argument("--models", required=True, help="saved list-ai-models response")

    u = command("unpack", "check a pack and write its files into the study folder")
    u.add_argument("--study", default=".", help="study folder: empty, or the folder of the pack's own study")
    u.add_argument("pack", help="the pack written by pack")
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    try:
        if args.command == "adopt":
            print(adopt.adopt(args.study, args.project, args.run, args.key))
        elif args.command == "detect":
            print(detect.detect(args.study, args.project, args.saved, args.new_intent, args.dry_run))
        elif args.command == "runs":
            print(runs.runs(args.study, args.saved, args.project, args.date))
        elif args.command == "pending":
            print(runs.pending(args.study, args.date))
        elif args.command == "ingest":
            if args.unavailable is not None:
                print(ingest.record_unavailable(args.study, args.project, args.unavailable, args.reason))
            else:
                results = (exportfile.assemble_pages(args.study, args.pages) if args.pages else args.results)
                print(ingest.ingest(args.study, args.project, results))
        elif args.command == "import":
            print(exportfile.import_export(args.study, args.file, args.sha256))
        elif args.command == "download":
            print(exportfile.download(args.study, args.url, args.sha256))
        elif args.command == "period":
            print(period.build(args.study, args.date, args.models))
        elif args.command == "method":
            print(method.write(args.study, args.date, args.models, args.force))
        elif args.command == "check":
            problems = check.check(args.study, args.report, args.date, args.unattended)
            if problems:
                print(f"check failed: {len(problems)} problem(s)")
                for problem in problems:
                    print(f"  - {problem}")
                if args.unattended:
                    day = args.date or Path(args.report).stem.split(".")[0]
                    print(f"Saved as {Path(args.report).with_name(f'{day}.draft.md')}, recorded as a draft; the next "
                          "invocation does not write it again.")
                return 1
            print("check passed: quotes are verbatim, figures and counts are the period's, sections are in order, "
                  "and no id, key, model id, file name or credit figure appears. The report is recorded as final "
                  "in history/reports.json.")
            if doctor.host_sandbox(doctor.SANDBOX_ROOTS) or doctor.sandbox_root(args.study, doctor.SANDBOX_ROOTS):
                print(f"This host deletes its files when the conversation ends: run monitor.py pack --study "
                      f"{args.study} --out <the folder the host offers for download>, copy the report there, and "
                      "offer the report and the pack for download.")
        elif args.command == "charts":
            print(charts.write(args.study, args.date))
        elif args.command == "doctor":
            lines, ok = doctor.report(args.study, skill_version=_skill_version())
            print("\n".join(lines))
            return 0 if ok else 1
        elif args.command == "pack":
            print(pack.pack(args.study, args.out, args.full, skill_version=_skill_version()))
        elif args.command == "demand":
            study = args.study
            seeds = getattr(args, "seeds", None) or str(Path(study) / "seeds.json")
            if args.demand_command == "autocomplete":
                stems = [w.strip() for w in args.stems.split(",") if w.strip()] if args.stems else None
                print(demand.autocomplete(study, seeds, args.hl, args.gl, stems))
            elif args.demand_command == "volumes":
                print(demand.merge_volumes(study, args.file, seeds))
            elif args.demand_command == "import":
                print(demand.import_export(study, args.file, seeds, args.provider, args.tool, args.theme, args.date))
            else:
                print(demand.summary(study))
        elif args.command == "validate":
            text, ok = (snapshot if snapshot.is_snapshot(args.study) else design).validate(args.study, args.models)
            print(text)
            return 0 if ok else 1
        elif args.command == "review":
            print((snapshot if snapshot.is_snapshot(args.study) else design).review(args.study, args.models))
        elif args.command == "revise":
            print(design.revise_files(args.study, args.previous, args.new_intent, args.dry_run))
        elif args.command == "payload":
            print(setup.payload(args.study, args.project, args.models, args.saved, args.runs))
        elif args.command == "bind":
            print(setup.bind(args.study, args.project, args.saved, args.run))
        elif args.command == "resume":
            print(snapshot.resume(args.study, args.runs))
        elif args.command == "close":
            print(snapshot.close(args.study, args.saved))
        elif args.command == "promote":
            print(snapshot.promote(args.study, args.answers, args.models))
        elif args.command == "unpack":
            print(pack.unpack(args.study, args.pack, skill_version=_skill_version()))
    except demand.Incomplete as exc:
        print(str(exc))
        return 1
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except ingest.NotFinal as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except exportfile.Unreachable as exc:
        print(str(exc), file=sys.stderr)
        return 7
    except period.BelowFloor as exc:
        Study(args.study).record_outcome("below_floor", str(exc))
        print(str(exc), file=sys.stderr)
        return 4
    except (schema.Mismatch, pack.Unknown) as exc:
        print(str(exc), file=sys.stderr)
        return 5
    except KeyboardInterrupt:
        print(f"interrupted: {args.command} stopped before it finished; run it again.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - the last resort: one line, never a traceback unless asked
        if args.debug or os.environ.get(DEBUG_ENV, "") not in ("", "0"):
            traceback.print_exc()
        detail = " ".join(str(exc).split())
        print(f"error: unexpected {type(exc).__name__} in {args.command}" + (f": {detail}" if detail else "")
              + f". Rerun with --debug (or {DEBUG_ENV}=1) to see where it happened, and report it.", file=sys.stderr)
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())
