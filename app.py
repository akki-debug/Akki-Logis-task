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

# Create tables for users, drivers, bookings, reviews, and tracking
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

    # User profile management
    st.write('<div class="big-title">User Profile</div>', unsafe_allow_html=True)
    user_info = cursor.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if user_info:
        st.write(f"**Username:** {user_info[1]}")
        st.write(f"**Email:** {user_info[2]}")

        new_username = st.text_input("Update Username", value=user_info[1])
        new_email = st.text_input("Update Email", value=user_info[2])
        
        if st.button("Update Profile"):
            cursor.execute('UPDATE users SET username = ?, email = ? WHERE id = ?', 
                           (new_username, new_email, user_info[0]))
            conn.commit()
            st.success("Profile updated successfully!")

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

    # View Booking History
    st.write('<div class="big-title">Booking History</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings WHERE user = ?', (username,))
    bookings_history = cursor.fetchall()

    if bookings_history:
        for booking in bookings_history:
            st.write(f'Booking ID: {booking[0]}, Status: {booking[7]}, Pickup: {booking[3]}, Dropoff: {booking[4]}')
    else:
        st.write("No bookings found.")

elif menu == "Driver":
    st.write('<div class="big-title">Driver Dashboard</div>', unsafe_allow_html=True)

    # Driver availability scheduling
    st.write('<div class="sub-title">Set Availability</div>', unsafe_allow_html=True)
    availability_start = st.time_input("Availability Start Time")
    availability_end = st.time_input("Availability End Time")
    if st.button("Set Availability"):
        st.success(f"Driver availability set from {availability_start} to {availability_end}.")

    # Driver performance metrics
    st.write('<div class="big-title">Driver Performance Metrics</div>', unsafe_allow_html=True)
    driver_name = st.text_input("Enter Driver Name")
    
    cursor.execute('SELECT COUNT(*) FROM bookings WHERE driver = ? AND status = "delivered"', (driver_name,))
    completed_jobs = cursor.fetchone()[0]

    cursor.execute('SELECT AVG(rating) FROM reviews WHERE booking_id IN (SELECT id FROM bookings WHERE driver = ?)', (driver_name,))
    avg_rating = cursor.fetchone()[0]

    st.write(f"Completed Jobs: {completed_jobs}")
    st.write(f"Average Rating: {avg_rating:.2f}" if avg_rating else "No ratings available.")

    # Accepting bookings
    st.write('<div class="sub-title">Available Bookings</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings WHERE driver = "unassigned"')
    available_bookings = cursor.fetchall()

    for booking in available_bookings:
        st.write(f'Booking ID: {booking[0]}, Pickup: {booking[3]}, Dropoff: {booking[4]}, Estimated Cost: ${booking[6]:.2f}')
        if st.button(f"Accept Booking {booking[0]}", key=f"accept-{booking[0]}"):
            cursor.execute('UPDATE bookings SET driver = ?, status = ? WHERE id = ?', (driver_name, "accepted", booking[0]))
            conn.commit()
            st.success(f"Booking {booking[0]} accepted successfully!")

