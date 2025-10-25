# bit_utils.py
import numpy as np

def bytes_to_bits(b: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(b, dtype=np.uint8)).astype(np.uint8)

def bits_to_bytes(bits: np.ndarray) -> bytes:
    if bits.size % 8 != 0:
        pad = 8 - (bits.size % 8)
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    return np.packbits(bits).tobytes()
