# stego_image.py
import numpy as np
from PIL import Image
from bit_utils import bytes_to_bits, bits_to_bytes
from spread_utils import permuted_indices
from crypto_utils import HEADER_LEN, SALT_LEN

def embed_image(in_path, out_path, full_payload: bytes, password: str, lsb: int=1, spread=True, progress=None):
    img = Image.open(in_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1)  # bytes
    total_slots = flat.size * lsb

    bits = bytes_to_bits(full_payload)
    need = bits.size
    if need > total_slots: raise ValueError("Payload too large for this image with current LSB setting")

    header_slots = HEADER_LEN * 8
    salt_slots   = SALT_LEN * 8
    rem_slots    = total_slots - (header_slots + salt_slots)
    rem_bits     = need - (header_slots + salt_slots)
    if rem_bits < 0: raise ValueError("Payload smaller than header+salt?")

    # Write header (sequential)
    for i in range(header_slots):
        bidx = i // lsb; off = i % lsb
        v = int(flat[bidx]) & ~(1<<off)
        flat[bidx] = v | ((int(bits[i]) & 1) << off)

    # Write salt (sequential)
    for i in range(header_slots, header_slots + salt_slots):
        bidx = i // lsb; off = i % lsb
        v = int(flat[bidx]) & ~(1<<off)
        flat[bidx] = v | ((int(bits[i]) & 1) << off)

    # Remaining (permuted)
    seed = (password.encode() + full_payload[HEADER_LEN:HEADER_LEN+SALT_LEN])
    idxs = permuted_indices(rem_slots, seed, rem_bits) if spread and rem_bits>0 else np.arange(rem_bits, dtype=np.int64)
    base_slot = header_slots + salt_slots
    for i in range(rem_bits):
        slot = base_slot + int(idxs[i])
        bidx = slot // lsb; off = slot % lsb
        v = int(flat[bidx]) & ~(1<<off)
        flat[bidx] = v | ((int(bits[header_slots + salt_slots + i]) & 1) << off)
        if progress and (i % 10000 == 0): progress(i, rem_bits)

    Image.fromarray(flat.reshape(arr.shape), "RGB").save(out_path)

def extract_image(in_path, password: str, use_rs=False, rs_nsym=0, lsb: int=1, spread=True, progress=None):
    from payload_format import parse_payload
    from crypto_utils import HEADER_LEN, SALT_LEN, MAGIC
    import struct

    img = Image.open(in_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1)
    total_slots = flat.size * lsb

    header_slots = HEADER_LEN * 8
    if header_slots > total_slots: raise ValueError("Image too small")

    # read header seq
    hb = []
    for i in range(header_slots):
        bidx = i // lsb; off = i % lsb
        hb.append((int(flat[bidx]) >> off) & 1)
    from bit_utils import bits_to_bytes
    header = bits_to_bytes(np.array(hb, dtype=np.uint8))

    if header[:len(MAGIC)] != MAGIC: raise ValueError("Magic not found")
    pay_len = struct.unpack(">Q", header[len(MAGIC):len(MAGIC)+8])[0]
    payload_bits_needed = pay_len * 8

    salt_slots = SALT_LEN * 8
    if header_slots + salt_slots + payload_bits_needed - salt_slots > total_slots:
        raise ValueError("Capacity mismatch")

    # salt seq
    sb = []
    for i in range(header_slots, header_slots + salt_slots):
        bidx = i // lsb; off = i % lsb
        sb.append((int(flat[bidx]) >> off) & 1)
    salt_bytes = bits_to_bytes(np.array(sb, dtype=np.uint8))

    rem_bits = payload_bits_needed - salt_slots
    rem_slots = total_slots - (header_slots + salt_slots)

    from spread_utils import permuted_indices
    seed = password.encode() + salt_bytes
    idxs = permuted_indices(rem_slots, seed, rem_bits) if spread and rem_bits>0 else np.arange(rem_bits, dtype=np.int64)

    # reconstruct payload bits (salt + permuted remainder)
    pb = []
    pb.extend(sb)
    base_slot = header_slots + salt_slots
    for i in range(rem_bits):
        slot = base_slot + int(idxs[i])
        bidx = slot // lsb; off = slot % lsb
        pb.append((int(flat[bidx]) >> off) & 1)
        if progress and (i % 10000 == 0): progress(i, rem_bits)

    payload = bits_to_bytes(np.array(pb, dtype=np.uint8))
    full = header + payload
    return parse_payload(full, password, use_rs=use_rs, rs_nsym=rs_nsym)
