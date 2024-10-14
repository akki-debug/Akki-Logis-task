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

# Create tables for users, drivers, bookings, reviews, tracking if they don't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT)''')

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

            # Create a Folium map
            map_ = folium.Map(location=[latitude, longitude], zoom_start=13)
            folium.Marker([latitude, longitude], popup="Current Location").add_to(map_)
            st_folium(map_, width=725)
        else:
            st.warning("Booking is still being processed. Tracking will be available once confirmed.")
    else:
        st.warning("No booking found with that ID.")

    # Feedback section
    st.write('<div class="big-title">Provide Feedback</div>', unsafe_allow_html=True)
    booking_id_for_feedback = st.number_input("Enter Booking ID to provide feedback", min_value=1)

    cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id_for_feedback,))
    feedback_booking = cursor.fetchone()

    if feedback_booking:
        st.write(f"**Booking Status: {feedback_booking[7]}**")
        
        if feedback_booking[7] == "delivered":
            rating = st.slider("Rate your experience (1 to 5)", 1, 5)
            feedback_text = st.text_area("Feedback (Optional)")
            
            if st.button("Submit Feedback"):
                try:
                    cursor.execute('INSERT INTO reviews (booking_id, rating, feedback) VALUES (?, ?, ?)', 
                                   (booking_id_for_feedback, rating, feedback_text))
                    conn.commit()
                    st.success("Feedback submitted successfully!")
                except sqlite3.Error as e:
                    st.error(f"An error occurred while submitting feedback: {e}")
        else:
            st.warning("Feedback can only be provided for completed bookings.")
    else:
        st.warning("No booking found with that ID.")

    # Display previous feedback
    st.write('<div class="big-title">Previous Feedback</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM reviews WHERE booking_id = ?', (booking_id_for_feedback,))
    previous_feedbacks = cursor.fetchall()

    if previous_feedbacks:
        feedback_df = pd.DataFrame(previous_feedbacks, columns=["ID", "Booking ID", "Rating", "Feedback"])
        st.dataframe(feedback_df)
    else:
        st.write("No feedback found for this booking ID.")

elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)

    # Driver registration/login
    st.write("### Driver Registration/Login")
    driver_name = st.text_input("Driver Name")
    vehicle = st.text_input("Vehicle Type")
    if st.button("Register/Login as Driver"):
        cursor.execute('INSERT OR IGNORE INTO drivers (name, vehicle, available) VALUES (?, ?, ?)', 
                       (driver_name, vehicle, 1))
        conn.commit()
        st.success("Driver registered/logged in successfully!")

    # Assigning jobs to drivers
    if st.button("View Available Bookings"):
        cursor.execute('SELECT * FROM bookings WHERE status = "booked"')
        available_bookings = cursor.fetchall()
        if available_bookings:
            for booking in available_bookings:
                st.write(f"**Booking ID:** {booking[0]} | **Pickup:** {booking[3]} | **Dropoff:** {booking[4]} | **Cost:** ${booking[6]}")
                if st.button(f"Accept Booking {booking[0]}"):
                    cursor.execute('UPDATE bookings SET driver = ?, status = ? WHERE id = ?', 
                                   (driver_name, "accepted", booking[0]))
                    conn.commit()
                    st.success(f"Booking {booking[0]} accepted!")
                    log_admin_action(f"Driver {driver_name} accepted booking {booking[0]}.")

    # Show earnings
    if st.button("View Earnings"):
        earnings = calculate_earnings(driver_name)
        st.write(f"**Total Earnings:** ${earnings:.2f}")

# Admin Interface
elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # View all bookings
    st.write("### All Bookings")
    cursor.execute('SELECT * FROM bookings')
    all_bookings = cursor.fetchall()

    if all_bookings:
        # Check the structure of all_bookings
        st.write(f"Total bookings found: {len(all_bookings)}")
        
        # Print the structure of the first booking for inspection
        st.write("Example booking data:", all_bookings[0])
        
        # Check the number of columns in the first booking
        num_columns = len(all_bookings[0])
        st.write(f"Number of columns in data: {num_columns}")
        
        # Create a DataFrame with the correct number of columns
        # Ensure that the columns match the actual number of columns returned
        expected_columns = ["ID", "User", "Driver", "Pickup", "Dropoff", "Vehicle Type", "Estimated Cost", "Status"]

        # Adjust expected_columns if necessary
        if num_columns == 9:  # Adjust this condition based on what extra column is present
            expected_columns.append("Extra Column Name")  # Replace with the actual name of the extra column

        try:
            df = pd.DataFrame(all_bookings, columns=expected_columns)
            st.dataframe(df)
        except ValueError as e:
            st.error(f"Error creating DataFrame: {e}")
    else:
        st.warning("No bookings found.")



            

# Close the database connection when done
conn.close()
