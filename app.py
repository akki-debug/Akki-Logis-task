import streamlit as st
import sqlite3
from geopy.distance import geodesic
import random
import folium
from streamlit_folium import st_folium
from streamlit.components.v1 import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import pandas as pd

# Custom CSS for better UI
custom_css = """
<style>
    .big-title { font-size: 30px; color: #3498db; font-weight: bold; margin-bottom: 20px;}
    .sub-title { font-size: 20px; color: #2ecc71; font-weight: bold; margin: 20px 0 10px; }
    .card { background-color: #f5f5f5; padding: 15px; border-radius: 10px; margin: 10px 0; border: 1px solid #ddd; }
    .card-header { font-size: 18px; font-weight: bold; }
    .btn-accept { background-color: #27ae60; color: white; padding: 8px 15px; border-radius: 5px; border: none; cursor: pointer; }
    .btn-accept:hover { background-color: #2ecc71; }
    .btn-status { background-color: #2980b9; color: white; padding: 8px 15px; border-radius: 5px; border: none; cursor: pointer; }
    .btn-status:hover { background-color: #3498db; }
</style>
"""
html(custom_css)

# Display the logistics image above the header
st.image("Logistic image.png", caption="Logistics Management", use_column_width=True)

# Connect to SQLite database
conn = sqlite3.connect('logistics.db')
cursor = conn.cursor()