elif menu == "Admin":
    st.write('<div class="big-title">Admin Dashboard</div>', unsafe_allow_html=True)

    # Detailed Analytics Section
    st.write('<div class="big-title">Analytics Overview</div>', unsafe_allow_html=True)
    cursor.execute('SELECT COUNT(*) FROM bookings')
    total_bookings = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM bookings WHERE status = "delivered"')
    delivered_bookings = cursor.fetchone()[0]

    cursor.execute('SELECT AVG(rating) FROM reviews')
    avg_rating = cursor.fetchone()[0]

    st.write(f"Total Bookings: {total_bookings}")
    st.write(f"Delivered Bookings: {delivered_bookings}")
    st.write(f"Average Rating: {avg_rating:.2f}" if avg_rating else "No ratings available.")

    # New: User analytics
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    st.write(f"Total Users: {total_users}")

    cursor.execute('SELECT vehicle_type, COUNT(*) FROM bookings GROUP BY vehicle_type')
    vehicle_stats = cursor.fetchall()
    
    st.write("**Bookings by Vehicle Type:**")
    for vehicle, count in vehicle_stats:
        st.write(f"{vehicle.capitalize()}: {count} bookings")

    # Manage Users
    st.write('<div class="big-title">Manage Users</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    for user in users:
        st.write(f'User ID: {user[0]}, Username: {user[1]}, Email: {user[2]}')
        if st.button(f"Edit User {user[1]}", key=f"edit-user-{user[0]}"):
            new_username = st.text_input(f"New Username for {user[1]}", value=user[1])
            new_email = st.text_input(f"New Email for {user[1]}", value=user[2])
            if st.button(f"Save Changes for {user[1]}", key=f"save-user-{user[0]}"):
                cursor.execute('UPDATE users SET username = ?, email = ? WHERE id = ?', (new_username, new_email, user[0]))
                conn.commit()
                st.success(f"User {user[1]} updated successfully!")
        if st.button(f"Delete User {user[1]}", key=f"delete-user-{user[0]}"):
            cursor.execute('DELETE FROM users WHERE id = ?', (user[0],))
            conn.commit()
            st.success(f"User {user[1]} deleted successfully!")

    # Driver Management
    st.write('<div class="big-title">Manage Drivers</div>', unsafe_allow_html=True)
    driver_name = st.text_input("Driver Name")
    driver_vehicle = st.text_input("Vehicle Type")
    if st.button("Add Driver"):
        cursor.execute('INSERT INTO drivers (name, vehicle, available) VALUES (?, ?, ?)', (driver_name, driver_vehicle, 1))
        conn.commit()
        st.success("Driver added successfully!")

    cursor.execute('SELECT * FROM drivers')
    drivers = cursor.fetchall()
    for driver in drivers:
        st.write(f"Driver ID: {driver[0]}, Name: {driver[1]}, Vehicle: {driver[2]}, Available: {'Yes' if driver[3] else 'No'}")
        if st.button(f"Deactivate Driver {driver[1]}", key=f"deactivate-driver-{driver[0]}"):
            cursor.execute('UPDATE drivers SET available = 0 WHERE id = ?', (driver[0],))
            conn.commit()
            st.success(f"Driver {driver[1]} deactivated!")
        if st.button(f"Activate Driver {driver[1]}", key=f"activate-driver-{driver[0]}"):
            cursor.execute('UPDATE drivers SET available = 1 WHERE id = ?', (driver[0],))
            conn.commit()
            st.success(f"Driver {driver[1]} activated!")

    # Manage Bookings
    st.write('<div class="big-title">Manage Bookings</div>', unsafe_allow_html=True)
    cursor.execute('SELECT * FROM bookings')
    bookings = cursor.fetchall()
    for booking in bookings:
        st.write(f"Booking ID: {booking[0]}, User: {booking[1]}, Driver: {booking[2]}, Pickup: {booking[3]}, Dropoff: {booking[4]}, Status: {booking[7]}")
        if st.button(f"Update Booking {booking[0]}", key=f"update-booking-{booking[0]}"):
            new_status = st.selectbox(f"Update Status for Booking {booking[0]}", ["booked", "accepted", "in_progress", "delivered"], index=["booked", "accepted", "in_progress", "delivered"].index(booking[7]))
            cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', (new_status, booking[0]))
            conn.commit()
            st.success(f"Booking {booking[0]} updated!")
        if st.button(f"Delete Booking {booking[0]}", key=f"delete-booking-{booking[0]}"):
            cursor.execute('DELETE FROM bookings WHERE id = ?', (booking[0],))
            conn.commit()
            st.success(f"Booking {booking[0]} deleted successfully!")

    # Review Management
    st.write('<div class="big-title">Review Management</div>', unsafe_allow_html=True)
    review_filter = st.selectbox("Filter Reviews By", ["All", "Rating", "Booking ID"])

    if review_filter == "Rating":
        rating_filter = st.slider("Select Rating", 1, 5)
        cursor.execute('SELECT * FROM reviews WHERE rating = ?', (rating_filter,))
        filtered_reviews = cursor.fetchall()
    elif review_filter == "Booking ID":
        booking_id_filter = st.number_input("Enter Booking ID", min_value=1)
        cursor.execute('SELECT * FROM reviews WHERE booking_id = ?', (booking_id_filter,))
        filtered_reviews = cursor.fetchall()
    else:
        cursor.execute('SELECT * FROM reviews')
        filtered_reviews = cursor.fetchall()

    for review in filtered_reviews:
        st.write(f'Booking ID: {review[1]}, Rating: {review[2]}, Feedback: {review[3]}')
        if st.button(f"Delete Review {review[1]}", key=f"delete-review-{review[0]}"):
            cursor.execute('DELETE FROM reviews WHERE id = ?', (review[0],))
            conn.commit()
            st.success(f"Review for Booking {review[1]} deleted!")

    # New: Export Data
    st.write('<div class="big-title">Export Data</div>', unsafe_allow_html=True)
    if st.button("Export Bookings Data as CSV"):
        cursor.execute('SELECT * FROM bookings')
        bookings_data = cursor.fetchall()
        bookings_df = pd.DataFrame(bookings_data, columns=['ID', 'User', 'Driver', 'Pickup', 'Dropoff', 'Vehicle', 'Cost', 'Status'])
        bookings_df.to_csv('bookings_data.csv', index=False)
        st.success("Bookings data exported successfully!")
    
    if st.button("Export User Data as CSV"):
        cursor.execute('SELECT * FROM users')
        users_data = cursor.fetchall()
        users_df = pd.DataFrame(users_data, columns=['ID', 'Username', 'Email'])
        users_df.to_csv('users_data.csv', index=False)
        st.success("User data exported successfully!")

    if st.button("Export Driver Data as CSV"):
        cursor.execute('SELECT * FROM drivers')
        drivers_data = cursor.fetchall()
        drivers_df = pd.DataFrame(drivers_data, columns=['ID', 'Name', 'Vehicle', 'Available'])
        drivers_df.to_csv('drivers_data.csv', index=False)
        st.success("Driver data exported successfully!")


# Closing the database connection
conn.close()
