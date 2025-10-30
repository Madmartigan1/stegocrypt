# payload_format.py
import struct
from crypto_utils import encrypt_bytes, decrypt_bytes, HEADER_LEN, SALT_LEN
from ecc_utils import rs_encode, rs_decode, REED_OK

# StegoCrypt payload wrapper (inside the ciphertext-protected area)
# [ b"SC01" ][ u16_be name_len ][ name_bytes ][ raw_secret_bytes ]
FORMAT_TAG = b"SC01"

def build_payload(secret_bytes, password, use_rs=False, rs_nsym=0, orig_name=None):
    # Optionally protect the RAW SECRET with RS before wrapping
    if use_rs:
        if rs_nsym <= 0:
            raise ValueError("ECC enabled but rs_nsym <= 0")
        secret_bytes = rs_encode(secret_bytes, rs_nsym)
    if orig_name is None:
        name_bytes = b""
    else:
        name_bytes = orig_name.encode("utf-8")
    if len(name_bytes) > 65535:
        raise ValueError("Filename too long to embed in payload header")
    header = FORMAT_TAG + struct.pack(">H", len(name_bytes)) + name_bytes
    pt = header + secret_bytes
    return encrypt_bytes(password, pt)

def parse_payload(payload, password, use_rs=False, rs_nsym=0):
    blob = decrypt_bytes(password, payload)
    meta = {"filename": None}
    # Peel our inner header if present
    if len(blob) >= 6 and blob[:4] == FORMAT_TAG:
        name_len = struct.unpack(">H", blob[4:6])[0]
        off = 6
        if off + name_len <= len(blob):
            name_bytes = blob[off:off+name_len]
            meta["filename"] = name_bytes.decode("utf-8", errors="replace")
            body = blob[off+name_len:]
        else:
            # malformed; treat entire blob as body
            body = blob
    else:
        # no tag; treat entire blob as body
        body = blob

    # If ECC was used, decode the BODY (raw secret) now
    if use_rs:
        if rs_nsym <= 0:
            raise ValueError("ECC enabled but rs_nsym <= 0")
        decoded, status = rs_decode(body, rs_nsym)
        if status != REED_OK:
            raise ValueError(f"ECC decode failed (status={status})")
        body = decoded

    return body, meta
    
def split_header_salt(full_bytes: bytes):
    # convenience for embed/extract (header then SALT sequential)
    header = full_bytes[:HEADER_LEN]
    salt   = full_bytes[HEADER_LEN:HEADER_LEN+SALT_LEN]
    return header, salt
