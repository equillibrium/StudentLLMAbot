import os

from pylovepdf.tools.officepdf import OfficeToPdf


async def convert_to_pdf(file):
    t = OfficeToPdf(public_key=os.getenv("ILOVEPDF_PUB_KEY"),
                    verify_ssl=False, proxies=None)
    t.add_file(file_path=f'{file["path"] + file["name"]}')
    t.debug = False
    t.set_output_folder(f'{file['path']}')

    t.execute()

    pdf_name = t.download()

    t.delete_current_task()

    return pdf_name