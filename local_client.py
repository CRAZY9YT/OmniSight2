"""
local_client.py
---------------
OmniSight local vision client.
"""

import base64
import os
import threading

from openai import OpenAI


BASE_URL = os.environ.get(
    "OMNISIGHT_LOCAL_URL",
    "http://localhost:1234/v1"
)

MODEL_NAME = os.environ.get(
    "OMNISIGHT_LOCAL_MODEL",
    "qwen/qwen2.5-vl-7b"
)

MAX_TOKENS = 1200


SYSTEM_INSTRUCTION = """
You are OmniSight, a powerful desktop AI copilot with vision.

You can help with:
- Code errors and debugging
- Explaining anything on screen
- Summarizing documents
- Reading UI elements
- Understanding images and diagrams

Be accurate, concise and helpful.
Never invent information.
"""


CHAT_SYSTEM_INSTRUCTION = """
You are OmniSight, a smart desktop AI assistant.

Be conversational, helpful and concise.
Answer naturally.
"""


class LocalClient:

    def __init__(self):

        self.client = OpenAI(
            base_url=BASE_URL,
            api_key="lm-studio",
            timeout=60.0
        )

        self.last_attempts = 0

        self.request_lock = threading.Lock()

    def ask_direct_mode(
        self,
        screenshot_jpeg_bytes,
        user_question
    ):

        with self.request_lock:

            self.last_attempts = 1

            try:

                image_base64 = base64.b64encode(
                    screenshot_jpeg_bytes
                ).decode("utf-8")

                image_url = (
                    f"data:image/jpeg;base64,{image_base64}"
                )

                response = self.client.chat.completions.create(

                    model=MODEL_NAME,

                    messages=[

                        {
                            "role": "system",
                            "content": SYSTEM_INSTRUCTION
                        },

                        {
                            "role": "user",
                            "content": [

                                {
                                    "type": "text",
                                    "text": user_question
                                },

                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_url
                                    }
                                }

                            ]
                        }

                    ],

                    max_tokens=MAX_TOKENS
                )

                answer = response.choices[0].message.content

                finish_reason = response.choices[0].finish_reason

                print(
                    f"[Local Client Debug] "
                    f"finish_reason={finish_reason}"
                )

                if not answer or not answer.strip():

                    raise RuntimeError(
                        "Local model returned an empty response."
                    )

                return answer.strip()

            except Exception as exc:

                print(
                    f"[Local Client Debug] {exc}"
                )

                raise RuntimeError(
                    f"Local AI request failed: {exc}"
                ) from exc

    def ask_text_only(self, user_question):

        with self.request_lock:

            self.last_attempts = 1

            try:

                response = self.client.chat.completions.create(

                    model=MODEL_NAME,

                    messages=[

                        {
                            "role": "system",
                            "content": CHAT_SYSTEM_INSTRUCTION
                        },

                        {
                            "role": "user",
                            "content": user_question
                        }

                    ],

                    max_tokens=MAX_TOKENS
                )

                answer = response.choices[0].message.content

                if not answer or not answer.strip():

                    raise RuntimeError(
                        "Local model returned an empty response."
                    )

                return answer.strip()

            except Exception as exc:

                print(
                    f"[Local Client Debug] {exc}"
                )

                raise RuntimeError(
                    f"Local AI request failed: {exc}"
                ) from exc