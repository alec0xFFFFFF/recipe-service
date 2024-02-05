import pytesseract
import cv2
import hashlib
import numpy as np


def extract_text(file):
    # Read the image
    image_bytes = file.read()

    # Convert the bytes to a numpy array
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)

    # Decode the image from the array
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    # Correct skew
    corrected_image = correct_skew(image)
    text = pytesseract.image_to_string(corrected_image)
    return text


def correct_skew(image):
    height, width = image.shape[:2]
    # Convert to grayscale and detect edges
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Detect lines in the image
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)

    # Calculate the angle of each line
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.arctan2(y2 - y1, x2 - x1) * 180. / np.pi
        angles.append(angle)

    # Calculate the median angle and rotate the image to correct skew
    median_angle = np.median(angles)
    rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    return cv2.warpAffine(rotated, cv2.getRotationMatrix2D((width / 2, height / 2), median_angle, 1), (width, height))


def calculate_md5(file_data):
    md5_hash = hashlib.md5()
    for chunk in file_data:
        md5_hash.update(chunk)
    return md5_hash.hexdigest()
