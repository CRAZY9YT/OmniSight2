import base64
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

with open("vision_test.jpg", "rb") as image_file: 
       image_data = base64.b64encode(image_file.read()).decode("utf-8")

response = client.chat.completions.create(
    model="google/gemma-4-e4b",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe this image in 2 concise sentences. Focus on the main subject and what is happening."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            ]
        }
    ],
    temperature=0.2,
    max_tokens=800
)

print("\n[OmniSight Local Vision Test]")
print(response)
print("CONTENT:", repr(response.choices[0].message.content))
print("FINISH:", response.choices[0].finish_reason)
print("USAGE:", response.usage)