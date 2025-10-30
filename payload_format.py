# payload_format.py
import struct
from crypto_utils import encrypt_bytes, decrypt_bytes, HEADER_LEN, SALT_LEN, MAGIC
from ecc_utils import rs_encode, rs_decode

# Inside the encrypted blob:
# [ b"SC01" ][ u16_be name_len ][ name_bytes ][ raw_secret_bytes_or_RS ]
FORMAT_TAG = b"SC01"


def build_payload(secret_bytes: bytes, password: str, use_rs: bool = False, rs_nsym: int = 0, orig_name: str | None = None) -> bytes:
    """
    Returns: MAGIC + >Q payload_len + (salt + nonce + ciphertext + tag)
    Where ciphertext = AES-GCM( FORMAT_TAG + u16 name_len + name + raw_or_rs )
    """
    # Optional ECC on the raw secret before wrapping
    if use_rs:
        if rs_nsym <= 0:
            raise ValueError("ECC enabled but rs_nsym <= 0")
        secret_bytes = rs_encode(secret_bytes, rs_nsym)

    # Optional filename
    name_bytes = b"" if orig_name is None else orig_name.encode("utf-8")
    if len(name_bytes) > 65535:
        raise ValueError("Filename too long to embed in payload header")

    # Inner plaintext that will be encrypted
    inner = FORMAT_TAG + struct.pack(">H", len(name_bytes)) + name_bytes + secret_bytes

    # Encrypt inner (returns salt + nonce + ciphertext + tag)
    payload = encrypt_bytes(password, inner)

    # Prepend transport header expected by image/video writers:
    # MAGIC + 8-byte big-endian payload length
    header = MAGIC + struct.pack(">Q", len(payload))
    return header + payload


def parse_payload(full: bytes, password: str, use_rs: bool = False, rs_nsym: int = 0) -> tuple[bytes, dict]:
    """
    full: header (MAGIC + >Q len) + encrypted payload (salt+nonce+ciphertext+tag)
    Returns: (raw_secret_bytes, {"filename": Optional[str]})
    """
    # Verify and consume header
    if len(full) < HEADER_LEN + SALT_LEN:
        raise ValueError("Payload too short for header + salt")
    if full[:len(MAGIC)] != MAGIC:
        raise ValueError("Bad magic in header")

    pay_len = struct.unpack(">Q", full[len(MAGIC):len(MAGIC) + 8])[0]
    start = HEADER_LEN
    end = start + pay_len
    if end > len(full):
        raise ValueError("Truncated payload per header length")

    encrypted = full[start:end]
    blob = decrypt_bytes(password, encrypted)

    meta = {"filename": None}

    # Peel optional inner header
    if len(blob) >= 6 and blob[:4] == FORMAT_TAG:
        name_len = struct.unpack(">H", blob[4:6])[0]
        off = 6
        if off + name_len <= len(blob):
            meta["filename"] = blob[off:off + name_len].decode("utf-8", errors="replace")
            body = blob[off + name_len:]
        else:
            # malformed name length; treat whole blob as body
            body = blob
    else:
        # no inner tag; entire blob is the body
        body = blob

    # Optional ECC decode
    if use_rs:
        if rs_nsym <= 0:
            raise ValueError("ECC enabled but rs_nsym <= 0")
        try:
            body = rs_decode(body, rs_nsym)  # rs_decode returns bytes; raises on failure
        except Exception as e:
            raise ValueError(f"ECC decode failed: {e}")

    return body, meta


def split_header_salt(full_bytes: bytes) -> tuple[bytes, bytes]:
    """Convenience for embed/extract (header then SALT sequential)."""
    header = full_bytes[:HEADER_LEN]
    salt = full_bytes[HEADER_LEN:HEADER_LEN + SALT_LEN]
    return header, salt
