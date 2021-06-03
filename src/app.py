from flask import Flask, render_template, request, session, send_file
from flask.helpers import url_for
from pymongo import MongoClient

import math
import config
import os
import hashlib
import shortuuid
import uuid
import data_format
import boto3, botostubs

from werkzeug.utils import redirect, secure_filename


app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = config.SECRET_KEY
app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER

pwd = os.getcwd()

# Database setup
client = MongoClient(config.MONGO_URI)
db = client.drive
users = db.users
shared = db.shared
print('Connected to Database')

# Connecting to s3
s3 = boto3.client("s3",
                  region_name="ap-south-1",
                  aws_access_key_id=config.AWS_KEY_ID,
                  aws_secret_access_key=config.AWS_SECRET_ACCESS)

print('Connected to S3')


# Routes
#---------------------------------
# Login Page
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if "uid" in session:
            return redirect(url_for('upage'))
        return render_template('login.html', temp='let pflag=false; let lflag=false;')

    if request.method == 'POST':
        email = request.form["email"]
        password = request.form["password"]

        # Checking if password exists
        check = users.find_one({"email": email}, {"_id":0, "email":1, "password":1, "uid":1})

        if check is None:
            return render_template('login.html', temp='let pflag=true; let lflag=false;')
        else:
            # Validating Password
            hash_pass = hashlib.sha256(password.encode()).hexdigest()

            if hash_pass == check["password"]:
                session["uid"] = check["uid"]
                return redirect(url_for('upage'))
            else:
                return render_template('login.html', temp='let pflag=true; let lflag=false;')


# Signup Page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    if request.method == 'POST':
        data = request.json

        check = users.find_one({"email": data["email"]})

        if check is None:
            password = data["pass"]
            hash_pass = hashlib.sha256(password.encode()).hexdigest()
            uid = str(uuid.uuid4())

            document = {
                "uid": uid,
                "username": data["username"],
                "email": data["email"],
                "tel": data["tel"],
                "password": hash_pass,
                "storage_limit": 10**8,
                "storage_used": 0,
                "files": []
            }

            try:
                users.insert_one(document)
                print("New User Added :: " + document["username"])
            except Exception as e:
                print("An error occured :: ", e)
                return {'response': 'failed'}    
            
            return {'response': 'success'}
        else:
            return {'response': 'euser'}

# User Page
@app.route('/home')
def upage():
    if "uid" in session:
        return render_template('page.html')  
    else:
        return render_template('login.html', temp='let pflag=false; let lflag=false;')

# File upload
@app.route('/upload', methods=['post'])
def upload():
    if request.method == 'POST':
        filesize = request.cookies.get('filesize')
        f = request.files['file']
        filename = f.filename
        print('{} {}'.format(filename, filesize))
        file_path = os.path.join(config.UPLOAD_FOLDER, filename)
        f.save(file_path)

        file_handling(f, filesize, file_path)

        return 'success'

# File download
@app.route('/download/<file_id>')
def download(file_id):
    if "uid" in session:
        uid = session["uid"]
        file_path = get_file(uid, file_id)
        
        return send_file(file_path)
    else:
        return render_template('login.html', temp='let pflag=false; let lflag=false;')

    
# Delete File
@app.route('/delete/<file_id>')
def delete(file_id):
    if "uid" in session:
        uid = session["uid"]

        filename = ""
        filesize = 0
        data = users.find_one({"uid": uid}, {"_id":0, "files":1})

        for i in range(len(data["files"])):
            if data["files"][i]["key"] == file_id:
                filename = data["files"][i]["name"] + '.' + data["files"][i]["ext"]
                filesize = int(data["files"][i]["bytes"])
                print(type(filesize))

        file_path = os.path.join(config.UPLOAD_FOLDER, filename)

        try:
            s3.delete_object(
                Bucket='cloudflaskdrivebucket',
                Key=file_id)
        except Exception as e:
            print('S3 delete error :: ', e)

        users.update_one({"uid": uid}, {"$pull": {"files": {"key": file_id}}})
        users.update_one({"uid": uid}, {"$inc": {"storage_used": -filesize}})

        os.remove(file_path)

    else:
        return render_template('login.html', temp='let pflag=false; let lflag=false;')


# Logout
@app.route('/logout')
def logout():
    session.pop('uid', None)
    return render_template('login.html', temp='let pflag=false; let lflag=true;')

# Data
@app.route('/data')
def data():
    if "uid" in session:
        uid = session["uid"]
        data = users.find_one({"uid": uid})

        temp = {
             "name": data["username"],
             "storage_used": data_format.data_converter(data["storage_used"]),
             "storage_limit": data_format.data_converter(data["storage_limit"]),
             "value": math.floor((data["storage_used"]/data["storage_limit"])*100),
             "files": data["files"]
        }

        return temp
    else:
        return render_template('login.html', temp='let pflag=false; let lflag=false;')


# Functions
#-------------------------------
# Processing and uploading files
def file_handling(f, filesize, file_path):
        uid = session["uid"]
        print(uid)
        key = shortuuid.uuid()
        temp = f.filename.split('.')
        
        file_dat = {
            "name": temp[0],
            "size": data_format.data_converter(filesize),
            "key": key,
            "ext": temp[1],
            "bytes": filesize
        }

        try:
            s3.upload_file(file_path, 'cloudflaskdrivebucket', key)  
        except Exception as e:
            print('S3 upload failed :: ', e)      

        users.update({"uid": uid}, { "$push": {"files": file_dat}, "$inc": {"storage_used": int(filesize)}})

# Get file details
def get_file(uid, file_id):
    filename = ""
    data = users.find_one({"uid": uid}, {"_id":0, "files":1})

    for i in range(len(data["files"])):
        if data["files"][i]["key"] == file_id:
            filename = data["files"][i]["name"] + '.' + data["files"][i]["ext"]
    
    return os.path.join(config.UPLOAD_FOLDER, filename)
