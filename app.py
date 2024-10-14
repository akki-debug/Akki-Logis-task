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
import pandas as pd  # Import Pandas here

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
                  (id INTEGER PRIMARY KEY, username TEXT, email TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
                  (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
                   vehicle_type TEXT, estimated_cost REAL, status TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
                  (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tracking
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, latitude REAL, longitude REAL)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS reviews 
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, rating INTEGER, feedback TEXT)''')

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

# Title and app navigation
st.title("On-Demand Logistics Platform")
menu = st.sidebar.radio("Navigation", ["User", "Driver", "Admin"])

if menu == "User":
    st.write('<div class="big-title">Book a Vehicle</div>', unsafe_allow_html=True)

    # User registration/login
    st.write("### User Registration/Login")
    username = st.text_input("Username")
    email = st.text_input("Email")
    if st.button("Register/Login"):
        cursor.execute('INSERT OR IGNORE INTO users (username, email) VALUES (?, ?)', (username, email))
        conn.commit()
        st.success("User registered/logged in successfully!")

    # User inputs
    pickup = st.text_input("Pickup Location (latitude,longitude)", "40.7128,-74.0060")
    dropoff = st.text_input("Dropoff Location (latitude,longitude)", "40.730610,-73.935242")
    vehicle_type = st.selectbox("Select Vehicle", ['car', 'van', 'truck'])
    estimated_cost = estimate_price(pickup, dropoff, vehicle_type)
    
    st.write(f"**Estimated Price: ${estimated_cost:.2f}**")

    if st.button("Book Now", key="user-book"):
        # Insert booking into database
        cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                         estimated_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                       (username, "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked"))
        conn.commit()
        st.success("Booking successful!")
        
        # Send confirmation email
        send_email(email, "Booking Confirmation", f"Your booking for a {vehicle_type} has been confirmed!")

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
        if st.button("Submit Review", key=f"submit-review-{booking_id}"):
            cursor.execute('INSERT INTO reviews (booking_id, rating, feedback) VALUES (?, ?, ?)',
                           (booking_id, rating, feedback))
            conn.commit()
            st.success("Feedback submitted successfully!")

elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)

    # Driver availability scheduling
    st.write('<div class="sub-title">Set Availability</div>', unsafe_allow_html=True)
    availability_start = st.time_input("Available from", datetime.now().time())
    availability_end = st.time_input("Available until", datetime.now().time())
    
    st.write('<div class="sub-title">Available Jobs</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings WHERE status = "booked"')
    bookings = cursor.fetchall()

    for booking in bookings:
        st.write(f'<div class="card"><div class="card-header">Booking ID: {booking[0]}</div>'
                 f'Pickup: {booking[3]}<br>Dropoff: {booking[4]}<br>Vehicle: {booking[5]}</div>',
                 unsafe_allow_html=True)
        if st.button(f"Accept Job {booking[0]}", key=f"accept-{booking[0]}"):
            cursor.execute('UPDATE bookings SET driver = ?, status = ? WHERE id = ?', 
                           ("driver1", "accepted", booking[0]))
            conn.commit()
            st.success(f"Job {booking[0]} accepted!")

elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # Detailed Analytics Section
    st.write('<div class="big-title">Analytics Overview</div>', unsafe_allow_html=True)
    
    cursor.execute('SELECT COUNT(*) FROM bookings')
    total_bookings = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM bookings WHERE status = "delivered"')
    delivered_bookings = cursor.fetchone()[0]
    
    cursor.execute('SELECT AVG(rating) FROM reviews')
    avg_rating = cursor.fetchone()[0] or 0

    st.write(f"Total Bookings: {total_bookings}")
    st.write(f"Delivered Bookings: {delivered_bookings}")
    st.write(f"Average Rating: {avg_rating:.2f}")

    # Manage Users Section
    st.write('<div class="big-title">User Management</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()

    for user in users:
        st.write(f'User ID: {user[0]}, Username: {user[1]}, Email: {user[2]}')
        if st.button(f"Remove User {user[0]}", key=f"remove-user-{user[0]}"):
            cursor.execute('DELETE FROM users WHERE id = ?', (user[0],))
            conn.commit()
            st.success(f"User {user[1]} removed.")

    # Manage Drivers Section
    st.write('<div class="big-title">Driver Management</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM drivers')
    drivers = cursor.fetchall()

    for driver in drivers:
        st.write(f'Driver ID: {driver[0]}, Name: {driver[1]}, Vehicle: {driver[2]}, Available: {driver[3]}')
        if st.button(f"Toggle Availability {driver[0]}", key=f"toggle-driver-{driver[0]}"):
            new_availability = 1 - driver[3]  # Toggle availability
            cursor.execute('UPDATE drivers SET available = ? WHERE id = ?', (new_availability, driver[0]))
            conn.commit()
            status = "available" if new_availability else "not available"
            st.success(f"Driver {driver[1]} is now {status}.")

    # Manage Bookings Section
    st.write('<div class="big-title">Booking Management</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings')
    bookings = cursor.fetchall()

    for booking in bookings:
        st.write(f'Booking ID: {booking[0]}, User: {booking[1]}, Driver: {booking[2]}, '
                 f'Status: {booking[7]}')
        if st.button(f"Complete Booking {booking[0]}", key=f"complete-booking-{booking[0]}"):
            cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', ("delivered", booking[0]))
            conn.commit()
            st.success(f"Booking {booking[0]} completed.")

    # Review Moderation Section
    st.write('<div class="big-title">Review Management</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM reviews')
    reviews = cursor.fetchall()

    for review in reviews:
        st.write(f'Review ID: {review[0]}, Booking ID: {review[1]}, Rating: {review[2]}, Feedback: {review[3]}')
        if st.button(f"Delete Review {review[0]}", key=f"delete-review-{review[0]}"):
            cursor.execute('DELETE FROM reviews WHERE id = ?', (review[0],))
            conn.commit()
            st.success(f"Review {review[0]} deleted.")

# Close the database connection
conn.close() 
