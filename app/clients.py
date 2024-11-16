import os

import google.generativeai as genai
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

MODEL_CHOICES = os.getenv('MODEL_CHOICES').split(',')

system_message = ("Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой. "
                  "Отвечай всегда на русском языке, не переходи на английский, если не просят. "
                  "Если к тебе обратятся на английском языке или попросят помочь с английским, "
                  "можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах, "
                  "помогай студентам решать их проблемы с учебой.")

# Initialize clients for Groq, OpenAI, and Gemini
groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = genai.GenerationConfig(
    temperature=1,
    top_p=0.95,
    top_k=40,
    max_output_tokens=8192,
    response_mime_type="text/plain"
)

gemini_client = genai.GenerativeModel(
    model_name=MODEL_CHOICES[2],
    generation_config=generation_config,
    system_instruction=system_message
)


async def get_gemini_response():
    gemini_client.start_chat()
