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