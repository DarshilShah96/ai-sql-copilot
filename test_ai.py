import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 👇 take user input
user_input = input("Enter your business question: ")

prompt = f"""
Convert the following business question into SQL query:

{user_input}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

print("\nGenerated SQL:\n")
print(response.choices[0].message.content)