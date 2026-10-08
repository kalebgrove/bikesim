import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import argparse
import time

import numpy as np

from env import BikeSimEnv
from agent1 import Agent
from backend.engine.rider import Rider
from backend.engine.route import Route


def build_env(route_path: str, dt: float, wind: tuple[float, float]) -> BikeSimEnv:
    rider = Rider(
        rider_mass=70.0,
        bike_mass=10.0,
        ftp=250.0,
        f_max=1000.0,
        cda=0.3,
        crr=0.005,
        inertia=0.15,  # both wheels, kg*m^2
        wheel_radius=0.35,
        metabolic_efficiency=0.22,
    )
    route = Route.get_route_from_gpx(route_path)
    return BikeSimEnv(rider, route, wind_velocity_vector=wind, dt=dt)


def run_episode(env: BikeSimEnv, agent: Agent, train: bool = True, max_steps: int = 40_000) -> dict:
    state = env.reset()
    total_reward = 0.0
    steps = 0
    distance_covered = 0.0
    max_speed = 0.0

    for _ in range(max_steps):
        action = agent.choose_action(state, eps_greedy=train)
        next_state, reward, terminated, truncated = env.step(action)

        if train:
            # Store `terminated` only: a time-limit cut-off isn't a true end state, so
            # the target must still bootstrap from next_state there.
            agent.remember(state, action, next_state, reward, terminated)
            agent.schedule()
            if agent.steps_done % agent.learn_every == 0:
                agent.learn()

        total_reward += reward
        distance_covered = env.position
        max_speed = max(max_speed, env.velocity)
        steps += 1
        state = next_state

        if terminated or truncated:
            break

    return {
        "reward": total_reward,
        "steps": steps,
        "distance": distance_covered,
        "max_speed": max_speed,
        "crashes": env.crashes,
        "finished": env.finished,
        "time": env.time_elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Train a DQN agent to ride a bike route.")
    parser.add_argument("--route", default=os.path.join(ROOT, "backend", "data", "stage-1-route.gpx"), help="Path to a GPX route file.")
    parser.add_argument("--episodes", type=int, default=5000, help="Number of training episodes.")
    parser.add_argument("--dt", type=float, default=0.5, help="Physics timestep in seconds.")
    parser.add_argument("--wind-x", type=float, default=0.0, help="Wind velocity x (m/s).")
    parser.add_argument("--wind-y", type=float, default=0.0, help="Wind velocity y (m/s).")
    parser.add_argument("--checkpoint-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints"), help="Directory to store checkpoints.")
    parser.add_argument("--resume", default=None, help="Checkpoint file to resume training from.")
    parser.add_argument("--log-every", type=int, default=50, help="Log progress every N episodes.")
    parser.add_argument("--save-every", type=int, default=100, help="Save checkpoint (and run a greedy ride for best.pt) every N episodes.")
    parser.add_argument("--max-steps", type=int, default=40_000, help="Max steps per episode.")
    args = parser.parse_args()

    os.makedirs(args.checkpoint_dir, exist_ok=True)

    env = build_env(args.route, args.dt, (args.wind_x, args.wind_y))
    limited_m = sum(v < env.CURVE_SPEED_CAP for v in env.speed_limits) * env.LIMIT_SPACING_M
    print(f"Route length: {env.total_distance / 1000:.2f} km | Corner-limited: {limited_m:.0f} m")
    print(f"State dim: {env.n_state} | Action count: {env.n_actions}")

    agent = Agent(n_state=env.n_state, n_actions=env.n_actions)
    if args.resume and os.path.exists(args.resume):
        agent.load(args.resume)
        print(f"Resumed from {args.resume} (steps_done={agent.steps_done})")

    rewards = []
    ride_times = []
    best_time = float("inf")
    start = time.time()

    for episode in range(1, args.episodes + 1):
        metrics = run_episode(env, agent, train=True, max_steps=args.max_steps)
        rewards.append(metrics["reward"])
        if metrics["finished"]:
            ride_times.append(metrics["time"])

        if episode % args.log_every == 0:
            recent = rewards[-args.log_every:]
            mean_reward = np.mean(recent)
            last_distance = metrics["distance"] / 1000.0
            elapsed = time.time() - start
            eps = agent.epsilon()
            best_ride = f"{min(ride_times) / 60:.1f} min" if ride_times else "-"
            print(
                f"ep={episode} | mean reward={mean_reward:8.1f} | "
                f"last: dist={last_distance:5.2f} km, ride={metrics['time'] / 60:.1f} min, "
                f"max speed={metrics['max_speed']:.1f} m/s, crashes={metrics['crashes']}, done={metrics['finished']} | "
                f"best ride={best_ride} | eps={eps:.3f} | t={elapsed:.0f}s",
                flush=True,
            )

        if episode % args.save_every == 0:
            # Pick best.pt by a greedy (epsilon = 0) ride: training reward includes random actions
            greedy = run_episode(env, agent, train=False, max_steps=args.max_steps)
            greedy_ride = f"{greedy['time'] / 60:.2f} min" if greedy["finished"] else "DNF"
            print(f"  greedy ride: {greedy_ride}, crashes={greedy['crashes']}", flush=True)
            if greedy["finished"] and greedy["time"] < best_time:
                best_time = greedy["time"]
                path = os.path.join(args.checkpoint_dir, "best.pt")
                agent.save(path)
            path = os.path.join(args.checkpoint_dir, f"episode_{episode}.pt")
            agent.save(path)

    final_path = os.path.join(args.checkpoint_dir, "final.pt")
    agent.save(final_path)
    print(f"Training complete. Final model saved to {final_path}")


if __name__ == "__main__":
    main()