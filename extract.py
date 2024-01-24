import pytesseract
from PIL import Image
import hashlib

def extractText(image_name):
    image = Image.open(image_name)
    text = pytesseract.image_to_string(image)
    return text

def calculate_md5(file_data):
    md5_hash = hashlib.md5()
    for chunk in file_data:
        md5_hash.update(chunk)
    return md5_hash.hexdigest()
