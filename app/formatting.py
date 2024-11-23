import logging
import os

import requests
from aiogram.utils.formatting import Pre, as_marked_list, as_line, Code, Text, Bold
from dotenv import load_dotenv

load_dotenv()


def format_message(message: str) -> str:
    formatted_parts = []
    inside_code_block = False
    buffer = []
    code_block_language = None  # Track the language identifier for the code block

    for line in message.splitlines():
        if line.startswith('```'):
            # If inside code block, close it
            if inside_code_block:
                buffer.append("```")  # Close the current code block
                formatted_parts.append(("\n".join(buffer)))
                buffer = []
            # Toggle code block state
            inside_code_block = not inside_code_block
            # Capture the language identifier, if it exists
            if inside_code_block:
                code_block_language = line.lstrip('`')  # Capture language (e.g., python)
                buffer.append(f"```{code_block_language}")  # Start the code block with the language
            else:
                code_block_language = None  # Reset the language identifier
        elif inside_code_block:
            buffer.append(line)  # Collect lines inside the code block
        elif line.startswith('*'):
            clean_line = line.lstrip('*').strip()
            formatted_parts.append(as_marked_list(clean_line).as_markdown())
        else:
            # Handle inline code and escape text
            formatted_line = ""
            code = line.split("`")
            for i, part in enumerate(code):
                if i % 2 == 0:
                    # Escape regular text
                    formatted_line += Text(part).as_markdown()
                else:
                    # Format as inline code
                    formatted_line += Code(part).as_markdown()
            formatted_parts.append(formatted_line)

    # Add any remaining text inside a code block and ensure closing "```"
    if buffer:
        buffer.append("```")  # Ensure the code block ends properly
        formatted_parts.append(Pre("\n".join(buffer)).as_markdown())

    bold_formatted_parts = []
    for lines in formatted_parts:
        bold_lines =  lines.split("\\*\\*")
        for i, bold_line in enumerate(bold_lines):
            if i % 2 == 0:
                bold_formatted_parts.append(bold_line)
            else:
                bold_formatted_parts.append(Bold(bold_line).as_markdown())
        bold_formatted_parts.append("\n")

    result = "".join(bold_formatted_parts)

    return result


# def send_message(message):
#     BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
#     # Replace with the chat ID of the recipient
#     CHAT_ID = 217815700
#     # Your message
#     MESSAGE = message
#
#     # Telegram API URL
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
#
#     # Parameters for the API request
#     params = {
#         "chat_id": CHAT_ID,
#         "text": MESSAGE,
#         "parse_mode": "MARKDOWNV2",
#     }
#
#     print(url)
#     response = requests.post(url, data=params)
#
#     print(response.text)
#
# text = """
# Simple text
# A line with **bold** text
# ```python
# print("code here")
# print("and some more code")
# ```
# And a line with `code.py`
# Here's a list:
# *one
# *two
# """
#
# msg = format_message(text)
#
# send_message(msg)

text = """```python
code
```
"""

print(text.split('```')[1].split('\n')[0])