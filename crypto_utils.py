# crypto_utils.py
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256

MAGIC = b"STEGVID3"
SALT_LEN = 16
NONCE_LEN = 12
PBKDF2_ITERS = 200_000
KEY_LEN = 32
AES_TAG_LEN = 16
HEADER_LEN = len(MAGIC) + 8  # magic + 8-byte big-endian payload length

def derive_key(password: str, salt: bytes) -> bytes:
    return PBKDF2(password.encode("utf-8"), salt, dkLen=KEY_LEN, count=PBKDF2_ITERS, hmac_hash_module=SHA256)

def encrypt_bytes(password: str, plaintext: bytes) -> bytes:
    salt = get_random_bytes(SALT_LEN)
    key  = derive_key(password, salt)
    nonce = get_random_bytes(NONCE_LEN)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return salt + nonce + ciphertext + tag  # payload

def decrypt_bytes(password: str, payload: bytes) -> bytes:
    if len(payload) < SALT_LEN + NONCE_LEN + AES_TAG_LEN:
        raise ValueError("Payload too short")
    salt  = payload[:SALT_LEN]
    nonce = payload[SALT_LEN:SALT_LEN+NONCE_LEN]
    rest  = payload[SALT_LEN+NONCE_LEN:]
    if len(rest) < AES_TAG_LEN:
        raise ValueError("Missing tag")
    ciphertext, tag = rest[:-AES_TAG_LEN], rest[-AES_TAG_LEN:]
    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)
