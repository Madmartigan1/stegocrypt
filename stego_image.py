# stego_image.py
import numpy as np
from PIL import Image
from spread_utils import permuted_indices
from crypto_utils import HEADER_LEN, SALT_LEN
from payload_format import parse_payload

def embed_image(in_path, out_path, full_payload: bytes, password: str, lsb: int=1, spread=True, progress=None):
    img = Image.open(in_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1)  # bytes
    total_slots = flat.size * lsb

    bits = bytes_to_bits(full_payload)
    need = bits.size
    # Make sure GUI can key off "too large" / "capacity"
    if need > total_slots:
        raise ValueError("Payload too large for this image with current LSB (capacity exceeded)")

    header_slots = HEADER_LEN * 8
    salt_slots   = SALT_LEN * 8
    rem_slots    = total_slots - (header_slots + salt_slots)
    rem_bits     = need - (header_slots + salt_slots)
    if rem_bits < 0:
        raise ValueError("Internal size mismatch: payload smaller than header+salt (unexpected)")

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

    # Always save losslessly; if the user picked a non-PNG name, still write PNG to avoid LSB loss.
    img_out = Image.fromarray(flat.reshape(arr.shape), "RGB")
    try:
        img_out.save(out_path, format="PNG")
    except Exception:
        # Fallback: append .png if an exotic extension causes PIL confusion
        img_out.save(out_path + ".png", format="PNG")

def extract_image(in_path, password: str, use_rs=False, rs_nsym=0, lsb: int=1, spread=True, progress=None):
    from crypto_utils import MAGIC
    import struct

    img = Image.open(in_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    flat = arr.reshape(-1)
    total_slots = flat.size * lsb

    header_slots = HEADER_LEN * 8
    if header_slots > total_slots:
        raise ValueError("Image too small")

    # Try LSB in {current,1,2,3}
    from bit_utils import bits_to_bytes
    tried = [lsb] + [x for x in (1,2,3) if x != lsb]
    header = None
    for test_lsb in tried:
        hb = []
        for i in range(header_slots):
            bidx = i // test_lsb; off = i % test_lsb
            hb.append((int(flat[bidx]) >> off) & 1)
        cand = bits_to_bytes(np.array(hb, dtype=np.uint8))
        if cand[:len(MAGIC)] == MAGIC:
            header = cand
            lsb = test_lsb
            break
    if header is None:
        raise ValueError("Magic not found")
    # Re-read header with the detected LSB (for consistency and clarity)
    hb = []
    for i in range(header_slots):
        bidx = i // lsb; off = i % lsb
        hb.append((int(flat[bidx]) >> off) & 1)
    header = bits_to_bytes(np.array(hb, dtype=np.uint8))

    if header[:len(MAGIC)] != MAGIC: raise ValueError("Magic not found")
    
    pay_len = struct.unpack(">Q", header[len(MAGIC):len(MAGIC)+8])[0]
    payload_bits_needed = pay_len * 8

    salt_slots = SALT_LEN * 8
    # Capacity must cover: header + full payload (which already includes salt)
    if header_slots + payload_bits_needed > total_slots:
        raise ValueError("Capacity mismatch (carrier too small for embedded payload)")

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
