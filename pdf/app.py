from flask import Flask, request, send_file
import os
import subprocess
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = '/tmp/uploads'
CONVERTED_FOLDER = '/tmp/converted'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

@app.route('/convert', methods=['POST'])
def convert_to_pdf():
    if 'file' not in request.files:
        return {"error": "No file provided"}, 400
    file = request.files['file']
    if file.filename == '':
        return {"error": "No file selected"}, 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    pdf_filename = filename.rsplit('.', 1)[0] + '.pdf'
    pdf_filepath = os.path.join(CONVERTED_FOLDER, pdf_filename)

    try:
        # Convert DOC to PDF using pandoc
        subprocess.run(['pandoc', filepath, '-o', pdf_filepath], check=True)
        return send_file(pdf_filepath, as_attachment=True)
    except subprocess.CalledProcessError as e:
        return {"error": "Failed to convert file"}, 500
    finally:
        # Clean up
        os.remove(filepath)
        if os.path.exists(pdf_filepath):
            os.remove(pdf_filepath)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
