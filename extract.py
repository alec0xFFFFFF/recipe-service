import pytesseract
from PIL import Image

def extractText(image_name):
    image = Image.open(image_name)
    text = pytesseract.image_to_string(image)
    return text
