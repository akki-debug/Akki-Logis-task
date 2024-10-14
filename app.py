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
import os

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
                  (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT, profile_picture TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
                  (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
                   vehicle_type TEXT, estimated_cost REAL, status TEXT, favorite_driver INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
                  (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER, earnings REAL DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tracking
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, latitude REAL, longitude REAL)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS reviews 
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, rating INTEGER, feedback TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS admin_logs 
                  (id INTEGER PRIMARY KEY, action TEXT, timestamp TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS promotions 
                  (id INTEGER PRIMARY KEY, code TEXT, discount REAL, active INTEGER)''')

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

# Function to upload profile picture
def upload_profile_picture(file):
    if file:
        file_path = os.path.join("uploads", file.name)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        return file_path
    return None

# Function to get booking history
def get_booking_history(username):
    cursor.execute('SELECT * FROM bookings WHERE user = ?', (username,))
    return cursor.fetchall()

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
    
    profile_picture = st.file_uploader("Upload Profile Picture", type=["png", "jpg", "jpeg"])

    if st.button("Register/Login"):
        profile_picture_path = upload_profile_picture(profile_picture)
        cursor.execute('INSERT OR IGNORE INTO users (username, email, password, profile_picture) VALUES (?, ?, ?, ?)', (username, email, password, profile_picture_path))
        conn.commit()
        st.success("User registered/logged in successfully!")

    # Update profile
    if st.button("Update Profile"):
        new_email = st.text_input("New Email", value=email)
        new_password = st.text_input("New Password", type="password")
        cursor.execute('UPDATE users SET email = ?, password = ? WHERE username = ?', (new_email, new_password, username))
        conn.commit()
        st.success("Profile updated successfully!")

    # Booking History
    st.write('<div class="big-title">Booking History</div>', unsafe_allow_html=True)
    booking_history = get_booking_history(username)
    if booking_history:
        for booking in booking_history:
            st.write(f"**Booking ID:** {booking[0]}, **Pickup:** {booking[3]}, **Dropoff:** {booking[4]}, **Status:** {booking[7]}")
    else:
        st.write("No booking history found.")

    # User inputs
    pickup = st.text_input("Pickup Location (latitude,longitude)", "40.7128,-74.0060")
    dropoff = st.text_input("Dropoff Location (latitude,longitude)", "40.730610,-73.935242")
    vehicle_type = st.selectbox("Select Vehicle", ['car', 'van', 'truck'])
    
    estimated_cost = estimate_price(pickup, dropoff, vehicle_type)
    st.write(f"**Estimated Price: ${estimated_cost:.2f}**")

    # Promotions
    st.write("### Promotions")
    promo_code = st.text_input("Enter Promo Code")
    cursor.execute('SELECT * FROM promotions WHERE code = ? AND active = 1', (promo_code,))
    promo = cursor.fetchone()
    if promo:
        estimated_cost *= (1 - promo[2] / 100)
        st.success(f"Promo applied! New Estimated Price: ${estimated_cost:.2f}")

    # Booking section
    st.write('<div class="big-title">Book Now</div>', unsafe_allow_html=True)
    booking_date = st.date_input("Select Booking Date", datetime.now())
    booking_time = st.time_input("Select Booking Time", datetime.now().time())

    if st.button("Book Now", key="user-book"):
        booking_datetime = datetime.combine(booking_date, booking_time)
        try:
            cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                             estimated_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                           (username, "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked"))
            conn.commit()
            st.success("Booking successful!")
            
            # Send email confirmation
            send_email(email, "Booking Confirmation", f"Your booking has been confirmed. Estimated cost: ${estimated_cost:.2f}")
        except Exception as e:
            st.error(f"Error in booking: {e}")

if menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)
    driver_name = st.text_input("Driver Name")
    vehicle_type = st.text_input("Vehicle Type")
    available = st.selectbox("Availability", ["Available", "Not Available"])
    
    # Register Driver
    if st.button("Register Driver"):
        cursor.execute('INSERT INTO drivers (name, vehicle, available) VALUES (?, ?, ?)', (driver_name, vehicle_type, int(available == "Available")))
        conn.commit()
        st.success("Driver registered successfully!")

    # Earnings Report
    st.write('<div class="big-title">Earnings Report</div>', unsafe_allow_html=True)
    earnings = calculate_earnings(driver_name)
    st.write(f"**Total Earnings: ${earnings:.2f}**")

    # Driver Availability Toggle
    if st.button("Toggle Availability"):
        cursor.execute('UPDATE drivers SET available = ? WHERE name = ?', (int(available == "Not Available"), driver_name))
        conn.commit()
        st.success("Availability status updated!")

    # Trip History
    st.write('<div class="big-title">Trip History</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings WHERE driver = ?', (driver_name,))
    trip_history = cursor.fetchall()
    if trip_history:
        for trip in trip_history:
            st.write(f"**Trip ID:** {trip[0]}, **Pickup:** {trip[3]}, **Dropoff:** {trip[4]}, **Status:** {trip[7]}")
    else:
        st.write("No trip history found.")

if menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # User Management
    st.write("### User Management")
    cursor.execute('SELECT * FROM users')
    user_list = cursor.fetchall()
    for user in user_list:
        st.write(f"User: {user[1]}, Email: {user[2]}")

    # Driver Management
    st.write("### Driver Management")
    cursor.execute('SELECT * FROM drivers')
    driver_list = cursor.fetchall()
    for driver in driver_list:
        st.write(f"Driver: {driver[1]}, Vehicle: {driver[2]}, Availability: {'Available' if driver[3] else 'Not Available'}")

    # Advanced Analytics
    st.write("### Analytics")
    total_bookings = cursor.execute('SELECT COUNT(*) FROM bookings').fetchone()[0]
    total_users = cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_drivers = cursor.execute('SELECT COUNT(*) FROM drivers').fetchone()[0]
    st.write(f"Total Bookings: {total_bookings}, Total Users: {total_users}, Total Drivers: {total_drivers}")

    # Promotion Management
    st.write("### Promotion Management")
    promo_code = st.text_input("Promo Code")
    discount = st.number_input("Discount (%)", min_value=0, max_value=100)
    if st.button("Add Promotion"):
        cursor.execute('INSERT INTO promotions (code, discount, active) VALUES (?, ?, ?)', (promo_code, discount, 1))
        conn.commit()
        st.success("Promotion added successfully!")

    # Logs
    st.write("### Admin Action Logs")
    cursor.execute('SELECT * FROM admin_logs')
    logs = cursor.fetchall()
    for log in logs:
        st.write(f"Action: {log[1]}, Timestamp: {log[2]}")

    # Feedback Management
    st.write("### User Feedback")
    cursor.execute('SELECT * FROM reviews')
    feedback_list = cursor.fetchall()
    for feedback in feedback_list:
        st.write(f"Booking ID: {feedback[1]}, Rating: {feedback[2]}, Feedback: {feedback[3]}")

# Close the connection
conn.close()
