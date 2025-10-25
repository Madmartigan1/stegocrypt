# spread_utils.py
import hashlib, random
import numpy as np

def permuted_indices(total_slots: int, seed_bytes: bytes, take: int) -> np.ndarray:
    if take > total_slots: raise ValueError("take > total_slots")
    seed_int = int.from_bytes(hashlib.sha256(seed_bytes).digest(), "big")
    rng = random.Random(seed_int)
    # efficient when take << total_slots
    if take * 10 < total_slots:
        s = set()
        while len(s) < take:
            s.add(rng.randrange(total_slots))
        return np.fromiter(s, dtype=np.int64)
    idx = list(range(total_slots))
    rng.shuffle(idx)
    return np.array(idx[:take], dtype=np.int64)

def chunk_seed(base_seed: bytes, chunk_index: int) -> bytes:
    # derive deterministic per-chunk seed
    return hashlib.sha256(base_seed + chunk_index.to_bytes(8, "big")).digest()
