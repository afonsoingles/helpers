from openai import OpenAI
import os

class AI:
    def __init__(self):
        self.openai = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL"), api_key=os.environ.get("OPENAI_API_KEY"))
    

    def prompt(self, text):
        response = self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": text},],
            max_tokens=1000,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
