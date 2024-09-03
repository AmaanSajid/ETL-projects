from flask import Flask, request, render_template, redirect, url_for
from google.cloud import storage
import os
from google.cloud import aiplatform
app = Flask(__name__)

# Configure the GCS bucket name
GCS_BUCKET_NAME = 'client-data-bkt'

# Initialize the Google Cloud Storage client
storage_client = storage.Client()

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file:
            # Upload the file to GCS
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(file.filename)
            blob.upload_from_file(file)
            return f'File {file.filename} uploaded to {GCS_BUCKET_NAME}.'
    return render_template('index.html')

if __name__ == '__main__':
    # Ensure the environment variable for the GCS service account key is set
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "drgenai-7daf412ca440.json"
    project="drgenai"
    location="us-central1"
    aiplatform.init(project=project,location=location)
    app.run(debug=True)