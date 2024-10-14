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

# Create tables if they don't exist
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

# Function to add feedback for bookings
def add_feedback(booking_id, rating, feedback):
    cursor.execute('INSERT INTO reviews (booking_id, rating, feedback) VALUES (?, ?, ?)', (booking_id, rating, feedback))
    conn.commit()

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

    # User inputs for booking
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
    booking = cursor.fetchone()

    if booking:
        st.write(f"**Booking Status: {booking[7]}**")
        
        if booking[7] != 'booked':
            # Show real-time map tracking
            cursor.execute('SELECT * FROM tracking WHERE booking_id = ?', (tracking_booking_id,))
            tracking_data = cursor.fetchone()
            
            if tracking_data:
                latitude, longitude = tracking_data[2], tracking_data[3]
                map_center = [latitude, longitude]
                folium_map = folium.Map(location=map_center, zoom_start=14)
                folium.Marker(map_center, tooltip="Current Location").add_to(folium_map)
                st_folium(folium_map, width=725)
            else:
                st.warning("No tracking data available yet.")
        else:
            st.warning("Booking is still being processed. Please check back later.")
    else:
        st.warning("Booking ID not found.")

    # View past bookings
    st.write('<div class="big-title">View Past Bookings</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings WHERE user = ?', (username,))
    past_bookings = cursor.fetchall()

    # Debugging output
    st.write("Debugging Output: Past Bookings Data", past_bookings)

    if past_bookings:
        past_bookings_df = pd.DataFrame(past_bookings, columns=["ID", "User", "Driver", "Pickup", "Dropoff", "Vehicle Type", "Estimated Cost", "Status"])
        st.dataframe(past_bookings_df)
    else:
        st.warning("No past bookings found.")

    # Add feedback for past bookings
    feedback_booking_id = st.number_input("Enter Booking ID to provide feedback", min_value=1)
    feedback_rating = st.slider("Rating (1-5)", 1, 5)
    feedback_text = st.text_area("Feedback")
    
    if st.button("Submit Feedback"):
        add_feedback(feedback_booking_id, feedback_rating, feedback_text)
        st.success("Feedback submitted successfully!")

# Driver Section
elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)
    driver_name = st.text_input("Enter your name")

    if st.button("Login as Driver"):
        earnings = calculate_earnings(driver_name)
        st.write(f"**Your total earnings: ${earnings:.2f}**")

        # View active bookings
        cursor.execute('SELECT * FROM bookings WHERE driver = ? AND status = "booked"', (driver_name,))
        active_bookings = cursor.fetchall()

        if active_bookings:
            active_bookings_df = pd.DataFrame(active_bookings, columns=["ID", "User", "Pickup", "Dropoff", "Vehicle Type", "Estimated Cost", "Status"])
            st.dataframe(active_bookings_df)
            if st.button("Accept Booking"):
                # Logic to accept booking
                booking_id_to_accept = st.number_input("Enter Booking ID to accept", min_value=1)
                cursor.execute('UPDATE bookings SET driver = ?, status = "accepted" WHERE id = ?', (driver_name, booking_id_to_accept))
                conn.commit()
                st.success(f"Booking {booking_id_to_accept} accepted successfully!")

        else:
            st.warning("No active bookings found.")

        # Option to update vehicle status
        if st.button("Mark as Delivered"):
            delivered_booking_id = st.number_input("Enter Booking ID to mark as delivered", min_value=1)
            cursor.execute('UPDATE bookings SET status = "delivered" WHERE id = ?', (delivered_booking_id,))
            conn.commit()
            st.success(f"Booking {delivered_booking_id} marked as delivered!")

# Admin Section
elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)
    admin_username = st.text_input("Admin Username")
    admin_password = st.text_input("Admin Password", type="password")

    if st.button("Login as Admin"):
        # Simple admin check (in a real scenario, use secure authentication)
        if admin_username == "admin" and admin_password == "password":
            st.success("Admin logged in successfully!")

            # View all bookings
            st.subheader("All Bookings")
            cursor.execute('SELECT * FROM bookings')
            all_bookings = cursor.fetchall()
            all_bookings_df = pd.DataFrame(all_bookings, columns=["ID", "User", "Driver", "Pickup", "Dropoff", "Vehicle Type", "Estimated Cost", "Status"])
            st.dataframe(all_bookings_df)

            # View driver earnings
            st.subheader("Driver Earnings")
            cursor.execute('SELECT name, SUM(estimated_cost) FROM drivers LEFT JOIN bookings ON drivers.name = bookings.driver GROUP BY name')
            driver_earnings = cursor.fetchall()
            st.write(driver_earnings)

            # Log admin actions
            if st.button("Log Admin Action"):
                log_admin_action("Admin accessed dashboard")
                st.success("Admin action logged.")

            # View admin logs
            st.subheader("Admin Logs")
            cursor.execute('SELECT * FROM admin_logs')
            admin_logs = cursor.fetchall()
            admin_logs_df = pd.DataFrame(admin_logs, columns=["ID", "Action", "Timestamp"])
            st.dataframe(admin_logs_df)

        else:
            st.error("Invalid admin credentials.")

# Close the database connection
conn.close()
