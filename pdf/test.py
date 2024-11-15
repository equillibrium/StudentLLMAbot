import os

from dotenv import load_dotenv
from pylovepdf.tools.officepdf import OfficeToPdf

load_dotenv()


def convert_to_pdf():
    t = OfficeToPdf(public_key=os.getenv("ILOVEPDF_PUB_KEY"),
                    verify_ssl=False, proxies=None)
    t.add_file(file_path="C:\\Temp\\Test_2.doc")
    t.debug = False
    t.set_output_folder('C:\\Temp\\')

    t.execute()

    downloaded_filename = t.download()

    t.delete_current_task()

    return t.downloaded_filename


convert_to_pdf()
