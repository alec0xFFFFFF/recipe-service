import base64
import os

import requests
from openai import OpenAI


client = OpenAI()


class Agent:
    def __init__(self):
        pass

    def generate_response(self, system_prompt, prompt):
        try:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",
                     "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )

            return completion.choices[0].message.content
        except Exception as e:
            return str(e)

    def get_transcript(self, audio_stream):
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_stream,
            response_format="text"
        )
        return transcript

    def generate_vision_response(self, image_bytes, prompt):

        # Getting the base64 string
        base64_image = base64.b64encode(image_bytes.read()).decode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
        }

        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        return response.json()['choices'][0]['message']['content']

    def get_embedding(self, text, model="text-embedding-3-large"):
        text = text.replace("\n", " ")
        return client.embeddings.create(input=[text], model=model).data[0].embedding

    def get_image_variations(self, byte_array):
        response = client.images.create_variation(
            image=byte_array,
            n=1,
            model="dall-e-2",
            size="1024x1024"
        )
        return response.data[0].url

    def text_to_speech(self, text, voice_id="xNx17ebeAzBxoUz7iepQ", model_id="eleven_multilingual_v2"):
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        payload = {
            "model_id": model_id,
            "text": text,
            "voice_settings":  {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        headers = {"Content-Type": "application/json", 'xi-api-key': os.getenv("ELEVEN_LABS_KEY")}

        response = requests.request("POST", url, json=payload, headers=headers)
        return response
