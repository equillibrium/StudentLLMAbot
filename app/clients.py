import os

import google.generativeai as genai
import httpx
import requests
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()


async def get_client_for_model(model):
    from main import SYSTEM_MESSAGE

    response = requests.get("https://console.groq.com", timeout=10)
    if response.status_code == 403:
        proxy = os.getenv('PROXY')
        async_client = httpx.AsyncClient(proxy=proxy)
        groq_client = AsyncGroq(api_key=os.getenv(
            'GROQ_API_KEY'), http_client=async_client)
    else:
        groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))

    try:
        if "gemini" in model:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

            generation_config = genai.GenerationConfig(
                temperature=1,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
                response_mime_type="text/plain"
            )
            gemini_client = genai.GenerativeModel(
                model_name=model,
                generation_config=generation_config,
                system_instruction=SYSTEM_MESSAGE
            )
            return gemini_client
        else:
            return groq_client
    except ValueError:
        raise ValueError(f"Unknown model: {model}")
