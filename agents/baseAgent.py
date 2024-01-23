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

    def get_embedding(self, text, model="text-embedding-ada-002"):
        text = text.replace("\n", " ")
        return client.embeddings.create(input=[text], model=model).data[0].embedding