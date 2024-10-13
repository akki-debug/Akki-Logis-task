import streamlit as st
import sqlite3
from geopy.distance import geodesic
import random
import folium
from streamlit_folium import st_folium

# Connect to SQLite database
conn = sqlite3.connect('logistics.db')
cursor = conn.cursor()

# Create tables for users, drivers, and bookings
cursor.execute('''CREATE TABLE IF NOT EXISTS bookings 
              (id INTEGER PRIMARY KEY, user TEXT, driver TEXT, pickup TEXT, dropoff TEXT, 
               vehicle_type TEXT, estimated_cost REAL, status TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS drivers
              (id INTEGER PRIMARY KEY, name TEXT, vehicle TEXT, available INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tracking
              (id INTEGER PRIMARY KEY, booking_id INTEGER, latitude REAL, longitude REAL)''')

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

# Title and app navigation
st.title("On-Demand Logistics Platform")
menu = st.sidebar.selectbox("Navigation", ["User", "Driver", "Admin"])

if menu == "User":
    st.header("Book a Vehicle")

    # User inputs
    pickup = st.text_input("Pickup Location (latitude,longitude)", "40.7128,-74.0060")
    dropoff = st.text_input("Dropoff Location (latitude,longitude)", "40.730610,-73.935242")
    vehicle_type = st.selectbox("Select Vehicle", ['car', 'van', 'truck'])
    estimated_cost = estimate_price(pickup, dropoff, vehicle_type)
    
    st.write(f"Estimated Price: ${estimated_cost:.2f}")

    if st.button("Book Now"):
        # Insert booking into database
        cursor.execute('''INSERT INTO bookings (user, driver, pickup, dropoff, vehicle_type, 
                         estimated_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                       ("user1", "unassigned", pickup, dropoff, vehicle_type, estimated_cost, "booked"))
        conn.commit()
        st.success("Booking successful!")

    # Option to track bookings
    st.header("Track Your Vehicle")
    booking_id = st.number_input("Enter Booking ID", min_value=1)
    
    cursor.execute('SELECT * FROM bookings WHERE id = ?', (booking_id,))
    booking = cursor.fetchone()

    if booking and booking[6] != 'booked':
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
    st.header("Driver Dashboard")

    # Driver sees available jobs
    st.subheader("Available Jobs")
    cursor.execute('SELECT * FROM bookings WHERE status = "booked"')
    bookings = cursor.fetchall()

    for booking in bookings:
        st.write(f"Booking ID: {booking[0]}, Pickup: {booking[3]}, Dropoff: {booking[4]}, Vehicle: {booking[5]}")
        if st.button(f"Accept Job {booking[0]}"):
            cursor.execute('UPDATE bookings SET driver = ?, status = ? WHERE id = ?', 
                           ("driver1", "accepted", booking[0]))
            conn.commit()
            st.success(f"Job {booking[0]} accepted")

    # Update job status
    st.subheader("Update Job Status")
    job_id = st.number_input("Enter Job ID", min_value=1)
    new_status = st.selectbox("Select Status", ["en route", "goods collected", "delivered"])

    if st.button("Update Status"):
        cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', (new_status, job_id))
        conn.commit()
        st.success(f"Status updated to {new_status}")

elif menu == "Admin":
    st.header("Admin Dashboard")
    
    # Manage drivers
    st.subheader("Add New Driver")
    driver_name = st.text_input("Driver Name")
    driver_vehicle = st.selectbox("Vehicle Type", ["car", "van", "truck"])
    if st.button("Add Driver"):
        cursor.execute('INSERT INTO drivers (name, vehicle, available) VALUES (?, ?, ?)', 
                       (driver_name, driver_vehicle, 1))
        conn.commit()
        st.success("Driver added successfully!")

    # Show all drivers
    st.subheader("All Drivers")
    cursor.execute('SELECT * FROM drivers')
    drivers = cursor.fetchall()
    
    for driver in drivers:
        st.write(f"Driver: {driver[1]}, Vehicle: {driver[2]}, Available: {'Yes' if driver[3] else 'No'}")

    # View analytics
    st.subheader("Fleet Analytics")

    # Total completed trips
    cursor.execute('SELECT COUNT(*) FROM bookings WHERE status = "delivered"')
    completed_trips = cursor.fetchone()[0]
    st.write(f"Total Completed Trips: {completed_trips}")

    # Average trip cost
    cursor.execute('SELECT AVG(estimated_cost) FROM bookings WHERE status = "delivered"')
    avg_cost = cursor.fetchone()[0]

    if avg_cost is not None:
        st.write(f"Average Trip Cost: ${avg_cost:.2f}")
    else:
        st.write("Average Trip Cost: N/A")

# Close the database connection when done
conn.close()
