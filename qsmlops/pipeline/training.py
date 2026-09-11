"""Pure-Python reference trainer: deterministic linear regression.

Serves as the platform's demo ML workload. Deliberately dependency-free and
seeded so that training runs are reproducible byte-for-byte, which the
passport/registry machinery relies on.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from qsmlops.crypto.hashing import canonical_json


@dataclass
class Dataset:
    samples: list[list[float]]  # each row: features..., label
    feature_names: list[str]

    @property
    def X(self) -> list[list[float]]:
        return [row[:-1] for row in self.samples]

    @property
    def y(self) -> list[float]:
        return [row[-1] for row in self.samples]


def make_synthetic_regression(
    n: int = 200,
    true_weights: tuple[float, ...] = (1.5, -2.0),
    bias: float = 0.5,
    noise: float = 0.05,
    seed: int = 42,
) -> Dataset:
    rng = random.Random(seed)
    samples = []
    for _ in range(n):
        x1 = rng.uniform(-3, 3)
        x2 = rng.uniform(-3, 3)
        y = (
            true_weights[0] * x1
            + true_weights[1] * x2
            + bias
            + rng.gauss(0, noise)
        )
        samples.append([x1, x2, y])
    return Dataset(samples=samples, feature_names=["x1", "x2"])


def train_linear_regression(
    dataset: Dataset, epochs: int = 300, lr: float = 0.02, seed: int = 7
) -> dict:
    """Full-batch gradient descent; returns serializable model artifact."""
    X, y = dataset.X, dataset.y
    n_features = len(X[0])
    rng = random.Random(seed)
    weights = [rng.uniform(-0.01, 0.01) for _ in range(n_features)]
    bias = 0.0
    n = len(X)
    for _ in range(epochs):
        grad_w = [0.0] * n_features
        grad_b = 0.0
        for row, target in zip(X, y):
            pred = sum(w * v for w, v in zip(weights, row)) + bias
            err = pred - target
            for i in range(n_features):
                grad_w[i] += err * row[i]
            grad_b += err
        weights = [w - lr * (g / n) for w, g in zip(weights, grad_w)]
        bias -= lr * (grad_b / n)
    return {"weights": [round(w, 10) for w in weights], "bias": round(bias, 10)}


def evaluate_linear(model: dict, dataset: Dataset) -> dict:
    weights, bias = model["weights"], model["bias"]
    preds = [
        sum(w * v for w, v in zip(weights, row)) + bias for row in dataset.X
    ]
    y = dataset.y
    mse = sum((p - t) ** 2 for p, t in zip(preds, y)) / len(y)
    mean_y = sum(y) / len(y)
    var = sum((t - mean_y) ** 2 for t in y)
    r2 = 1.0 - (sum((p - t) ** 2 for p, t in zip(preds, y)) / var if var else 0.0)
    return {"mse": round(mse, 8), "r2": round(r2, 8), "n": len(y)}


def serialize_model(model: dict) -> bytes:
    return canonical_json({"type": "linear-regression", **model})


def deserialize_model(raw: bytes) -> dict:
    doc = json.loads(raw.decode("utf-8"))
    return {"weights": doc["weights"], "bias": doc["bias"]}
