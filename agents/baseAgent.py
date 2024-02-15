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

    def generate_vision_response(self, image_bytes):

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
                            "text": "Extract all the text in this image of a recipe."
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
            "max_tokens": 300
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        print(response.json())
        return response.json()

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
