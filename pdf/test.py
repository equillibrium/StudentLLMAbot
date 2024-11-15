from pylovepdf.tools.officepdf import OfficeToPdf

t = OfficeToPdf('project_public_c28f3c765bab4cc4043c63a870eb6720_ioU2g25ce7e9f42ff1ca6a12a1dc3f25e548c',
                verify_ssl=False, proxies=None)
t.add_file('C:\\Users\\kotob\\Downloads\\Telegram Desktop\\Test_2.doc')
t.debug = False
t.set_output_folder('C:\\Users\\kotob\\Downloads\\Telegram Desktop\\')

t.execute()
t.download()
t.delete_current_task()