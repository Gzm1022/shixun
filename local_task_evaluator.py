import argparse
import json
import os
import subprocess
import sys
from glob import glob
from pathlib import Path


def _run_task(args, task: str) -> dict:
    run_name = args.run_name or f"{task}_{args.variant}_eval_seed{args.scene_seed}"
    if len(args.tasks) > 1:
        run_name = f"{run_name}_{task}"

    cmd = [
        sys.executable,
        "run_dialog.py",
        "--task",
        task,
        "--comm_mode",
        args.comm_mode,
        "--num_runs",
        str(args.runs),
        "--tsteps",
        str(args.tsteps),
        "--num_replans",
        str(args.num_replans),
        "--seed",
        str(args.scene_seed),
        "--run_timeout",
        str(args.timeout),
        "--rrt_timeout",
        str(args.rrt_timeout),
        "--run_name",
        run_name,
        "--data_dir",
        args.output_dir,
    ]

    if args.skip_display:
        cmd.append("--skip_display")
    if args.skip_smooth_path:
        cmd.append("--skip_smooth_path")
    if args.fallback_first:
        cmd.append("--fallback_first")

    if task == "sort":
        cmd.extend(["--sort_variant", args.variant])
        cmd.extend(["--sort_target_mode", args.sort_target_mode])
    if task == "rope":
        cmd.extend(["--rope_variant", args.variant])
        cmd.extend(["--rope_goal_noise", str(args.rope_goal_noise)])
        cmd.extend(["--rope_obstacle_noise", str(args.rope_obstacle_noise)])
        cmd.extend(["--rope_pose_noise", str(args.rope_pose_noise)])
    if task == "sweep":
        cmd.extend(["--sweep_variant", args.variant])
        cmd.extend(["--sweep_cube_noise", str(args.sweep_cube_noise)])
        cmd.extend(["--sweep_target_noise", str(args.sweep_target_noise)])

    print("Running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=False)

    run_dir = Path(args.output_dir) / run_name
    result_files = glob(str(run_dir / "run_*" / "steps*_success_*.json"))
    successes = 0
    timed_out = 0
    elapsed = []
    details = []
    for result_file in sorted(result_files):
        with open(result_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        success = bool(result.get("success", False))
        successes += int(success)
        timed_out += int(bool(result.get("timed_out", False)))
        elapsed.append(float(result.get("elapsed_time", 0.0)))
        details.append(
            {
                "file": result_file,
                "success": success,
                "step": result.get("step"),
                "timed_out": result.get("timed_out", False),
                "elapsed_time": result.get("elapsed_time", 0.0),
            }
        )

    total = len(result_files)
    summary = {
        "task": task,
        "variant": args.variant,
        "run_name": run_name,
        "successes": successes,
        "total": total,
        "success_rate": (successes / total) if total else 0.0,
        "timed_out": timed_out,
        "avg_elapsed_time": (sum(elapsed) / len(elapsed)) if elapsed else 0.0,
        "details": details,
    }

    summary_path = run_dir / "local_eval_summary.json"
    os.makedirs(run_dir, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Local RoCoBench task evaluator built on run_dialog.py")
    parser.add_argument("--tasks", nargs="+", default=["rope"], choices=["sort", "cabinet", "rope", "sweep", "sandwich", "pack"])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--tsteps", type=int, default=10)
    parser.add_argument("--num_replans", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--rrt_timeout", type=int, default=200)
    parser.add_argument("--output_dir", default="data")
    parser.add_argument("--scene_seed", type=int, default=42)
    parser.add_argument("--run_name", default="")
    parser.add_argument("--comm_mode", default="plan", choices=["chat", "plan", "dialog"])
    parser.add_argument("--variant", default="default", choices=["default", "easy", "medium", "hard"])
    parser.add_argument("--sort_target_mode", default="fixed", choices=["fixed", "permuted"])
    parser.add_argument("--rope_goal_noise", type=float, default=0.0)
    parser.add_argument("--rope_obstacle_noise", type=float, default=0.0)
    parser.add_argument("--rope_pose_noise", type=float, default=0.0)
    parser.add_argument("--sweep_cube_noise", type=float, default=0.0)
    parser.add_argument("--sweep_target_noise", type=float, default=0.0)
    parser.add_argument("--fallback_first", dest="fallback_first", action="store_true", default=True)
    parser.add_argument("--no_fallback_first", dest="fallback_first", action="store_false")
    parser.add_argument("--skip_display", dest="skip_display", action="store_true", default=True)
    parser.add_argument("--show_display", dest="skip_display", action="store_false")
    parser.add_argument("--skip_smooth_path", dest="skip_smooth_path", action="store_true", default=True)
    parser.add_argument("--keep_smooth_path", dest="skip_smooth_path", action="store_false")
    args = parser.parse_args()

    summaries = [_run_task(args, task) for task in args.tasks]
    print("\nSummary")
    for summary in summaries:
        print(
            f"{summary['task']} {summary['variant']}: "
            f"{summary['successes']}/{summary['total']} = {summary['success_rate'] * 100:.1f}% "
            f"(timeouts={summary['timed_out']}, avg_time={summary['avg_elapsed_time']:.1f}s)"
        )


if __name__ == "__main__":
    main()
