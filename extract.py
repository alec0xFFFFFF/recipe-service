import hashlib


def calculate_md5(file_data):
    md5_hash = hashlib.md5()
    for chunk in file_data:
        md5_hash.update(chunk)
    return md5_hash.hexdigest()
