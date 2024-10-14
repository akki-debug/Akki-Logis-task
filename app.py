import streamlit as st
import sqlite3
from geopy.distance import geodesic
import random
import folium
from streamlit_folium import st_folium
from streamlit.components.v1 import html
import matplotlib.pyplot as plt
import altair as alt
import smtplib
from email.mime.text import MIMEText

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

# Create tables for users, drivers, and bookings
cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
              (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
               vehicle_type TEXT, estimated_cost REAL, status TEXT, date TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
              (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tracking
              (id INTEGER PRIMARY KEY, booking_id INTEGER, latitude REAL, longitude REAL)''')

conn.commit()

# Function to estimate price with dynamic pricing based on demand
def estimate_price(pickup, dropoff, vehicle_type):
    pickup_coords = tuple(map(float, pickup.split(',')))
    dropoff_coords = tuple(map(float, dropoff.split(',')))
    dist = geodesic(pickup_coords, dropoff_coords).km
    base_price = 5  # base price
    vehicle_multiplier = {'truck': 2, 'van': 1.5, 'car': 1.2}
    
    # Dynamic pricing based on demand
    cursor.execute('SELECT COUNT(*) FROM bookings WHERE status="booked"')
    active_jobs = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM drivers WHERE available=1')
    available_drivers = cursor.fetchone()[0]
    
    if available_drivers > 0 and active_jobs >= available_drivers:
        base_price *= 1.2  # Increase price by 20% during high demand
    
    return base_price + dist * vehicle_multiplier.get(vehicle_type, 1)

# Function to mock GPS location for tracking
def get_mock_gps():
    return (40.7128 + random.uniform(-0.01, 0.01), -74.0060 + random.uniform(-0.01, 0.01))

# Function to send an email notification
def send_email_notification(to_email, subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = 'your_email@example.com'
        msg['To'] = to_email

        with smtplib.SMTP('smtp.example.com', 587) as server:
            server.starttls()
            server.login('your_email@example.com', 'your_password')
            server.sendmail('your_email@example.com', to_email, msg.as_string())
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# Title and app navigation
st.title("On-Demand Logistics Platform")
menu = st.sidebar.radio("Navigation", ["User", "Driver", "Admin"])

if menu == "User":
    st.write('<div class="big-title">Book a Vehicle</div>', unsafe_allow_html=True)

    # User inputs
    pickup = st.text_input("Pickup Location (latitude,longitude)", "40.7128,-74.0060")
    dropoff = st.text_input("Dropoff Location (latitude,longitude)", "40.730610,-73.935242")
    vehicle_type = st.selectbox("Select Vehicle", ['car', 'van', 'truck'])
    date = st.date_input("Select Date for Booking")
    
    estimated_cost = estimate_price(pickup, dropoff, vehicle_type)
    
    st.write(f"**Estimated Price: ${estimated_cost:.2f}**")

    if st.button("Book Now", key="user-book"):
        # Insert booking into database
        cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                         estimated_cost, status, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                       ("user1", "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked", date))
        conn.commit()
        st.success("Booking successful!")
        send_email_notification("user_email@example.com", "Booking Confirmation", f"Your booking for {vehicle_type} is confirmed!")

    # Option to track bookings
    st.write('<div class="big-title">Track Your Vehicle</div>', unsafe_allow_html=True)
    booking_id = st.number_input("Enter Booking ID", min_value=1)
    
    cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
    booking = cursor.fetchone()

    if booking:
        st.write(f"**Booking Status: {booking[7]}**")
        
        if booking[7] != 'booked':
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

elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)

    # Driver sees available jobs
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
            st.success(f"Job {booking[0]} accepted")

    # Update job status
    st.write('<div class="sub-title">Update Job Status</div>', unsafe_allow_html=True)
    job_id = st.number_input("Enter Job ID", min_value=1, key="job-id-driver")
    new_status = st.selectbox("Select Status", ["en route", "goods collected", "delivered"])

    if st.button("Update Status", key="update-status-driver"):
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', (new_status, job_id))
        conn.commit()
        st.success(f"Status updated to {new_status}")

elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)
    
    # Manage drivers
    st.write('<div class="sub-title">Add New Driver</div>', unsafe_allow_html=True)
    driver_name = st.text_input("Driver Name")
    driver_vehicle = st.selectbox("Vehicle Type", ["car", "van", "truck"])
    if st.button("Add Driver", key="add-driver"):
        cursor.execute('INSERT INTO drivers (name, vehicle, available) VALUES (?, ?, ?)', 
                       (driver_name, driver_vehicle, 1))
        conn.commit()
        st.success("Driver added successfully!")

    # Show all drivers
    st.write('<div class="sub-title">All Drivers</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM drivers')
    drivers = cursor.fetchall()
    
    for driver in drivers:
        st.write(f"Driver: {driver[1]}, Vehicle: {driver[2]}, Available: {'Yes' if driver[3] else 'No'}")

    # Analytics: Completed trips
    st.write('<div class="sub-title">Completed Trips</div>', unsafe_allow_html=True)
    cursor.execute('SELECT date, COUNT(*) FROM bookings WHERE status = "delivered" GROUP BY date')
    trip_data = cursor.fetchall()

    if trip_data:
        dates, trip_counts = zip(*trip_data)
        trip_chart = alt.Chart(alt.Data(values=[{'date': d, 'count': c} for d, c in zip(dates, trip_counts)])).mark_line().encode(
            x='date:T',
            y='count:Q'
        )
        st.altair_chart(trip_chart, use_container_width=True)

# Ensure database changes are committed before closing connection
conn.commit()
conn.close()
