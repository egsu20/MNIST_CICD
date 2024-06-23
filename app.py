from flask import Flask, request, render_template
import os
import subprocess
import zipfile

app = Flask(__name__)

UPLOAD_FOLDER = os.path.abspath('mlflow_cicd/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    username = request.form.get('username')
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    if 'model' not in request.files:
        return render_template('index.html', message="Upload Failed: No model file part in the request"), 400

    model_file = request.files['model']
    if model_file.filename == '':
        return render_template('index.html', message="Upload Failed: No model file selected for uploading"), 400

    model_file_path = os.path.join(user_folder, model_file.filename)
    model_file.save(model_file_path)

    data_included = request.form.get('data_included')
    data_file_path = None
    if data_included == 'no':
        if 'data' not in request.files or request.files['data'].filename == '':
            return render_template('index.html', message="Upload Failed: No data file selected for uploading"), 400

        data_file = request.files['data']
        data_folder = os.path.join(user_folder, 'data')
        os.makedirs(data_folder, exist_ok=True)
        data_file_path = os.path.join(data_folder, data_file.filename)
        data_file.save(data_file_path)

        with zipfile.ZipFile(data_file_path, 'r') as zip_ref:
            zip_ref.extractall(data_folder)

    training_included = request.form.get('training_included')
    evaluation_included = request.form.get('evaluation_included')

    current_dir = os.getcwd()
    os.chdir(os.path.abspath('mlflow_cicd'))
    try:
        subprocess.run(['git', 'pull'], check=True)
        subprocess.run(['git', 'add', model_file_path], check=True)
        if data_file_path:
            subprocess.run(['git', 'add', data_folder], check=True)
        subprocess.run(['git', 'commit', '-m', f'Add new model and data files for user {username}'], check=True)
        subprocess.run(['git', 'push'], check=True)
    except subprocess.CalledProcessError as e:
        os.chdir(current_dir)
        return render_template('index.html', message=f"Upload Failed: {str(e)}"), 500

    if training_included == 'yes':
        try:
            subprocess.run(['python', 'scripts/train_model.py'], check=True)
        except subprocess.CalledProcessError as e:
            os.chdir(current_dir)
            return render_template('index.html', message=f"Training Failed: {str(e)}"), 500

    if evaluation_included == 'yes':
        try:
            subprocess.run(['python', 'scripts/evaluate_model.py'], check=True)
        except subprocess.CalledProcessError as e:
            os.chdir(current_dir)
            return render_template('index.html', message=f"Evaluation Failed: {str(e)}"), 500

    os.chdir(current_dir)
    return render_template('index.html', message="Upload Successful"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
