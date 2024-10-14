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
import pandas as pd  # Import Pandas

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

# Title and app navigation
st.title("On-Demand Logistics Platform")
menu = st.sidebar.radio("Navigation", ["User", "Driver", "Admin"])

# User Section
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

    if st.button("Book Now", key="user-book"):
        booking_datetime = datetime.combine(booking_date, booking_time)
        try:
            cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                             estimated_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                           (username, "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked"))
            conn.commit()
            st.success("Booking successful!")
            
            # Send confirmation email
            send_email(email, "Booking Confirmation", f"Your booking for a {vehicle_type} has been confirmed for {booking_datetime}!")

            # Get the ID of the last booking for feedback
            booking_id = cursor.lastrowid
            
            # Add feedback section
            feedback_rating = st.number_input("Rate your experience (1-5)", min_value=1, max_value=5)
            feedback_text = st.text_area("Provide your feedback")
            
            if st.button("Submit Feedback"):
                try:
                    cursor.execute('INSERT INTO reviews (booking_id, rating, feedback) VALUES (?, ?, ?)', 
                                   (booking_id, feedback_rating, feedback_text))
                    conn.commit()
                    st.success("Feedback submitted successfully!")
                except sqlite3.Error as e:
                    st.error(f"An error occurred while submitting feedback: {e}")

        except sqlite3.Error as e:
            st.error(f"An error occurred while booking: {e}")

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
    st.write('<div class="big-title">Track Your Vehicle</div>', unsafe_allow_html=True)
    tracking_booking_id = st.number_input("Enter Booking ID", min_value=1)
    
    cursor.execute('SELECT * FROM bookings WHERE id = ?', (tracking_booking_id,))
    tracking_info = cursor.fetchone()
    
    if tracking_info:
        # Display booking information
        st.write(f"**User:** {tracking_info[1]}")
        st.write(f"**Driver:** {tracking_info[2]}")
        st.write(f"**Pickup:** {tracking_info[3]}")
        st.write(f"**Dropoff:** {tracking_info[4]}")
        st.write(f"**Vehicle Type:** {tracking_info[5]}")
        st.write(f"**Estimated Cost:** ${tracking_info[6]:.2f}")
        st.write(f"**Status:** {tracking_info[7]}")

        # Display map if the booking is active
        if tracking_info[7] == "in_progress":
            mock_lat, mock_lon = get_mock_gps()
            m = folium.Map(location=[mock_lat, mock_lon], zoom_start=14)
            folium.Marker([mock_lat, mock_lon], tooltip="Your Vehicle").add_to(m)
            st_folium(m)

    # Option to view past bookings
    st.write('<div class="big-title">View Past Bookings</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings WHERE user = ?', (username,))
    past_bookings = cursor.fetchall()

    if past_bookings:
        past_bookings_df = pd.DataFrame(past_bookings, columns=["ID", "User", "Driver", "Pickup", "Dropoff", "Vehicle Type", "Estimated Cost", "Status"])
        st.dataframe(past_bookings_df)
    else:
        st.warning("No past bookings found.")

# Driver Section
elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)

    # Driver login
    driver_name = st.text_input("Driver Name")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        cursor.execute('SELECT * FROM drivers WHERE name = ? AND password = ?', (driver_name, password))
        driver_info = cursor.fetchone()

        if driver_info:
            st.success("Login successful!")

            # Display driver details
            st.write(f"**Name:** {driver_info[1]}")
            st.write(f"**Vehicle:** {driver_info[2]}")
            st.write(f"**Available:** {'Yes' if driver_info[3] else 'No'}")
            st.write(f"**Experience:** {driver_info[4]} years")
            st.write(f"**Earnings:** ${driver_info[5]:.2f}")

            # Accepting bookings
            if st.button("Accept Booking"):
                # Logic to accept booking (mocked for simplicity)
                st.success("Booking accepted!")
                # Update driver earnings
                earnings = calculate_earnings(driver_name)
                st.write(f"Total earnings: ${earnings:.2f}")

            # Track earnings
            if st.button("Track Earnings"):
                earnings = calculate_earnings(driver_name)
                st.write(f"Total earnings: ${earnings:.2f}")

        else:
            st.error("Invalid login credentials.")

# Admin Section
elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # Admin login
    admin_username = st.text_input("Admin Username")
    admin_password = st.text_input("Admin Password", type="password")

    if st.button("Login"):
        # Mocking admin authentication
        if admin_username == "admin" and admin_password == "admin":
            st.success("Admin login successful!")

            # View all bookings
            st.write("### All Bookings")
            cursor.execute('SELECT * FROM bookings')
            all_bookings = cursor.fetchall()

            if all_bookings:
                # Check the structure of all_bookings
                st.write(f"Total bookings found: {len(all_bookings)}")
                
                # Create a DataFrame for bookings
                df_bookings = pd.DataFrame(all_bookings, columns=["ID", "User", "Driver", "Pickup", "Dropoff", "Vehicle Type", "Estimated Cost", "Status"])
                st.dataframe(df_bookings)
            else:
                st.warning("No bookings found.")

            # View user feedback
            st.write('<div class="big-title">User Feedback</div>', unsafe_allow_html=True)

            cursor.execute('SELECT * FROM reviews')
            all_feedback = cursor.fetchall()

            if all_feedback:
                feedback_data = pd.DataFrame(all_feedback, columns=["ID", "Booking ID", "Rating", "Feedback"])
                st.dataframe(feedback_data)
            else:
                st.warning("No feedback available.")
        else:
            st.error("Invalid admin credentials.")

# Close the database connection
conn.close()
