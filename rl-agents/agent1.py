import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import random
import math
import logging
from collections import deque, namedtuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

logging.basicConfig(level=logging.INFO)

device = torch.device(
    "cuda" if torch.cuda.is_available() else
    "mps" if torch.backends.mps.is_available() else
    "cpu"
)
# Tensors get device= explicitly. torch.set_default_device() was used here before, but it
# intercepts every torch call and was ~half of training time on CPU.

Transition = namedtuple("Transition", ("state", "action", "next_state", "reward", "done"))


class ReplayMemory:
    def __init__(self, capacity: int):
        self.memory = deque([], maxlen=capacity)

    def push(self, state, action, next_state, reward, done):
        self.memory.append(Transition(state, action, next_state, reward, done))

    def sample(self, batch_size: int):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


class DQN(nn.Module):
    def __init__(self, n_observations, n_actions):
        super(DQN, self).__init__()
        self.layer1 = nn.Linear(n_observations, 128)
        self.layer2 = nn.Linear(128, 128)
        self.layer3 = nn.Linear(128, n_actions)

    def forward(self, x):
        x = F.relu(self.layer1(x))
        x = F.relu(self.layer2(x))
        return self.layer3(x)


class Agent:
    def __init__(
        self,
        n_state: int,
        n_actions: int,
        memory_capacity: int = 100_000,
        batch_size: int = 128,
        learning_rate: float = 5e-4,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: int = 1_000_000,  # ~380 episodes of exploration; at 200k it hit the floor by ~ep 60 and braking was barely tried
        tau: float = 0.005,
        learn_every: int = 4,
    ):
        self.n_state = n_state
        self.n_actions = n_actions
        self.batch_size = batch_size
        self.gamma = gamma
        self.tau = tau
        self.learn_every = learn_every
        self.steps_done = 0

        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay

        self.policy_net = DQN(n_state, n_actions).to(device)
        self.target_net = DQN(n_state, n_actions).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.AdamW(self.policy_net.parameters(), lr=learning_rate)
        self.memory = ReplayMemory(memory_capacity)

    def epsilon(self) -> float:
        progress = self.steps_done / self.epsilon_decay
        return self.epsilon_end + (self.epsilon_start - self.epsilon_end) * math.exp(-5.0 * progress)

    def choose_action(self, state: list[float], eps_greedy: bool = True) -> int:
        if eps_greedy and random.random() < self.epsilon():
            return random.randrange(self.n_actions)

        with torch.no_grad():
            state_t = torch.tensor(np.asarray(state, dtype=np.float32), dtype=torch.float32, device=device)
            return int(self.policy_net(state_t).argmax().item())

    def remember(self, *transition):
        self.memory.push(*transition)

    def _matching_state(self, state):
        return state if state is not None else np.zeros(self.n_state, dtype=np.float32)

    def learn(self):
        if len(self.memory) < self.batch_size:
            return None

        transitions = self.memory.sample(self.batch_size)
        batch = Transition(*zip(*transitions))

        state_batch = torch.tensor(np.array(batch.state, dtype=np.float32), dtype=torch.float32, device=device)
        action_batch = torch.tensor(batch.action, dtype=torch.long, device=device).unsqueeze(1)
        reward_batch = torch.tensor(batch.reward, dtype=torch.float32, device=device).unsqueeze(1)
        done_batch = torch.tensor(batch.done, dtype=torch.float32, device=device).unsqueeze(1)

        next_states_list = [self._matching_state(s) for s in batch.next_state]
        next_state_batch = torch.tensor(np.array(next_states_list, dtype=np.float32), dtype=torch.float32, device=device)

        q_values = self.policy_net(state_batch).gather(1, action_batch)

        with torch.no_grad():
            next_actions = self.policy_net(next_state_batch).argmax(dim=1, keepdim=True)
            next_q_values = self.target_net(next_state_batch).gather(1, next_actions)
            targets = reward_batch + (1.0 - done_batch) * self.gamma * next_q_values

        loss = F.smooth_l1_loss(q_values, targets)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=10.0)
        self.optimizer.step()

        self._soft_update()
        return loss.item()

    @torch.no_grad()
    def _soft_update(self):
        # target <- target + tau * (policy - target), done in place
        for target_param, policy_param in zip(self.target_net.parameters(), self.policy_net.parameters()):
            target_param.lerp_(policy_param, self.tau)

    def schedule(self):
        self.steps_done += 1

    def save(self, path: str):
        torch.save(
            {
                "policy_net": self.policy_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "steps_done": self.steps_done,
                "n_state": self.n_state,
                "n_actions": self.n_actions,
            },
            path,
        )

    def load(self, path: str):
        checkpoint = torch.load(path, map_location=device)
        # Fail with a readable message instead of a tensor size mismatch from load_state_dict
        saved = (checkpoint.get("n_state", self.n_state), checkpoint.get("n_actions", self.n_actions))
        if saved != (self.n_state, self.n_actions):
            raise ValueError(
                f"{path} has n_state={saved[0]}, n_actions={saved[1]}; "
                f"this agent has n_state={self.n_state}, n_actions={self.n_actions}"
            )
        self.policy_net.load_state_dict(checkpoint["policy_net"])
        self.target_net.load_state_dict(checkpoint["target_net"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.steps_done = checkpoint.get("steps_done", self.steps_done)