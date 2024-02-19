import requests

url = "https://api.elevenlabs.io/v1/text-to-speech/xNx17ebeAzBxoUz7iepQ"

payload = {
    "text": "this is a test",
    "voice_settings": {
        "similarity_boost": 0,
        "stability": 0
    }
}
headers = {
    "xi-api-key": "e6efb39b8d5813b530ce5a6ad5f1c79a",
    "Content-Type": "application/json"
}

response = requests.request("POST", url, json=payload, headers=headers)
CHUNK_SIZE = 1024
with open('output.mp3', 'wb') as f:
    for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
        if chunk:
            f.write(chunk)
# print(response.text)
