# stego_video.py
import cv2, numpy as np
from bit_utils import bytes_to_bits, bits_to_bytes
from spread_utils import permuted_indices, chunk_seed
from crypto_utils import HEADER_LEN, SALT_LEN
from payload_format import parse_payload

def _quick_header_magic_ok(path, lsb_guess: int = 1) -> bool:
    """
    Reopen a just-written video and confirm we can read the MAGIC from the
    sequential header area. Uses the same LSB auto-detect you use at extract.
    Returns True if MAGIC found, else False.
    """
    import cv2, numpy as np, struct
    from crypto_utils import MAGIC, HEADER_LEN, SALT_LEN
    from bit_utils import bits_to_bytes

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return False
    w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    channels = 3
    header_slots = HEADER_LEN * 8
    salt_slots   = SALT_LEN   * 8
    slots_per_frame = max(1, w*h*channels*lsb_guess)
    seq_frames   = int(np.ceil((header_slots + salt_slots) / slots_per_frame))
    frames = []
    for _ in range(max(1, seq_frames)):
        ret, f = cap.read()
        if not ret:
            break
        frames.append(f)
    cap.release()
    if not frames:
        return False
    stacked = np.stack(frames, axis=0)
    flat = stacked.ravel()
    tried = [lsb_guess] + [x for x in (1,2,3) if x != lsb_guess]
    for test_lsb in tried:
        hb = []
        for i in range(header_slots):
            bidx = i // test_lsb; off = i % test_lsb
            if bidx >= flat.size:
                break
            hb.append((int(flat[bidx]) >> off) & 1)
        if not hb or len(hb) < header_slots:
            continue
        cand = bits_to_bytes(np.array(hb, dtype=np.uint8))
        if cand[:len(MAGIC)] == MAGIC:
            return True
    return False

def _write_bit(flat: np.ndarray, slot: int, lsb: int, bit: int):
    bidx, off = slot // lsb, slot % lsb
    flat[bidx] = (int(flat[bidx]) & ~(1<<off)) | ((bit & 1) << off)

def _read_bit(flat: np.ndarray, slot: int, lsb: int) -> int:
    bidx, off = slot // lsb, slot % lsb
    return (int(flat[bidx]) >> off) & 1

def embed_video_streaming(in_path, out_path, full_payload: bytes, password: str,
                         lsb: int=1, spread=True, chunk_frames: int=60,
                         codec="ffv1", progress=None):
    """
    Streaming embedding: processes frames in chunks. If use_ffv1=True, we write PNGs to a temp dir then call ffmpeg (see ffmpeg_wrap.py).
    """
    from ffmpeg_wrap import LosslessWriter
    cap = cv2.VideoCapture(in_path)
    if not cap.isOpened(): raise RuntimeError("Cannot open video")

    w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps= cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    channels = 3

    bits = bytes_to_bits(full_payload)
    need_bits = bits.size

    # capacity in slots across entire video
    total_slots = total_frames * w * h * channels * lsb
    if need_bits > total_slots: 
        cap.release()
        raise ValueError("Payload too large for this video with selected LSB (capacity exceeded)")

    # header + salt sequential occupy the first (HEADER_LEN+SALT_LEN)*8 slots of the stream
    header_slots = HEADER_LEN * 8
    salt_slots   = SALT_LEN   * 8
    rem_bits     = need_bits - (header_slots + salt_slots)
    if rem_bits < 0:
        cap.release()
        raise ValueError("Payload smaller than header+salt")

    # writer
    writer = LosslessWriter(out_path, w, h, fps, codec=codec)

    bit_idx = 0
    frame_cursor = 0
    chunk_index = 0

    # Pass 1: write header+salt sequentially at the very start
    # We can implement it by filling slots from the beginning across frames until these bits are done.
    def next_chunk_frames(n):
        frames = []
        for _ in range(n):
            ret, f = cap.read()
            if not ret: break
            frames.append(f)
        return frames

    # Helper: number of slots in N frames
    def slots_in_frames(nframes): return nframes * w * h * channels * lsb

    # First, enough frames to cover header+salt
    needed_seq_slots = header_slots + salt_slots
    seq_frames_needed = int(np.ceil(needed_seq_slots / (w*h*channels*lsb)))
    frames = next_chunk_frames(max(seq_frames_needed, 1))
    if not frames: 
        cap.release(); writer.close()
        raise RuntimeError("No frames in source")

    stacked = np.stack(frames, axis=0)
    flat = stacked.ravel()
    # embed header+salt sequentially
    for i in range(header_slots + salt_slots):
        _write_bit(flat, i, lsb, int(bits[i]))
    bit_idx = header_slots + salt_slots
    writer.write_frames(stacked)
    frame_cursor += len(frames)
    if progress: progress(bit_idx, need_bits)

    # Remaining bits: process in chunks
    seed_base = password.encode() + full_payload[HEADER_LEN:HEADER_LEN+SALT_LEN]
    slots_per_frame = w*h*channels*lsb

    while bit_idx < need_bits:
        frames = next_chunk_frames(chunk_frames)
        if not frames: break
        stacked = np.stack(frames, axis=0)
        flat = stacked.ravel()

        chunk_slots_total = flat.size *  lsb
        to_embed = min(chunk_slots_total, need_bits - bit_idx)
        if to_embed <= 0:
            writer.write_frames(stacked)
            frame_cursor += len(frames)
            break

        # permute indices within this chunk (deterministic per chunk)
        seed = chunk_seed(seed_base, chunk_index)
        idxs = permuted_indices(chunk_slots_total, seed, to_embed) if spread else np.arange(to_embed, dtype=np.int64)

        for i in range(to_embed):
            _write_bit(flat, int(idxs[i]), lsb, int(bits[bit_idx + i]))

        bit_idx += to_embed
        writer.write_frames(stacked)
        frame_cursor += len(frames)
        chunk_index += 1
        if progress: progress(bit_idx, need_bits)

    cap.release()
    writer.close()
    if bit_idx < need_bits:
        raise RuntimeError("Ran out of capacity before finishing payload")
        
    # --- Post-embed verification to catch any lossless/pix_fmt mishaps early
    if not _quick_header_magic_ok(out_path, lsb_guess=lsb):
        raise RuntimeError(
            "Verification failed: header magic not found in output video.\n\n"
            "This usually means the encoder path wasn't truly lossless or the pixel format changed.\n"
            "Tips:\n"
            "  • Prefer codec='ffv1' (Matroska .mkv) for exact per-pixel preservation.\n"
            "  • If using h264rgb, ensure ffmpeg uses libx264rgb with -crf 0, -preset veryslow, and -pix_fmt bgr24 (to match OpenCV BGR).\n"
            "  • Avoid any post-processing/transcoding tools that may rewrite frames."
        )

