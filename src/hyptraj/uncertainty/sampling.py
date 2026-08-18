"""Phase-H2 Monte-Carlo sampling engine (H2 §62).

Responsible ONLY for standardized Gaussian sample generation:

* ``numpy.random.Generator`` via ``default_rng`` with the frozen H0
  REPRODUCIBILITY seed (H0 §33; H2 §10);
* a single ANTITHETIC master standardized sample bank: ``(z_j, -z_j)``
  pairs in the fixed interleaved order ``z1, -z1, z2, -z2, ...`` so that
  every legal nested prefix (256, 512, 1024, 2048, 4096) is made of whole
  pairs and has exact zero input mean (H2 §11, §12);
* common-random-number identity: every model / alpha shares the SAME
  standardized sample IDs (H0 §49; H2 §12);
* sample-bank reproducibility: bit-generator / seed / shape / dtype /
  ordering recorded AND a SHA-256 of the raw float bytes stored in the
  H2 snapshot (H2 §13).

This module NEVER propagates trajectories (the caller/generator does) and
NEVER uses the global ``np.random`` state (only explicit local ``Generator``
instances; ``np.random.seed`` / ``np.random.normal`` are forbidden).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from hyptraj.uncertainty.protocol import (
    STATE_DIM,
    MONTE_CARLO_RNG_POLICY,
)

REPRODUCIBILITY_SEED = int(MONTE_CARLO_RNG_POLICY["reproducibility_seed"])
BIT_GENERATOR = "PCG64"
DEFAULT_MAX_PAIRS = 2048          # -> 4096 standardized samples
NESTED_SAMPLE_SIZES = (256, 512, 1024, 2048, 4096)
DTYPE = np.float64

# Bootstrap reproducibility (H2 §34): deterministic; NOT a physical
# parameter and deliberately different from the sampling seed.
BOOTSTRAP_SEED = 2027

ANTITHETIC_ORDERING = (
    "z1, -z1, z2, -z2, ...  (interleaved); every nested prefix N is a set "
    "of whole antithetic pairs => exact zero input mean to machine precision"
)


def bank_sha256(z_bank: np.ndarray) -> str:
    """SHA-256 of the raw float64 bytes of a standardized sample bank."""
    return hashlib.sha256(np.asarray(z_bank, dtype=DTYPE).tobytes()).hexdigest()


def build_antithetic_bank(
    n_pairs: int = DEFAULT_MAX_PAIRS,
    *,
    seed: int = REPRODUCIBILITY_SEED,
) -> np.ndarray:
    """Build the master antithetic standardized sample bank.

    Returns ``(2 * n_pairs, 4)`` with rows
    ``[z0, -z0, z1, -z1, ...]`` where ``z_j ~ N(0, I)`` drawn from a fresh
    local ``Generator`` (never ``np.random``).
    """
    if n_pairs <= 0:
        raise ValueError("n_pairs must be positive.")
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(n_pairs, STATE_DIM)).astype(DTYPE)   # (n_pairs, 4)
    bank = np.empty((2 * n_pairs, STATE_DIM), dtype=DTYPE)
    bank[0::2] = base
    bank[1::2] = -base
    return bank


@dataclass(frozen=True)
class AntitheticSampleBank:
    """Frozen view of the master standardized sample bank (H2 §12, §13).

    ``prefix(N)`` returns exactly the first ``N`` rows of the bank
    (whole pairs for every ``N`` in ``NESTED_SAMPLE_SIZES``), and the
    bank's row index IS the common-random-number sample ID shared by every
    model / alpha invocation.
    """

    z: np.ndarray
    seed: int = REPRODUCIBILITY_SEED
    n_pairs: int = DEFAULT_MAX_PAIRS

    def __post_init__(self) -> None:
        arr = np.asarray(self.z, dtype=DTYPE)
        expected = self.n_pairs * 2
        if arr.shape != (expected, STATE_DIM):
            raise ValueError(
                f"bank must have shape ({expected}, 4); got {arr.shape}.")
        object.__setattr__(self, "z", arr)

    @property
    def n_max(self) -> int:
        return int(self.n_pairs * 2)

    @property
    def sha256(self) -> str:
        return bank_sha256(self.z)

    def prefix(self, n: int) -> np.ndarray:
        """First ``n`` standardized samples (nested prefixes compat rule)."""
        if n < 2 or n % 2 != 0:
            raise ValueError(f"prefix n must be a positive even int, got {n}.")
        if n > self.n_max:
            raise ValueError(f"n={n} exceeds bank size {self.n_max}.")
        return self.z[:n].copy()

    def sample_ids(self, n: int) -> np.ndarray:
        """Common-random-number IDs ``0..n-1`` (identical across models)."""
        if n > self.n_max:
            raise ValueError(f"n={n} exceeds bank size {self.n_max}.")
        return np.arange(n, dtype=int)

    def metadata(self) -> dict:
        """Reproducibility record to embed in the H2 snapshot (H2 §13, §70)."""
        return {
            "bit_generator": BIT_GENERATOR,
            "seed": self.seed,
            "shape": list(self.z.shape),
            "dtype": str(self.z.dtype),
            "antithetic_ordering": ANTITHETIC_ORDERING,
            "n_max_samples": self.n_max,
            "sample_bank_sha256": self.sha256,
        }


def sample_bank(seed: int = REPRODUCIBILITY_SEED) -> AntitheticSampleBank:
    """Deterministic builder: the one master bank used by the whole H2 run."""
    return AntitheticSampleBank(build_antithetic_bank(seed=seed), seed=seed)
