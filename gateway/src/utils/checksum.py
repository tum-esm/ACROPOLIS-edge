from hashlib import sha256


def verify_checksum(software_data, checksum):
    return checksum == sha256(software_data).digest().hex()