def extract_video_streaming(in_path, password: str, lsb: int=1, spread=True, chunk_frames: int=60,
                            use_rs=False, rs_nsym=0, progress=None):
    """Mirror the streaming embed logic:
       - Read header+salt sequentially from the first needed frames.
       - Then read ONLY subsequent chunks (chunk_index=0,1,...) and apply the same per-chunk permutation.
       NOTE: We intentionally DO NOT consume any leftover capacity from the initial header+salt batch,
             because the embedder didn't use it either.
    """
    import struct
    from crypto_utils import MAGIC, HEADER_LEN, SALT_LEN
    from bit_utils import bits_to_bytes

    cap = cv2.VideoCapture(in_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video")

    w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps= cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    channels = 3
    slots_per_frame = w * h * channels * lsb

    def next_chunk_frames(n):
        frames = []
        for _ in range(n):
            ret, f = cap.read()
            if not ret: break
            frames.append(f)
        return frames

    # ---- 1) Read just enough frames to cover header+salt, sequentially
    header_slots = HEADER_LEN * 8
    salt_slots   = SALT_LEN   * 8
    needed_seq   = header_slots + salt_slots
    seq_frames   = int(np.ceil(needed_seq / max(1, slots_per_frame)))

    frames = next_chunk_frames(max(1, seq_frames))
    if not frames:
        cap.release()
        raise RuntimeError("No frames")

    stacked = np.stack(frames, axis=0)
    flat = stacked.ravel()

    # Header (sequential, from slot 0) with LSB auto-detect like image path
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
            lsb = test_lsb   # lock in the detected LSB for the rest of extraction
            break
    if header is None:
        cap.release()
        raise ValueError("Magic not found")

    pay_len = struct.unpack(">Q", header[len(MAGIC):len(MAGIC)+8])[0]
    payload_bits_needed = pay_len * 8

    # Salt (immediately after header, sequential)
    sb = []
    for i in range(salt_slots):
        slot = header_slots + i
        bidx = slot // lsb; off = slot % lsb
        sb.append((int(flat[bidx]) >> off) & 1)
    salt_bytes = bits_to_bytes(np.array(sb, dtype=np.uint8))

    # Remaining payload bits (after salt)
    remaining_bits = payload_bits_needed - salt_slots
    if remaining_bits < 0:
        cap.release()
        raise ValueError("Payload length inconsistent (smaller than salt).")

    # IMPORTANT: Do NOT consume leftover capacity from the initial batch here.
    # The embedder started chunked permutation from the NEXT chunk, with chunk_index = 0.
    seed_base = password.encode() + salt_bytes
    pb = []
    pb.extend(sb)

    # ---- 2) Read subsequent chunks, chunk_index = 0,1,2...
    chunk_index = 0
    while remaining_bits > 0:
        frames = next_chunk_frames(chunk_frames)
        if not frames:
            break
        stacked = np.stack(frames, axis=0)
        flat = stacked.ravel()

        chunk_slots_total = flat.size * lsb
        take = min(remaining_bits, chunk_slots_total)

        if spread and take > 0:
            seed = chunk_seed(seed_base, chunk_index)
            idxs = permuted_indices(chunk_slots_total, seed, take)
        else:
            idxs = np.arange(take, dtype=np.int64)

        for i in range(take):
            slot = int(idxs[i])
            bidx = slot // lsb; off = slot % lsb
            pb.append((int(flat[bidx]) >> off) & 1)

        remaining_bits -= take
        chunk_index += 1

        if progress:
            done = payload_bits_needed - salt_slots - remaining_bits
            progress(done, payload_bits_needed - salt_slots)

    cap.release()
    if remaining_bits > 0:
        raise RuntimeError("Video ended before full payload was read")

    full = header + bits_to_bytes(np.array(pb, dtype=np.uint8))
    return parse_payload(full, password, use_rs=use_rs, rs_nsym=rs_nsym)
    