# Create tables for users, drivers, bookings, reviews, tracking if they don't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
                  (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
                   vehicle_type TEXT, estimated_cost REAL, status TEXT, favorite_driver INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
                  (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER, 
                   experience INTEGER, earnings REAL DEFAULT 0, vehicle_capacity INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tracking
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, latitude REAL, longitude REAL)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS reviews 
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, rating INTEGER, feedback TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS admin_logs 
                  (id INTEGER PRIMARY KEY, action TEXT, timestamp TEXT)''')

conn.commit()

# Function to estimate price
def estimate_price(pickup, dropoff, vehicle_type):
    pickup_coords = tuple(map(float, pickup.split(',')))
    dropoff_coords = tuple(map(float, dropoff.split(',')))
    dist = geodesic(pickup_coords, dropoff_coords).km
    base_price = 5  # base price
    vehicle_multiplier = {'truck': 2, 'van': 1.5, 'car': 1.2}
    return base_price + dist * vehicle_multiplier.get(vehicle_type, 1)

# Function to mock GPS location for tracking
def get_mock_gps():
    return (40.7128 + random.uniform(-0.01, 0.01), -74.0060 + random.uniform(-0.01, 0.01))

# Function to send email notifications
def send_email(to_address, subject, body):
    try:
        from_address = "your_email@gmail.com"
        password = "your_app_specific_password"  # use app-specific password if 2FA is on

        # Set up MIME
        msg = MIMEMultipart()
        msg['From'] = from_address
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Establish an SMTP connection
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Start TLS encryption
        server.login(from_address, password)  # Login to the server
        
        # Send email
        server.sendmail(from_address, to_address, msg.as_string())
        server.quit()
        st.success("Confirmation email sent successfully!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# Function to log admin actions
def log_admin_action(action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO admin_logs (action, timestamp) VALUES (?, ?)', (action, timestamp))
    conn.commit()

# Function to calculate earnings for drivers
def calculate_earnings(driver_name):
    cursor.execute('SELECT SUM(estimated_cost) FROM bookings WHERE driver = ? AND status = "delivered"', (driver_name,))
    earnings = cursor.fetchone()[0] or 0
    return earnings

# Insert sample drivers data (20 drivers)
drivers_data = [
    ('John Doe', 'truck', 1, 5, 0, 1000),
    ('Jane Smith', 'van', 1, 3, 0, 800),
    ('Robert Johnson', 'car', 1, 7, 0, 500),
    ('Emily Davis', 'truck', 1, 10, 0, 1200),
    ('Michael Brown', 'van', 1, 4, 0, 900),
    ('David Wilson', 'truck', 1, 6, 0, 1300),
    ('Sarah Lee', 'car', 1, 2, 0, 600),
    ('Daniel Harris', 'van', 1, 5, 0, 1000),
    ('Olivia Martinez', 'truck', 1, 9, 0, 1500),
    ('William Clark', 'car', 1, 8, 0, 550),
    ('Sophia Robinson', 'van', 1, 6, 0, 950),
    ('James Lewis', 'truck', 1, 12, 0, 1700),
    ('Grace Walker', 'car', 1, 4, 0, 650),
    ('Liam Hall', 'van', 1, 5, 0, 1050),
    ('Isabella Allen', 'truck', 1, 15, 0, 2000),
    ('Ethan Young', 'car', 1, 7, 0, 700),
    ('Mia King', 'van', 1, 10, 0, 1200),
    ('Benjamin Scott', 'truck', 1, 13, 0, 1800),
    ('Charlotte Green', 'car', 1, 3, 0, 550),
    ('Lucas Wright', 'van', 1, 8, 0, 1100)
]

for driver in drivers_data:
    cursor.execute('''INSERT INTO drivers (name, vehicle, available, experience, earnings, vehicle_capacity) 
                      VALUES (?, ?, ?, ?, ?, ?)''', driver)
conn.commit()

# Title and app navigation
st.title("On-Demand Logistics Platform")
menu = st.sidebar.radio("Navigation", ["User", "Driver", "Admin"])

if menu == "User":
    st.write('<div class="big-title">Book a Vehicle</div>', unsafe_allow_html=True)

    # User registration/login
    st.write("### User Registration/Login")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Register/Login"):
        cursor.execute('INSERT OR IGNORE INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
        conn.commit()
        st.success("User registered/logged in successfully!")

    # Update profile
    if st.button("Update Profile"):
        new_email = st.text_input("New Email", value=email)
        new_password = st.text_input("New Password", type="password")
        cursor.execute('UPDATE users SET email = ?, password = ? WHERE username = ?', (new_email, new_password, username))
        conn.commit()
        st.success("Profile updated successfully!")

    # User inputs
    pickup = st.text_input("Pickup Location (latitude,longitude)", "40.7128,-74.0060")
    dropoff = st.text_input("Dropoff Location (latitude,longitude)", "40.730610,-73.935242")
    vehicle_type = st.selectbox("Select Vehicle", ['car', 'van', 'truck'])
    estimated_cost = estimate_price(pickup, dropoff, vehicle_type)
    
    st.write(f"**Estimated Price: ${estimated_cost:.2f}**")

    # Booking section
    st.write('<div class="big-title">Book Now</div>', unsafe_allow_html=True)
    booking_date = st.date_input("Select Booking Date", datetime.now())
    booking_time = st.time_input("Select Booking Time", datetime.now().time())

    if st.button("Confirm Booking"):
        # Assign a random available driver
        cursor.execute('SELECT name FROM drivers WHERE vehicle = ? AND available = 1 ORDER BY RANDOM() LIMIT 1', (vehicle_type,))
        driver = cursor.fetchone()
        if driver:
            cursor.execute('INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, estimated_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                           (username, driver[0], pickup, dropoff, vehicle_type, estimated_cost, 'confirmed'))
            conn.commit()
            send_email(email, "Booking Confirmed", f"Your booking with {driver[0]} has been confirmed!")
            st.success(f"Booking confirmed with {driver[0]}")
        else:
            st.error("No available drivers at the moment.")

if menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)

    # Driver login
    driver_name = st.text_input("Driver Name")
    if st.button("Login as Driver"):
        cursor.execute('SELECT * FROM drivers WHERE name = ?', (driver_name,))
        driver = cursor.fetchone()
        if driver:
            st.success(f"Welcome, {driver_name}!")
        else:
            st.error("Driver not found.")

    # Earnings and status
    if driver_name:
        earnings = calculate_earnings(driver_name)
        st.write(f"**Total Earnings: ${earnings:.2f}**")

        if st.button("Mark as Available"):
            cursor.execute('UPDATE drivers SET available = 1 WHERE name = ?', (driver_name,))
            conn.commit()
            st.success("Marked as available.")
        
        if st.button("Mark as Unavailable"):
            cursor.execute('UPDATE drivers SET available = 0 WHERE name = ?', (driver_name,))
            conn.commit()
            st.success("Marked as unavailable.")

if menu == "Admin":
    st.write('<div class="big-title">Admin Panel</div>', unsafe_allow_html=True)

    # Display driver stats
    st.write('<div class="sub-title">Driver Statistics</div>', unsafe_allow_html=True)
    cursor.execute('SELECT name, vehicle, experience, earnings FROM drivers')
    drivers = cursor.fetchall()
    df_drivers = pd.DataFrame(drivers, columns=['Name', 'Vehicle', 'Experience', 'Earnings'])
    st.dataframe(df_drivers)

    # Logs
    st.write('<div class="sub-title">System Logs</div>', unsafe_allow_html=True)
    cursor.execute('SELECT action, timestamp FROM admin_logs ORDER BY timestamp DESC')
    logs = cursor.fetchall()
    df_logs = pd.DataFrame(logs, columns=['Action', 'Timestamp'])
    st.dataframe(df_logs)

# Close the database connection when done
conn.close()
