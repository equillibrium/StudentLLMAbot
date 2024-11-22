import os

import google.generativeai as genai
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()


async def get_client_for_model(model):
    from main import MODEL_CHOICES, SYSTEM_MESSAGE
    if model == MODEL_CHOICES[0]:
        groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
        return groq_client

    elif model == MODEL_CHOICES[1]:
        groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
        return groq_client
    elif model == MODEL_CHOICES[2]:
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
    elif model == MODEL_CHOICES[3]:
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
        raise ValueError(f"Unknown model: {model}")
