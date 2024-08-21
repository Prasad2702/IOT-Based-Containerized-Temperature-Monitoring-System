from flask import Flask, jsonify, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo
import Adafruit_DHT
import threading
import RPi.GPIO as GPIO
import time
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import json
import logging
import atexit
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kaushal'  # Ensure this is a secure random key

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Sensor setup
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 4

# AWS S3 Configuration
s3 = boto3.client(
    's3',
    region_name='aws_region_name',
    aws_access_key_id='your_access_key',
    aws_secret_access_key='your_secret_access_key'
)
bucket_name = 's3_bucket_name'  # Ensure this matches your S3 bucket name


# MySQL configuration
db_config = {
    'host': 'localhost',
    'user': 'newuser',
    'password': 'mysql',
    'database': 'sensor_db'
}

# Global variables to store sensor data
data = {
    'humidity': None,
    'temperature': None,
    'time': None
}

# AWS SES Configuration
ses_client = boto3.client(
    'ses',
    region_name='aws_region_name',
    aws_access_key_id='your_access_key',
    aws_secret_access_key='your_secret_access_key'
)
sender_email = "sender@gmail.com"
receiver_email = "receiver@gmail.com"

# GPIO setup
LED_PIN = 17  # GPIO pin for LED
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

def blink_led(duration=1, interval=0.5):
    end_time = time.time() + duration
    while time.time() < end_time:
        GPIO.output(LED_PIN, GPIO.HIGH)  # Turn LED on
        time.sleep(interval)
        GPIO.output(LED_PIN, GPIO.LOW)   # Turn LED off
        time.sleep(interval)

# Threshold values
TEMPERATURE_THRESHOLD = 24.0  # Example threshold for temperature in Celsius





def connect_to_database():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Connected to MySQL database")
            return connection
    except Error as e:
        print(f"Error: {e}")
        return None

def insert_data(username, humidity, temperature):
    connection = connect_to_database()
    if connection:
        try:
            table_name = f"sensor_data_{username}"
            cursor = connection.cursor()
            query = f"INSERT INTO {table_name} (humidity, temperature, timestamp) VALUES (%s, %s, %s)"
            cursor.execute(query, (humidity, temperature, datetime.now()))
            connection.commit()
        except Error as e:
            print(f"Insert data error: {e}")
        finally:
            cursor.close()
            connection.close()


def upload_to_s3(data, filename):
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=json.dumps(data),
            ContentType='application/json'
        )
        print(f"Data uploaded to S3 with filename: {filename}")
    except NoCredentialsError:
        print("Credentials not available.")
    except Exception as e:
        print(f"Failed to upload data to S3: {e}")

def fetch_data_from_last_10_minutes(username):
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor(dictionary=True)
        table_name = f"sensor_data_{username}"
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=60)
        query = f"""
            SELECT humidity, temperature, timestamp
            FROM {table_name}
            WHERE timestamp >= %s AND timestamp <= %s
        """
        cursor.execute(query, (start_time, end_time))
        rows = cursor.fetchall()
        cursor.close()
        connection.close()

        # Convert datetime objects to string
        for row in rows:
            row['timestamp'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        
        return rows


def send_email_alert(subject, body):
    try:
        response = ses_client.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [
                    receiver_email,
                ],
            },
            Message={
                'Subject': {
                    'Data': subject,
                },
                'Body': {
                    'Text': {
                        'Data': body,
                    },
                },
            }
        )
        print("Email alert sent:", response)
    except ClientError as e:
        print(f"Failed to send email alert: {e.response['Error']['Message']}")

