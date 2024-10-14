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
from datetime import datetime, timedelta
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

# Create tables for users, drivers, bookings, reviews, and tracking if they don't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
                  (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
                   vehicle_type TEXT, estimated_cost REAL, status TEXT, favorite_driver INTEGER DEFAULT 0, 
                   booking_date TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
                  (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER, earnings REAL DEFAULT 0)''')

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

    # Booking time selection
    future_booking = st.checkbox("Future Booking?")
    if future_booking:
        booking_date = st.date_input("Select Date", datetime.now().date() + timedelta(days=1))
    else:
        booking_date = datetime.now().date()

    if st.button("Book Now", key="user-book"):
        # Insert booking into database
        cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                         estimated_cost, status, booking_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (username, "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked", booking_date))
        conn.commit()
        st.success("Booking successful!")
        
      

    # Option to cancel booking
    booking_id = st.number_input("Enter Booking ID to cancel", min_value=1)
    if st.button("Cancel Booking"):
        cursor.execute('DELETE FROM bookings WHERE id = ? AND status = "booked"', (booking_id,))
        conn.commit()
        st.success(f"Booking {booking_id} canceled successfully!")

    # Option to track bookings
    st.write('<div class="big-title">Track Your Vehicle</div>', unsafe_allow_html=True)
    booking_id = st.number_input("Enter Booking ID", min_value=1)
    
    cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
    booking = cursor.fetchone()

    if booking:
        st.write(f"**Booking Status: {booking[7]}**")
        
        if booking[6] != 'booked':
            # Show real-time map tracking
            cursor.execute('SELECT * FROM tracking WHERE booking_id = ?', (booking_id,))
            tracking_data = cursor.fetchone()
            
            if tracking_data:
                latitude, longitude = tracking_data[2], tracking_data[3]
            else:
                latitude, longitude = get_mock_gps()
                cursor.execute('INSERT INTO tracking (booking_id, latitude, longitude) VALUES (?, ?, ?)',
                               (booking_id, latitude, longitude))
                conn.commit()

            m = folium.Map(location=[latitude, longitude], zoom_start=12)
            folium.Marker([latitude, longitude], popup="Driver Location").add_to(m)
            st_folium(m, width=700)

        # User feedback and rating after delivery
        rating = st.slider("Rate your experience", 1, 5, key=f"rating-{booking_id}")
        feedback = st.text_area("Leave feedback", key=f"feedback-{booking_id}")
        
        if st.button("Submit Review", key=f"review-{booking_id}"):
            cursor.execute('INSERT INTO reviews (booking_id, rating, feedback) VALUES (?, ?, ?)',
                           (booking_id, rating, feedback))
            conn.commit()
            st.success(f"Thank you for your feedback on Booking {booking_id}!")

elif menu == "Driver":
    st.write('<div class="big-title">Driver Portal</div>', unsafe_allow_html=True)

    # Driver registration
    st.write("### Driver Registration")
    driver_name = st.text_input("Driver Name")
    vehicle = st.selectbox("Vehicle Type", ['car', 'van', 'truck'])
    
    if st.button("Register"):
        cursor.execute('INSERT OR IGNORE INTO drivers (name, vehicle, available) VALUES (?, ?, ?)', 
                       (driver_name, vehicle, 1))
        conn.commit()
        st.success("Driver registered successfully!")

    # Accept bookings
    st.write("### Available Bookings")
    cursor.execute('SELECT * FROM bookings WHERE driver = "unassigned"')
    bookings = cursor.fetchall()
    
    for b in bookings:
        st.write(f"Booking ID: {b[0]}, Pickup: {b[3]}, Dropoff: {b[4]}, Estimated Cost: ${b[6]:.2f}")
        if st.button(f"Accept Booking {b[0]}", key=f"accept-{b[0]}"):
            cursor.execute('UPDATE bookings SET driver = ?, status = "in transit" WHERE id = ?', 
                           (driver_name, b[0]))
            conn.commit()
            st.success(f"Booking {b[0]} accepted successfully!")

    # Show earnings
    if st.button("Show My Earnings"):
        earnings = calculate_earnings(driver_name)
        st.write(f"**Total Earnings: ${earnings:.2f}**")

    # Mark bookings as delivered
    st.write("### My Bookings In Transit")
    cursor.execute('SELECT * FROM bookings WHERE driver = ? AND status = "in transit"', (driver_name,))
    in_transit_bookings = cursor.fetchall()
    
    for b in in_transit_bookings:
        st.write(f"Booking ID: {b[0]}, Pickup: {b[3]}, Dropoff: {b[4]}, Estimated Cost: ${b[6]:.2f}")
        if st.button(f"Mark as Delivered {b[0]}", key=f"delivered-{b[0]}"):
            cursor.execute('UPDATE bookings SET status = "delivered" WHERE id = ?', (b[0],))
            conn.commit()
            st.success(f"Booking {b[0]} marked as delivered!")

elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # View all users
    st.write("### Users List")
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    
    for u in users:
        st.write(f"User: {u[1]}, Email: {u[2]}")

    # View all bookings
    st.write("### All Bookings")
    cursor.execute('SELECT * FROM bookings')
    bookings = cursor.fetchall()

    for b in bookings:
        st.write(f"Booking ID: {b[0]}, User: {b[1]}, Driver: {b[2]}, Status: {b[7]}")

    # Admin action logs
    st.write("### Admin Logs")
    cursor.execute('SELECT * FROM admin_logs ORDER BY timestamp DESC')
    logs = cursor.fetchall()
    
    for log in logs:
        st.write(f"{log[1]} - {log[2]}")

    if st.button("Clear Logs"):
        cursor.execute('DELETE FROM admin_logs')
        conn.commit()
        st.success("Logs cleared!")
