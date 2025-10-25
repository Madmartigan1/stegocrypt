# payload_format.py
import struct
from crypto_utils import MAGIC, HEADER_LEN, SALT_LEN
from crypto_utils import encrypt_bytes, decrypt_bytes
from ecc_utils import rs_encode, rs_decode, REED_OK

def build_payload(plaintext: bytes, password: str, use_rs: bool=False, rs_nsym: int=0) -> bytes:
    enc = encrypt_bytes(password, plaintext)  # salt||nonce||ct||tag
    if use_rs:
        if not REED_OK: raise RuntimeError("Reed-Solomon requested but not available")
        enc = rs_encode(enc, rs_nsym)
    header = MAGIC + struct.pack(">Q", len(enc))
    return header + enc

def parse_payload(full_bytes: bytes, password: str, use_rs: bool=False, rs_nsym: int=0) -> bytes:
    if len(full_bytes) < HEADER_LEN: raise ValueError("Too short")
    if full_bytes[:len(MAGIC)] != MAGIC: raise ValueError("Magic mismatch")
    pay_len = struct.unpack(">Q", full_bytes[len(MAGIC):len(MAGIC)+8])[0]
    payload = full_bytes[HEADER_LEN:HEADER_LEN+pay_len]
    if use_rs:
        if not REED_OK: raise RuntimeError("Reed-Solomon requested but not available")
        payload = rs_decode(payload, rs_nsym)
    return decrypt_bytes(password, payload)

def split_header_salt(full_bytes: bytes):
    # convenience for embed/extract (header then SALT sequential)
    from crypto_utils import HEADER_LEN, SALT_LEN
    header = full_bytes[:HEADER_LEN]
    salt   = full_bytes[HEADER_LEN:HEADER_LEN+SALT_LEN]
    return header, salt
