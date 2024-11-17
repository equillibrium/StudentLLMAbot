import os
import time

import google.generativeai as genai
from dotenv import load_dotenv
from pylovepdf.tools.officepdf import OfficeToPdf

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])


async def convert_to_pdf(file):
    t = OfficeToPdf(public_key=os.getenv("ILOVEPDF_PUB_KEY"),
                    verify_ssl=False, proxies=None)
    t.add_file(file_path=os.path.join(file["path"], file["name"]))
    t.debug = False
    t.set_output_folder(file['path'])

    t.execute()

    converted_pdf = t.download()

    t.delete_current_task()

    return os.path.basename(converted_pdf)


async def upload_to_gemini(path, mime_type=None):
    """Uploads the given file to Gemini.

    See https://ai.google.dev/gemini-api/docs/prompting_with_media
    """
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file


async def get_from_gemini(name):
    file = genai.get_file(name)
    return file


async def wait_for_files_active(files):
    """Waits for the given files to be active.

    Some files uploaded to the Gemini API need to be processed before they can be
    used as prompt inputs. The status can be seen by querying the file's "state"
    field.

    This implementation uses a simple blocking polling loop. Production code
    should probably employ a more sophisticated approach.
    """
    print("Waiting for file processing...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
    print("...all files ready")
    print()


async def list_gemini_files():
    files = genai.list_files()
    # for f in files:
    #     print(f)
    return files
