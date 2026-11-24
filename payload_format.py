# payload_format.py
import struct
from crypto_utils import encrypt_bytes, decrypt_bytes, HEADER_LEN, SALT_LEN, MAGIC
from ecc_utils import rs_encode, rs_decode

# Inside the encrypted blob:
# [ b"SC01" ][ u16_be name_len ][ name_bytes ][ raw_secret_bytes ]
# (files from v1.0.6 and earlier may hold an RS-encoded secret here instead; see parse_payload)
FORMAT_TAG = b"SC01"


def _check_nsym(rs_nsym: int) -> None:
    # reedsolo works on 255-byte codewords: nsym parity bytes + (255 - nsym) data bytes.
    if not 0 < rs_nsym < 255:
        raise ValueError(f"ECC parity bytes must be between 1 and 254 (got {rs_nsym})")


def build_payload(secret_bytes: bytes, password: str, use_rs: bool = False, rs_nsym: int = 0, orig_name: str | None = None) -> bytes:
    """
    Without ECC:  MAGIC + >Q payload_len + salt + nonce + ciphertext + tag
    With ECC:     MAGIC + >Q payload_len + salt + RS(nonce + ciphertext + tag)
    Where ciphertext = AES-GCM( FORMAT_TAG + u16 name_len + name + secret )

    Reed-Solomon wraps the encrypted bytes (encrypt-then-ECC), so bit errors in the
    carrier are corrected *before* the GCM tag is checked. The salt stays raw: the
    extractor needs it to seed the bit permutation before it can read anything else.
    """
    # Optional filename
    name_bytes = b"" if orig_name is None else orig_name.encode("utf-8")
    if len(name_bytes) > 65535:
        raise ValueError("Filename too long to embed in payload header")

    # Inner plaintext that will be encrypted
    inner = FORMAT_TAG + struct.pack(">H", len(name_bytes)) + name_bytes + secret_bytes

    # Encrypt inner (returns salt + nonce + ciphertext + tag)
    payload = encrypt_bytes(password, inner)

    if use_rs:
        _check_nsym(rs_nsym)
        payload = payload[:SALT_LEN] + bytes(rs_encode(payload[SALT_LEN:], rs_nsym))

    # Prepend transport header expected by image/video writers:
    # MAGIC + 8-byte big-endian payload length
    header = MAGIC + struct.pack(">Q", len(payload))
    return header + payload


def _split_inner(blob: bytes) -> tuple[bytes, dict]:
    """Peel the optional SC01 inner header off a decrypted blob."""
    meta = {"filename": None}
    if len(blob) >= 6 and blob[:4] == FORMAT_TAG:
        name_len = struct.unpack(">H", blob[4:6])[0]
        off = 6
        if off + name_len <= len(blob):
            meta["filename"] = blob[off:off + name_len].decode("utf-8", errors="replace")
            return blob[off + name_len:], meta
    # no inner tag (or malformed name length): entire blob is the body
    return blob, meta


def parse_payload(full: bytes, password: str, use_rs: bool = False, rs_nsym: int = 0) -> tuple[bytes, dict]:
    """
    full: header (MAGIC + >Q len) + encrypted payload (see build_payload for both layouts)
    Returns: (raw_secret_bytes, {"filename": Optional[str]})

    With use_rs, the current layout (RS outside GCM) is tried first. If that fails,
    the legacy layout written by v1.0.6 and earlier (RS inside GCM, applied to the
    secret only) is tried, so older stego files still extract.
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

    if not use_rs:
        try:
            blob = decrypt_bytes(password, encrypted)
        except ValueError as e:
            raise ValueError(f"{e} (wrong password, damaged carrier, or the file was embedded "
                             "with different settings such as ECC or stealth mode)") from e
        return _split_inner(blob)

    _check_nsym(rs_nsym)
    salt = encrypted[:SALT_LEN]

    # Current layout: RS-decode outside the AES-GCM envelope, then decrypt.
    try:
        decoded = bytes(rs_decode(encrypted[SALT_LEN:], rs_nsym))
        blob = decrypt_bytes(password, salt + decoded)
        return _split_inner(blob)
    except Exception as e:
        new_err = e

    # Legacy layout (<= v1.0.6): decrypt first, then RS-decode the inner body.
    try:
        blob = decrypt_bytes(password, encrypted)
    except Exception:
        raise ValueError(
            f"ECC/decryption failed: {new_err}. Too many bit errors for ECC to correct, "
            "wrong password, or different settings (ECC parity bytes, stealth mode) than at embed time."
        ) from new_err
    body, meta = _split_inner(blob)
    try:
        body = bytes(rs_decode(body, rs_nsym))
    except Exception as e:
        raise ValueError(f"ECC decode failed: {e}") from e
    return body, meta


def split_header_salt(full_bytes: bytes) -> tuple[bytes, bytes]:
    """Convenience for embed/extract (header then SALT sequential)."""
    header = full_bytes[:HEADER_LEN]
    salt = full_bytes[HEADER_LEN:HEADER_LEN + SALT_LEN]
    return header, salt