def update_sensor_data(username):
    last_fetch_time = datetime.now()
    
    global data
    while True:
        humidity, temperature = Adafruit_DHT.read(DHT_SENSOR, DHT_PIN)
        if humidity is not None and temperature is not None:
            data['humidity'] = humidity
            data['temperature'] = temperature
            data['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	    
            insert_data(username, humidity, temperature)
	    
            # Check if thresholds are exceeded
            if temperature > TEMPERATURE_THRESHOLD:
                subject = "Sensor Alert: Threshold Exceeded"
                body = f"Temperature: {temperature:.1f}C\nHumidity: {humidity:.1f}%"
                #send_email_alert(subject, body)
                blink_led(duration=10)  # Blink LED for 10 seconds


            print(f"Updated data: {data}")  # Debug print
           
        else:
            print("Failed to retrieve data from sensor")

        # Check if 10 minutes have passed since the last fetch
        if datetime.now() - last_fetch_time >= timedelta(minutes=60):
            recent_data = fetch_data_from_last_10_minutes(username)
            if recent_data:
                filename = f"sensor_data_last_10_minutes_{username}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
                upload_to_s3(recent_data, filename)
            last_fetch_time = datetime.now()

        time.sleep(60)  # Adjust sleep time as necessary


@login_manager.user_loader
def load_user(user_id):
    connection = connect_to_database()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
        except Error as e:
            print(f"Load user error: {e}")
            user = None
        finally:
            cursor.close()
            connection.close()
        if user:
            return User(user['id'], user['username'])
    return None

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

@app.route('/')
@login_required
def index():
    username = current_user.username
    sensor_thread = threading.Thread(target=update_sensor_data, args=(username,))
    sensor_thread.daemon = True
    sensor_thread.start()
    return render_template('index.html', data=data)

@app.route('/data')
@login_required
def get_data():
    time_range = request.args.get('interval', '1min')  # Default to '1min' if no interval specified
    return jsonify(fetch_data_for_range(time_range))

def fetch_data_for_range(interval):
    connection = connect_to_database()
    if not connection:
        return {'error': 'Database connection failed'}

    try:
        username = current_user.username
        table_name = f"sensor_data_{username}"

        now = datetime.now()

        if interval == '5min':
            start_time = now - timedelta(minutes=5)
        elif interval == '30min':
            start_time = now - timedelta(minutes=30)
        elif interval == '1hour':
            start_time = now - timedelta(hours=1)
        elif interval == '1day':
            start_time = now - timedelta(days=1)
        elif interval == '1week':
            start_time = now - timedelta(weeks=1)
        else:
            start_time = now - timedelta(minutes=5)  # Default to 5 minutes

        cursor = connection.cursor(dictionary=True)
        query = f"SELECT * FROM {table_name} WHERE timestamp >= %s ORDER BY timestamp ASC"
        cursor.execute(query, (start_time,))
        rows = cursor.fetchall()
        data = {
            'time': [row['timestamp'].strftime('%Y-%m-%dT%H:%M:%S') for row in rows],  # ISO format for Chart.js
            'humidity': [row['humidity'] for row in rows],
            'temperature': [row['temperature'] for row in rows],
            'sensorData': rows  # Added to support table display
        }
        cursor.close()
    except Error as e:
        print(f"Fetch data error: {e}")
        data = {'error': 'Failed to fetch data'}
    finally:
        connection.close()
    
    return data

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        connection = connect_to_database()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
            except Error as e:
                print(f"Login error: {e}")
                user = None
            finally:
                cursor.close()
                connection.close()
            if user and check_password_hash(user['password'], password):
                user_obj = User(user['id'], user['username'])
                login_user(user_obj)
                # Start the sensor thread upon successful login
                sensor_thread = threading.Thread(target=update_sensor_data, args=(username,))
                sensor_thread.daemon = True
                sensor_thread.start()
                return redirect(url_for('index'))
            else:
                flash('Login failed. Check your username and/or password')
    return render_template('login.html', form=form)

@app.route('/fetch/<interval>')
def fetch_data(interval):
    data = fetch_data_for_range(interval)
    return render_template('index.html', data=data)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        connection = connect_to_database()
        if connection:
            try:
                cursor = connection.cursor()
                
                # Create user in 'users' table
                cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
                connection.commit()
                
                # Create sensor data table for the user
                table_name = f"sensor_data_{username}"
                create_table_query = f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        humidity FLOAT NOT NULL,
                        temperature FLOAT NOT NULL,
                        timestamp DATETIME NOT NULL
                    )
                """
                cursor.execute(create_table_query)
                connection.commit()
                
                flash('Your account has been created! You can now log in')
                return redirect(url_for('login'))
            except Error as e:
                print(f"Signup error: {e}")
                flash('An error occurred while creating your account.')
            finally:
                cursor.close()
                connection.close()
    return render_template('signup.html', form=form)

def cleanup_gpio():
    GPIO.cleanup()

atexit.register(cleanup_gpio)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
