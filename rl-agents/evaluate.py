import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import argparse
import glob
import re

from train import build_env, run_episode
from agent1 import Agent

BASELINE_MIN = 19.3  # constant 250 W with auto-braking on stage-1 (CLAUDE.md)


def checkpoint_paths(checkpoint_dir: str) -> list[str]:
    # episode_N.pt sorted by N (as text, episode_1000 would sort before episode_200), then best/final
    numbered: dict[str, int] = {}
    for p in glob.glob(os.path.join(checkpoint_dir, "episode_*.pt")):
        m = re.search(r"episode_(\d+)\.pt$", p)
        if m:  # skip e.g. episode_backup.pt
            numbered[p] = int(m.group(1))
    episodes = sorted(numbered, key=lambda p: numbered[p])
    extras = [os.path.join(checkpoint_dir, name) for name in ("best.pt", "final.pt")]
    return episodes + [p for p in extras if os.path.exists(p)]


def main():
    parser = argparse.ArgumentParser(description="Evaluate DQN checkpoints greedily (epsilon = 0) on a route.")
    parser.add_argument("--route", default=os.path.join(ROOT, "backend", "data", "stage-1-route.gpx"), help="Path to a GPX route file.")
    parser.add_argument("--dt", type=float, default=0.5, help="Physics timestep in seconds; use the one the checkpoints were trained with.")
    parser.add_argument("--checkpoint-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints"), help="Directory with .pt checkpoints.")
    parser.add_argument("--checkpoint", default=None, help="Evaluate only this .pt file (e.g. rl-agents/checkpoints/best.pt).")
    parser.add_argument("--crashes", action="store_true", help="Print details of every crash in each greedy ride.")
    args = parser.parse_args()

    paths = [args.checkpoint] if args.checkpoint else checkpoint_paths(args.checkpoint_dir)
    if not paths:
        print(f"No checkpoints found in {args.checkpoint_dir}")
        return

    env = build_env(args.route, args.dt, (0.0, 0.0))
    print(f"Route: {env.total_distance / 1000:.2f} km | dt={args.dt} s | baseline {BASELINE_MIN} min")
    print(f"{'checkpoint':<18} {'ride':>10} {'vs base':>8} {'crashes':>8} {'avg W':>6} {'max km/h':>9}")

    for path in paths:
        agent = Agent(n_state=env.n_state, n_actions=env.n_actions)
        try:
            agent.load(path)
        except ValueError as e:  # trained with a different observation/action size
            print(f"{os.path.basename(path):<18} skipped: {e}", flush=True)
            continue
        # Greedy run: no random actions, no replay memory, no learning
        metrics = run_episode(env, agent, train=False)
        # Read now: the next run_episode calls env.reset(), which zeroes these
        avg_power = env.mechanical_joules / env.time_elapsed if env.time_elapsed > 0 else 0.0

        if metrics["finished"]:
            minutes = metrics["time"] / 60
            ride, delta = f"{minutes:.2f} min", f"{minutes - BASELINE_MIN:+.2f}"
        else:
            ride, delta = "DNF", "-"

        print(
            f"{os.path.basename(path):<18} {ride:>10} {delta:>8} {metrics['crashes']:>8} "
            f"{avg_power:>6.0f} {metrics['max_speed'] * 3.6:>9.1f}",
            flush=True,
        )
        if args.crashes:
            print_crashes(env.crash_log)


def print_crashes(crash_log: list[dict]):
    # Speeds in km/h for readability; overshoot > a few km/h = the agent didn't brake in time,
    # < ~2 km/h = it cut the corner fine and misjudged slightly.
    if not crash_log:
        return
    print(f"    {'pos m':>7} {'t s':>6} {'grade%':>7} {'v km/h':>7} {'limit':>6} {'grip':>5} {'over':>5}  {'action':<7} brake need (last ~2 s)")
    for c in crash_log:
        action = f"B {c['brake_n']:.0f}N" if c["brake_n"] > 0 else f"P {c['power_w']:.0f}W"
        need = " ".join(f"{b:+.2f}" for b in c["brake_need"][-6:])
        print(
            f"    {c['position_m']:>7.0f} {c['time_s']:>6.0f} {c['grade_pct']:>7.1f} {c['v_new'] * 3.6:>7.1f} "
            f"{c['limit'] * 3.6:>6.1f} {c['grip_factor']:>5.2f} {c['overshoot'] * 3.6:>5.1f}  {action:<7} {need}",
            flush=True,
        )


if __name__ == "__main__":
    main()
