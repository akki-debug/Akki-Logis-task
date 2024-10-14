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

# Create tables for users, drivers, bookings, goods, reviews, tracking, admin logs if they don't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
                  (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
                   vehicle_type TEXT, estimated_cost REAL, status TEXT, favorite_driver INTEGER DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
                  (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER, experience INTEGER, 
                   earnings REAL DEFAULT 0, vehicle_capacity REAL, average_rating REAL DEFAULT 0)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tracking
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, latitude REAL, longitude REAL)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS reviews 
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, rating INTEGER, feedback TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS goods
                  (id INTEGER PRIMARY KEY, booking_id INTEGER, description TEXT, 
                   weight REAL, dimensions TEXT, type TEXT)''')

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

    # Capture goods information
    goods_description = st.text_input("Goods Description")
    goods_weight = st.number_input("Goods Weight (kg)", min_value=0.0)
    goods_dimensions = st.text_input("Goods Dimensions (LxWxH in cm)")
    goods_type = st.text_input("Goods Type (e.g., fragile, electronics)")

    # Booking section
    st.write('<div class="big-title">Book Now</div>', unsafe_allow_html=True)
    booking_date = st.date_input("Select Booking Date", datetime.now())
    booking_time = st.time_input("Select Booking Time", datetime.now().time())

    if st.button("Book Now", key="user-book"):
        booking_datetime = datetime.combine(booking_date, booking_time)
        if booking_datetime > datetime.now():
            try:
                cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                                 estimated_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                               (username, "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked"))
                booking_id = cursor.lastrowid

                # Insert goods data
                cursor.execute('''INSERT INTO goods (booking_id, description, weight, dimensions, type) 
                                  VALUES (?, ?, ?, ?, ?)''', 
                               (booking_id, goods_description, goods_weight, goods_dimensions, goods_type))
                conn.commit()
                st.success("Booking and goods details added successfully!")
                
                # Send confirmation email
                send_email(email, "Booking Confirmation", f"Your booking for a {vehicle_type} has been confirmed for {booking_datetime}!")
            except sqlite3.Error as e:
                st.error(f"An error occurred while booking: {e}")
        else:
            st.error("Booking time must be in the future.")

    # Option to cancel booking
    booking_id = st.number_input("Enter Booking ID to cancel", min_value=1)
    if st.button("Cancel Booking"):
        try:
            cursor.execute('DELETE FROM bookings WHERE id = ? AND status = "booked"', (booking_id,))
            conn.commit()
            st.success(f"Booking {booking_id} canceled successfully!")
        except sqlite3.Error as e:
            st.error(f"An error occurred while canceling the booking: {e}")

    # Option to track bookings
    st.write('<div class="sub-title">Track Your Booking</div>', unsafe_allow_html=True)
    booking_id = st.number_input("Enter Booking ID to track", min_value=1, key="track-booking")
    if st.button("Track Booking"):
        cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
        booking = cursor.fetchone()
        if booking:
            pickup_coords = tuple(map(float, booking[3].split(',')))
            dropoff_coords = tuple(map(float, booking[4].split(',')))

            # Display booking status and map
            st.write(f"**Booking Status:** {booking[7]}")
            st.write("### Pickup & Dropoff Locations:")
            map_obj = folium.Map(location=pickup_coords, zoom_start=12)
            folium.Marker(pickup_coords, tooltip="Pickup", icon=folium.Icon(color="green")).add_to(map_obj)
            folium.Marker(dropoff_coords, tooltip="Dropoff", icon=folium.Icon(color="red")).add_to(map_obj)
            folium.PolyLine([pickup_coords, dropoff_coords], color="blue").add_to(map_obj)
            st_folium(map_obj, width=700, height=500)
        else:
            st.error(f"No booking found with ID {booking_id}.")

    # Provide feedback on booking
    st.write('<div class="sub-title">Provide Feedback</div>', unsafe_allow_html=True)
    rating = st.slider("Rate your experience (1-5)", 1, 5)
    feedback = st.text_area("Additional feedback/comments")
    if st.button("Submit Feedback"):
        try:
            cursor.execute('INSERT INTO reviews (booking_id, rating, feedback) VALUES (?, ?, ?)', (booking_id, rating, feedback))
            conn.commit()
            st.success("Feedback submitted successfully!")
        except sqlite3.Error as e:
            st.error(f"An error occurred while submitting feedback: {e}")

elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)
    
    driver_name = st.text_input("Enter your name")
    
    if st.button("Login/Register"):
        cursor.execute('INSERT OR IGNORE INTO drivers (name, vehicle, available, experience, vehicle_capacity) VALUES (?, ?, ?, ?, ?)', 
                       (driver_name, "van", 1, 5, 800))
        conn.commit()
        st.success(f"Welcome, {driver_name}! You are now registered.")
    
    st.write("### Available Bookings")
    cursor.execute('SELECT * FROM bookings WHERE status = "booked" AND driver = "unassigned"')
    bookings = cursor.fetchall()
    for booking in bookings:
        st.write(f"**Booking ID:** {booking[0]}, Pickup: {booking[3]}, Dropoff: {booking[4]}, Estimated Cost: ${booking[6]:.2f}")
        if st.button("Accept Booking", key=f"accept-{booking[0]}"):
            cursor.execute('UPDATE bookings SET driver = ?, status = "accepted" WHERE id = ?', (driver_name, booking[0]))
            conn.commit()
            st.success(f"Booking {booking[0]} accepted successfully!")
    
    st.write("### Current Deliveries")
    cursor.execute('SELECT * FROM bookings WHERE driver = ? AND status = "accepted"', (driver_name,))
    deliveries = cursor.fetchall()
    for delivery in deliveries:
        st.write(f"**Booking ID:** {delivery[0]}, Pickup: {delivery[3]}, Dropoff: {delivery[4]}, Estimated Cost: ${delivery[6]:.2f}")
        if st.button("Mark as Delivered", key=f"delivered-{delivery[0]}"):
            cursor.execute('UPDATE bookings SET status = "delivered" WHERE id = ?', (delivery[0],))
            conn.commit()
            st.success(f"Booking {delivery[0]} marked as delivered!")
    
    # Show driver earnings
    st.write("### Driver Earnings")
    earnings = calculate_earnings(driver_name)
    st.write(f"**Total Earnings:** ${earnings:.2f}")

    # Option for drivers to update their location (mocked with random GPS data)
    if st.button("Update GPS Location"):
        new_location = get_mock_gps()
        cursor.execute('INSERT INTO tracking (booking_id, latitude, longitude) VALUES (?, ?, ?)', (booking_id, new_location[0], new_location[1]))
        conn.commit()
        st.success(f"GPS location updated: {new_location}")

elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # Show all bookings
    st.write('<div class="sub-title">All Bookings</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings')
    all_bookings = cursor.fetchall()
    df_bookings = pd.DataFrame(all_bookings, columns=['ID', 'User', 'Driver', 'Pickup', 'Dropoff', 'Vehicle', 'Cost', 'Status'])
    st.dataframe(df_bookings)

    # Show all users
    st.write('<div class="sub-title">All Users</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM users')
    all_users = cursor.fetchall()
    df_users = pd.DataFrame(all_users, columns=['ID', 'Username', 'Email', 'Password'])
    st.dataframe(df_users)

    # Show all drivers
    st.write('<div class="sub-title">All Drivers</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM drivers')
    all_drivers = cursor.fetchall()
    df_drivers = pd.DataFrame(all_drivers, columns=['ID', 'Name', 'Vehicle', 'Available', 'Experience', 'Earnings', 'Capacity', 'Rating'])
    st.dataframe(df_drivers)

    # Show all feedback/reviews
    st.write('<div class="sub-title">All Feedback/Reviews</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM reviews')
    all_reviews = cursor.fetchall()
    df_reviews = pd.DataFrame(all_reviews, columns=['ID', 'Booking ID', 'Rating', 'Feedback'])
    st.dataframe(df_reviews)

    # Show admin logs
    st.write('<div class="sub-title">Admin Logs</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM admin_logs')
    admin_logs = cursor.fetchall()
    df_logs = pd.DataFrame(admin_logs, columns=['ID', 'Action', 'Timestamp'])
    st.dataframe(df_logs)

# Sample drivers data
drivers_data = [
    ('John Doe', 'truck', 1, 5, 0, 1000),
    ('Jane Smith', 'van', 1, 3, 0, 800),
    ('Robert Johnson', 'car', 1, 7, 0, 500),
    ('Emily Davis', 'truck', 1, 10, 0, 1200),
    ('Michael Brown', 'van', 1, 4, 0, 900),
    ('Sarah Wilson', 'car', 1, 2, 0, 400),
    ('David Martinez', 'truck', 1, 8, 0, 1500),
    ('Laura Taylor', 'van', 1, 6, 0, 750),
    ('Chris Anderson', 'car', 1, 5, 0, 550),
    ('Jessica Thomas', 'truck', 1, 9, 0, 1300),
    ('Daniel Jackson', 'van', 1, 3, 0, 850),
    ('Sophia White', 'car', 1, 1, 0, 300),
    ('Matthew Harris', 'truck', 1, 7, 0, 1000),
    ('Olivia Lewis', 'van', 1, 5, 0, 800),
    ('James Lee', 'car', 1, 6, 0, 600),
    ('Isabella Clark', 'truck', 1, 4, 0, 1100),
    ('Alexander Walker', 'van', 1, 2, 0, 700),
    ('Mia Hall', 'car', 1, 3, 0, 500),
    ('William Allen', 'truck', 1, 8, 0, 1400),
    ('Charlotte Young', 'van', 1, 6, 0, 750)
]

# Insert sample drivers into the database
for driver in drivers_data:
    cursor.execute('INSERT INTO drivers (name, vehicle, available, experience, vehicle_capacity) VALUES (?, ?, ?, ?, ?)', driver)
conn.commit()
st.success("20 sample drivers added to the database successfully!")
