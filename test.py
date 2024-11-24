from flask import Flask, render_template, redirect, url_for, request, session, flash, make_response, jsonify
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
from io import StringIO
from datetime import datetime, timedelta
import mysql.connector
import datetime, csv, os, json, time, qrcode


# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "medcabinet",
    "password": "YKDCivJRUrptNK72eRyx", 
    "database": "medcabinet",
    "autocommit": True
}

# Define the directory for saving QR code images
QR_CODE_DIR = 'static/user_qrcodes/'

# Ensure the directory exists

app = Flask(__name__)
app.secret_key = '8d63cfa786bdee8fb79dbad79110d5c1'
socketio = SocketIO(app)

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# Dummy user data for demonstration
users = {"username123": "password123"}
inventory_sort_by = 'name'
doorlogs_sort_by = 'username'

#Session Timeout functinality
@app.before_request
def session_management():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(minutes=10)  # Set the session timeout (e.g., 1 minute)
    session.modified = True

    if 'user' in session:
        session['last_activity'] = datetime.datetime.now()


# Fetch inventory data
def fetch_inventory_data(category = None):
    global inventory_sort_by
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(dictionary=True) as cursor:
            # Force a refresh of the data
            cursor.execute("FLUSH TABLES medicine_inventory")
            
            if category:
                inventory_sort_by = category
                query = f"""
                    SELECT name, type, dosage, quantity, unit, date_stored, expiration_date 
                    FROM medicine_inventory 
                    WHERE quantity != 0 
                    ORDER BY {category} ASC
                """
            else:
                query = f"""
                    SELECT name, type, dosage, quantity, unit, date_stored, expiration_date 
                    FROM medicine_inventory 
                    WHERE quantity != 0 
                    ORDER BY name ASC
                """
            cursor.execute(query)
            inventory_items = cursor.fetchall()
            
            # Convert datetime objects to strings
            for item in inventory_items:
                item['date_stored'] = item['date_stored'].isoformat()
                item['expiration_date'] = item['expiration_date'].isoformat()
            
            return inventory_items
    except Exception as e:
        print(f"Error fetching inventory data: {e}")
        return []
    finally:
        if conn:
            conn.close()


# Serialize the data into json compatible format
def serialize_fetch_data(data, data_type):
    """ Helper function to serialize date and time fields """
    serialized_data = []

    if data_type == 'doorlogs':
        for log in data:
            if 'date' in log and isinstance(log['date'], datetime.date):
                log['date'] = log['date'].isoformat()
                # print(f"Serialized date: {log['date']}")

            if 'time' in log and isinstance(log['time'], timedelta):
                total_seconds = int(log['time'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                log['time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
                # print(f"Serialized time: {log['time']}")

            serialized_data.append(log)

    elif data_type == 'notifications':
        for notif in data:
            if 'expiration_date' in notif and isinstance(notif['expiration_date'], datetime.date):
                notif['expiration_date'] = notif['expiration_date'].isoformat()
                # print(f"Serialized expiration_date: {notif['expiration_date']}")

            if 'notification_date' in notif and isinstance(notif['notification_date'], datetime.date):
                notif['notification_date'] = notif['notification_date'].isoformat()
                # print(f"Serialized notification_date: {notif['notification_date']}")

            if 'notification_time' in notif and isinstance(notif['notification_time'], timedelta):
                total_seconds = int(notif['notification_time'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                notif['notification_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
                # print(f"Serialized notification_time: {notif['notification_time']}")

            serialized_data.append(notif)

    return serialized_data


# Fetch doorlogs data
def fetch_doorlogs_data(sort_by = None):
    global doorlogs_sort_by
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("FLUSH TABLES door_logs")

            if sort_by:
                doorlogs_sort_by = sort_by
                query = f"""
                    SELECT username, accountType, position, date, time, action_taken  
                    FROM door_logs 
                    ORDER BY {doorlogs_sort_by} ASC
                """
            else:
                query = f"""
                    SELECT username, accountType, position, date, time, action_taken  
                    FROM door_logs 
                    ORDER BY {doorlogs_sort_by} ASC
                """

            cursor.execute(query)
            doorlogs_data = cursor.fetchall()
            # Serialize date and time for JSON compatibility
            serialized_data = serialize_fetch_data(doorlogs_data, 'doorlogs')
            
            # print(serialized_data)
            return serialized_data
        
    except Exception as e:
        print(f"Error fetching doorlogs data: {e}")
        return []
    finally:
        if conn:
            conn.close()


# Fetch notifications data
def fetch_notifications_data():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(dictionary=True) as cursor:
            # Ensure the notification_logs table is updated
            cursor.execute("FLUSH TABLES notification_logs")

            # Fetch notifications ordered by days until expiration (ascending)
            query = "SELECT id, medicine_name, expiration_date, notification_date, days_until_expiration  FROM notification_logs ORDER BY days_until_expiration ASC"
            cursor.execute(query)
            notifications_data = cursor.fetchall()

            # Serialize the fetched data
            serialized_data = serialize_fetch_data(notifications_data, 'notifications')
            return serialized_data

    except Exception as e:
        print(f"Error fetching notifications data: {e}")
        return []
    finally:
        if conn:
            conn.close()



def fetch_accounts_data():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("FLUSH TABLES users")

            query = f"""
                    SELECT id, username, position, accountType FROM users 
                    """
            cursor.execute(query)
            accounts_data = cursor.fetchall()
            # serialized_data = serialize_fetch_data(notifications_data, 'notifications')
            return accounts_data
    except Exception as e:
        print(f"Error fetching notifications data: {e}")
        return []
    finally:
        if conn:
            conn.close()


# Broadcast inventory data
def broadcast_inventory_update():
    try:
        inventory_data = fetch_inventory_data(inventory_sort_by)
        socketio.emit('request_inventory_update', {'data': inventory_data})
    except Exception as e:
        print(f"Error in broadcast: {e}")

# Broadcast doorlogs data
def broadcast_doorlogs_update():
    try:
        doorlogs_data = fetch_doorlogs_data(doorlogs_sort_by)
        socketio.emit('request_doorlogs_update', {'data': doorlogs_data})
    except Exception as e:
        print(f"Error broadcasting doorlogs update: {e}")

# Broadcast notifications data
def broadcast_notifications_update():
    try:
        notifications_data = fetch_notifications_data()
        socketio.emit('request_notifications_update', {'data': notifications_data})
    except Exception as e:
        print(f"Error broadcasting notifications update: {e}")


# Set up scheduler with error handling
# scheduler = BackgroundScheduler()

# scheduler.add_job(
#     func=broadcast_inventory_update, 
#     trigger="interval", 
#     seconds= 10, #Request Interval
#     max_instances=1,
#     coalesce=True    
# )

# scheduler.add_job(
#     func=broadcast_doorlogs_update,
#     trigger="interval",
#     seconds=10, #Request Interval
#     max_instances=1,
#     coalesce=True
# )

# scheduler.add_job(
#     func=broadcast_notifications_update,
#     trigger="interval",
#     seconds=10,  #Request Interval
#     max_instances=1,
#     coalesce=True
# )

# scheduler.start()


# Webpage endpoints
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember_me = 'remember_me' in request.form

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Fetch the user from the database
            query = "SELECT * FROM users WHERE username = %s"
            cursor.execute(query, (username,))
            user = cursor.fetchone()

            # Check if user exists and password matches
            if user and user['password'] == password: 
                session['user'] = username  
                session['position'] = user['position']
                session['account_type'] = user['accountType']
                session['user_id'] = user['id']
                session['notification'] = fetch_notifications_data()

                resp = make_response(redirect(url_for('home')))
                if remember_me:
                    resp.set_cookie('username', username, max_age=30*24*60*60)
                    resp.set_cookie('password', password, max_age=30*24*60*60)
                else:
                    resp.delete_cookie('username')
                    resp.delete_cookie('password')
                    
                return resp
            else:
                flash('Invalid username or password', 'danger')
        except Exception as e:
            print(f"Database error: {e}")  # Log any errors
        finally:
            cursor.close()
    return render_template('login.html')


#Routing for the Home page
@app.route('/home')
def home():
    if 'user' in session:
        currentUser = {
            'username' : session.get('user'),
            'account_type' : session.get('account_type')
        }
        
        last_activity = session.get('last_activity')
        now = datetime.datetime.now()
        if last_activity and (now - last_activity).total_seconds() > 3600:
            flash('You have been automatically logged out due to inactivity', 'warning')
            return redirect(url_for('logout'))
        
        inventory_items = fetch_inventory_data(inventory_sort_by)
        
        return render_template('home.html', inventory_items=inventory_items, user=currentUser)
    else:
        return redirect(url_for('login'))


#Adding the functionality of Logout and Automatic Logout during Idle
@app.route('/logout')
def logout():
    session.pop('user', None)  # Clear the user session
    idle = request.args.get('idle')
    resp = make_response(redirect(url_for('login', idle=idle)))
    # Clear cookies on logout
    resp.delete_cookie('username')
    resp.delete_cookie('password')
    resp.delete_cookie('remember_me')
    return resp

@app.route('/inventory')
def inventory():
    export_format = request.args.get('format')
    filename = request.args.get('filename', 'inventory_data.csv')  # Default filename

    inventory_items = fetch_inventory_data(inventory_sort_by)

    # Export CSV functionality
    if export_format == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Brand Name', 'Generic Name', 'Dosage', 'Quantity', 'Unit', 'Date Stored', 'Expiration Date'])

        for item in inventory_items:
            writer.writerow([item['name'], item['type'], item['dosage'], item['quantity'], item['unit'], item['date_stored'], item['expiration_date']])

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'text/csv'
        return response

    # Render the full page otherwise
    return render_template('inventory.html', inventory_items=inventory_items)


@app.route('/doorlogs')
def doorlogs():
    if 'user' in session:
        currentUser = {
            'username' : session.get('user'),
            'account_type' : session.get('account_type')
        }
    else:
        return redirect(url_for('login'))
    
    export_format = request.args.get('format')
    filename = request.args.get('filename', 'doorlogs_data.csv')  # Default filename if none is provideda

    door_logs = fetch_doorlogs_data(doorlogs_sort_by)

    # Export CSV functionality
    if export_format == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Username', 'Account Type', 'Position', 'Date', 'Time', 'Action Taken'])

        # Write data rows
        for log in door_logs:
            writer.writerow([
                log.get('username', ''),
                log.get('accountType', ''),
                log.get('position', ''),
                log.get('date', ''),
                log.get('time', ''),
                log.get('action_taken', '')
            ])

        # Prepare the CSV response
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        
        return response

    # Main door logs template
    return render_template('doorlogs.html', door_logs=door_logs, user=currentUser)

@app.route('/notification')
def notification():
    if 'user' in session:
        currentUser = {
            'username' : session.get('user'),
            'account_type' : session.get('account_type')
        }

        notifications = fetch_notifications_data()
        return render_template('notification.html', user=currentUser, notifications=notifications)
    else:
        return redirect(url_for('login'))


# Endpoint to fetch notifications from the session
@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    notifications = session.get('notification', [])
    return jsonify(notifications)

# Endpoint to remove a notification from the session after it is shown
@app.route('/remove_notification', methods=['POST'])
def remove_notification():
    notification_id = request.json.get('id')
    notifications = session.get('notification', [])
    
    # Filter out the notification with the given id
    updated_notifications = [n for n in notifications if n['id'] != notification_id]
    session['notification'] = updated_notifications
    
    return jsonify({"status": "success"})

# Check account numbers
@app.route('/accounts/counts', methods=['GET'])
def get_account_counts():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Query to get count of Admin accounts
        cursor.execute("SELECT COUNT(*) FROM users WHERE accountType = 'Admin'")
        admin_count = cursor.fetchone()[0]

        # Query to get count of Staff accounts
        cursor.execute("SELECT COUNT(*) FROM users WHERE accountType = 'Staff'")
        staff_count = cursor.fetchone()[0]

        # Query to get count of Staff accounts
        cursor.execute("SELECT COUNT(*) FROM users WHERE position = 'Brgy Health Councilor'")
        councilor_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE position = 'Midwife'")
        midwife_count = cursor.fetchone()[0]

        return jsonify({'adminCount': admin_count, 'staffCount': staff_count, 'councilor' : councilor_count, 'midwife' : midwife_count})
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'adminCount': 0, 'staffCount': 0})
    finally:
        cursor.close()


@app.route('/accounts', methods=['GET', 'POST'])
def accounts():
    if 'user' in session:
        currentUser = {
            'username': session.get('user'),
            'account_type': session.get('account_type')
        }
    else:
        return redirect(url_for('login'))
    conn = get_db_connection()

    if request.method == 'POST':
        # Retrieve form data
        username = request.form.get('username')
        password = request.form.get('password')
        position = request.form.get('position')
        account_type = request.form.get('accountType')

        # Validate required fields
        if not all([username, password, position, account_type]):
            return jsonify({'success': False, 'error': 'All fields are required'})

        cursor = conn.cursor()
        try:
            # Check maximum counts
            cursor.execute("SELECT COUNT(*) FROM users WHERE accountType = 'Admin'")
            admin_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE accountType = 'Staff'")
            staff_count = cursor.fetchone()[0]

            if account_type == "Admin" and admin_count >= 2:
                return jsonify({'success': False, 'error': 'Maximum of 2 admin accounts allowed'})

            if account_type == "Staff" and staff_count >= 10:
                return jsonify({'success': False, 'error': 'Maximum of 10 staff accounts allowed'})

            # Generate QR code data and image
            qr_data = f"{password} - {position}"

            # Insert new user into the users table with QR code image path
            query = """
            INSERT INTO users (username, password, position, accountType, qrcode_data) 
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (username, password, position, account_type, qr_data))
            conn.commit()

            # Fetch the newly created user ID
            cursor.execute("SELECT LAST_INSERT_ID()")
            user_id = cursor.fetchone()[0]

            # Define QR code filename: userID_position_username.png
            qr_filename = f"{user_id}-{qr_data}.png"
            qr_path = os.path.join(QR_CODE_DIR, qr_filename)

            # Generate and save QR code image
            qr_img = qrcode.make(qr_data)
            qr_img.save(qr_path)

            return jsonify({'success': True, 'imagePath' : qr_path})
        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            cursor.close()
    
    else:
        users = fetch_accounts_data()
        return render_template('accounts.html', users=users, user=currentUser)


@app.route('/view_qr/<int:user_id>', methods=['POST', 'GET'])
def view_qr(user_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id = %s",
        (user_id,)
    )
    result = cursor.fetchone()
    conn.close()

    if result:
        qrpath = f'{QR_CODE_DIR}{result[0]}-{result[5]}.png'
        return jsonify({'success': True, 'imagePath': qrpath})
    else:
        return jsonify({'success': False, 'message': 'QR Code not found'}), 404


@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 401

    current_user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if the user is an admin and get the account type
        cursor.execute("SELECT accountType FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()

        if not user_data:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        account_type = user_data[0]

        # Restrict deletion of the last admin
        if account_type == 'Admin':
            cursor.execute("SELECT COUNT(*) FROM users WHERE accountType = 'Admin'")
            admin_count = cursor.fetchone()[0]
            if admin_count <= 1:
                return jsonify({'success': False, 'message': 'Cannot delete the last admin account'}), 400

        # Delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()

        # Check if the deleted user is the current user
        if user_id == int(current_user_id):
            session.pop('user', None) 
            idle = request.args.get('idle')
            resp = make_response(redirect(url_for('login', idle=idle)))
            # Clear cookies on logout
            resp.delete_cookie('username')
            resp.delete_cookie('password')
            resp.delete_cookie('remember_me')
            return jsonify({'success': True, 'message': 'User deleted and logged out', 'logout': True})

        return jsonify({'success': True, 'message': 'User deleted successfully'})

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete user'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get the JSON data from the request
        data = request.json
        username = data.get('username')
        position = data.get('position')
        accountType = data.get('accountType')
        newPassword = data.get('newPassword')
        # newQrCodeData = f'{newPassword} - {position}'

        # Validate that all fields are provided
        if not username or not position or not accountType:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        # Check if username is already taken by another user (excluding current user)
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE username = %s AND id != %s",
            (username, user_id)
        )
        username_exists = cursor.fetchone()[0]

        if username_exists > 0:
            return jsonify({'success': False, 'message': 'Username already exists'}), 409


        cursor.execute(
            "SELECT * FROM users WHERE id = %s",
            (user_id,)
        )

        user_data = cursor.fetchall()[0] 
        filename = f'{user_data[0]}-{user_data[5]}' 
        print(f'{user_data[0]}-{user_data[5]}')

        # Perform the update query
        if (newPassword):
            update_query = """
                UPDATE users
                SET username = %s, position = %s, accountType = %s, password = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (username, position, accountType, newPassword, user_id))
        else:
            update_query = """
                UPDATE users
                SET username = %s, position = %s, accountType = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (username, position, accountType, user_id))

        conn.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'User not found or no changes made'}), 404


        return jsonify({'success': True, 'message': 'User information updated successfully', 'imagePath' : filename})

    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({'success': False, 'message': 'Error updating user information'}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/search_data', methods=['GET', 'POST'])
def search_data():
    query_str = request.json.get('query', '').strip()
    table = request.json.get('table')

    if not query_str:
        return jsonify({"data": []}) 
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(dictionary=True) as cursor:
            if table == 'doorlogs':
                cursor.execute("FLUSH TABLES door_logs")

                query = f"""
                    SELECT username, accountType, position, date, time, action_taken 
                    FROM door_logs
                    WHERE username LIKE '%{query_str}%' OR accountType LIKE '%{query_str}%' OR position LIKE '%{query_str}%' OR action_taken LIKE '%{query_str}%'
                """
                cursor.execute(query)
                doorlogs_data = cursor.fetchall()
                # serialized_data = serialize_fetch_data(notifications_data, 'notifications')
                serialized_data = serialize_fetch_data(doorlogs_data, 'doorlogs')
                return jsonify({"data": serialized_data})
            
            elif table == 'inventory':
                cursor.execute("FLUSH TABLES medicine_inventory")

                query = f"""
                    SELECT name, type, dosage, quantity, unit, date_stored, expiration_date 
                    FROM medicine_inventory
                    WHERE name LIKE '%{query_str}%' OR type LIKE '%{query_str}%' OR unit LIKE '%{query_str}%'
                """
                cursor.execute(query)
                medicine_data = cursor.fetchall()
                # serialized_data = serialize_fetch_data(notifications_data, 'notifications')
                print(medicine_data)
                return jsonify({"data": medicine_data})

    except Exception as e:
        print(f"Error fetching search data: {e}")
        return []
    finally:
        if conn:
            conn.close()



# Client connections
@socketio.on('connect')
def handle_connect(auth=None):
    if 'user' in session:
        pass
        # Send initial inventory data when client connects
        inventory_data = fetch_inventory_data(inventory_sort_by)
        doorlogs_data = fetch_doorlogs_data(doorlogs_sort_by)
        notifications_data = fetch_notifications_data()

        # emit('inventory_update', {'data': inventory_data})
        # emit('doorlogs_update', {'data': doorlogs_data})
        # emit('notifications_update', {'data': notifications_data})


@socketio.on('request_inventory_update')
def inventory_update_request():
    inventory_data = fetch_inventory_data(inventory_sort_by)

    emit('inventory_update', {'data': inventory_data})
    

@socketio.on('request_doorlogs_update')
def doorlogs_update_request():
    doorlogs_data = fetch_doorlogs_data(doorlogs_sort_by)

    emit('doorlogs_update', {'data': doorlogs_data})

@socketio.on('request_notifications_update')
def notification_update_request():
    notifications_data = fetch_notifications_data()

    emit('notifications_update', {'data': notifications_data})


@socketio.on('request_sorted_inventory_update')
def handle_sorted_inventory_update_request(category):
    print(category['sort_by'])
    inventory_data = fetch_inventory_data(category['sort_by'])
    emit('sorted_data', {'data' : inventory_data})

@socketio.on('request_sorted_doorlogs_update')
def handle_sorted_doorlogs_update_request(category):
    print(category['sort_by'])
    doorlogs_data = fetch_doorlogs_data(category['sort_by'])
    emit('sorted_data', {'data' : doorlogs_data})
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
'''

-----------------------------------------------------------------API FOR SYSTEM_BASED (TKINTER)--------------------------------------------------------------


NOTE: THIS SECTION IS FOR CONNECTING THE SYSTEM-BASED APP ON THE MINI PC TO THE WEB APP SERVER FOR DATABASE INTEGRATION
'''
#API for depositing medicine
@app.route('/api/add_medicine', methods=['POST'])
def add_medicine():
    try:
        data = request.get_json()  # Parse the incoming JSON data
        print("Received data:", data)  # Debug: Print received data
        
        # Check if all required fields are present
        required_fields = ['name', 'type', 'dosage', 'quantity', 'unit', 'expiration_date', 'qr_code']
        for field in required_fields:
            if field not in data:
                return jsonify({"status": "error", "message": f"Missing field: {field}"}), 400
        
        # Insert data into the database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO medicine_inventory (name, type, dosage, quantity, unit, expiration_date, qr_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data['name'], data['type'], data['dosage'], data['quantity'], data['unit'], data['expiration_date'], data['qr_code']))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Medicine added successfully!"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
#API for manual login and fetching users for lockunlock
@app.route('/api/user_select', methods=['POST'])
def user_select():
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Request must be JSON"
        }), 400
    
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({
            "status": "error",
            "message": "Username and password are required"
        }), 400

    # Insert data into the database
    conn = get_db_connection2()
    cursor = conn.cursor()

    cursor.execute("SELECT username, accountType, position FROM users WHERE username = %s AND password = %s", (username, password))
    result = cursor.fetchone()

    cursor.close()  # Close cursor
    conn.close()    # Close connection

    if result:
        userName, accountType, position = result
        return jsonify({
            "status": "success",
            "username": userName,
            "accountType": accountType,
            "position": position
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Invalid username or password"
        }), 400

@app.route('/api/insert_door_log', methods=['POST'])
def insert_door_log():
    data = request.get_json()
    username = data['username']
    accountType = data['accountType']
    position = data['position']
    action_taken = data['action_taken']

    conn = get_db_connection()
    cursor = conn.cursor()

    insert_query = """
        INSERT INTO door_logs (username, accountType, position, date, time, action_taken)
        VALUES (%s, %s, %s, CURDATE(), CURTIME(), %s)
    """
    cursor.execute(insert_query, (
        username, 
        accountType, 
        position, 
        action_taken
    ))

    conn.commit()

    cursor.close()  # Close the cursor after executing the query
    conn.close()    # Close the connection after using it

    return jsonify({'status': 'success', 'message': 'Door log inserted'})

# Initialize MySQL connection pool
connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="my_pool",
    pool_size=5,
    host="localhost",
    user="medcabinet",
    password="YKDCivJRUrptNK72eRyx",
    database="medcabinet"
)

# Function to handle the serialization of date and timedelta objects
def serialize_row(row):
    serialized_row = []
    for field in row:
        if isinstance(field, (datetime.date, timedelta)):
            if isinstance(field, timedelta):
                # Convert timedelta to HH:MM:SS format
                field = str(field)
            else:
                # Convert datetime.date to string
                field = field.isoformat()
        serialized_row.append(field)
    return serialized_row


#API for extracting medicine inventory and door logs to csv file
@app.route('/api/get_table_data/<table_name>', methods=['GET'])
def get_table_data(table_name):
    """
    GET /api/get_table_data/<table_name>
    Retrieves data from the specified table with optional pagination.

    Parameters:
    - table_name (str): Allowed values are "medicine_inventory" and "door_logs".
    - offset (int): Starting position for rows (default: 0).

    Returns:
    - JSON object with columns and rows on success.
    - Error message on failure.
    """
    # Whitelist of allowed table names
    allowed_tables = {"medicine_inventory", "door_logs"}
    if table_name not in allowed_tables:
        return jsonify({"error": "Invalid table name"}), 400

    # Get pagination parameters
    offset = request.args.get('offset', 0, type=int)

    try:
        # Try to get a connection from the pool
        print(f"Attempting to get connection for {table_name}...")
        conn = connection_pool.get_connection()
        if not conn:
            return jsonify({"error": "Failed to establish a database connection."}), 500

        print(f"Connection established for {table_name}. Executing query...")

        cursor = conn.cursor()

        # Query to fetch all rows (no LIMIT or OFFSET)
        query = f"SELECT * FROM {table_name}"
        print(f"Executing query: {query} for table {table_name}")  # Debug: print the query

        cursor.execute(query)
        rows = cursor.fetchall()

        # Serialize the rows to make sure timedelta and datetime objects are converted to strings
        serialized_rows = [serialize_row(row) for row in rows]

        # Get column names dynamically
        column_names = [i[0] for i in cursor.description]

        # Handle empty results
        if not serialized_rows:
            return jsonify({"message": f"No data found in {table_name}"}), 404

        return jsonify({"columns": column_names, "rows": serialized_rows})

    except mysql.connector.Error as err:
        # Log specific MySQL error
        print(f"MySQL error: {err}")
        return jsonify({"error": "Failed to retrieve data from the database", "details": str(err)}), 500
    except Exception as e:
        # Log any other unexpected errors
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()
            print(f"Connection closed for {table_name}")


#API for fetching medicine inventory
@app.route('/api/medicine_inventory', methods=['GET'])
def get_medicine_inventory():
    # Fetch data from the database
    conn = mysql.connector.connect(
        host="localhost",
        user="medcabinet",
        password="YKDCivJRUrptNK72eRyx",
        database="medcabinet"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT name, type, dosage, quantity, unit, date_stored, expiration_date FROM medicine_inventory WHERE quantity <> 0")
    data = cursor.fetchall()

    # Convert data to a list of dictionaries
    inventory = []
    for row in data:
        inventory.append({
            "name": row[0],
            "type": row[1],
            "dosage": row[2],
            "quantity": row[3],
            "unit": row[4],
            "date_stored": row[5].strftime("%Y-%m-%d") if row[5] else None,
            "expiration_date": row[6].strftime("%Y-%m-%d") if row[6] else None,
        })
    cursor.close()
    conn.close()

    return jsonify(inventory)


@app.route('/api/door_logs', methods=['GET'])
def get_door_logs():
    try:
        order_by = request.args.get('order_by', 'username')
        sort = request.args.get('sort', 'ASC')

        # Validate inputs to prevent SQL injection
        valid_columns = ['username', 'accountType', 'position', 'date', 'time', 'action_taken']
        if order_by not in valid_columns:
            return jsonify({"error": "Invalid 'order_by' parameter"}), 400
        if sort not in ['ASC', 'DESC']:
            return jsonify({"error": "Invalid 'sort' parameter"}), 400

        # Connect to the database
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()

        # Query the database
        query = f"SELECT username, accountType, position, date, time, action_taken FROM door_logs ORDER BY {order_by} {sort}"
        cursor.execute(query)
        logs = cursor.fetchall()

        # Format the results
        results = []
        for log in logs:
            username, accountType, position, date, time, action_taken = log

            # Log the raw 'time' data
            app.logger.info(f"Raw time data for {username}: {time}")

            # Handle 'date' formatting
            date_formatted = date.strftime("%b %d, %Y") if date else "N/A"

            # Handle 'time' conversion (TIME type or None)
            time_in_seconds = None
            if time:
                try:
                    time_in_seconds = time.hour * 3600 + time.minute * 60 + time.second
                except AttributeError:
                    # Handle edge cases if 'time' isn't a TIME type
                    app.logger.warning(f"Unexpected time format: {time}")
                    time_in_seconds = None

            # Add the log to the results
            results.append({
                "username": username,
                "accountType": accountType,
                "position": position,
                "date": date_formatted,
                "time": time_in_seconds,
                "action_taken": action_taken
            })

        # Clean up resources
        cursor.close()
        conn.close()

        # Return the results as JSON
        return jsonify(results)

    except mysql.connector.Error as db_error:
        app.logger.error(f"Database error: {db_error}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500



#API for fetching users to use on account settings
@app.route('/api/accountsettings_users', methods=['GET'])
def accountsettings_users():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT username, position, accountType FROM users ORDER BY accountType ASC")
        users = cursor.fetchall()
        conn.close()

        # Format the data as a list of dictionaries
        user_list = [{"username": u[0], "position": u[1], "accountType": u[2]} for u in users]
        return jsonify(user_list)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    

# Database connection
def get_db_connection2():
    conn = mysql.connector.connect(
        host="localhost",
        user="medcabinet",
        password="YKDCivJRUrptNK72eRyx",
        database="medcabinet"
    )
    return conn

#API for counting admins
@app.route('/api/admin_count', methods=['GET'])
def admin_count():
    conn = get_db_connection2()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE accountType = 'Admin'")
    count = cursor.fetchone()[0]
    conn.close()
    return jsonify({'admin_count': count})

#API for deleting user account
@app.route('/api/delete_user_account', methods=['POST'])
def delete_user_account():
    data = request.json
    username = data.get('username')

    conn = get_db_connection2()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = %s", (username,))
    conn.commit()
    conn.close()
    return jsonify({'message': f"User '{username}' deleted successfully"})

#API for adding user account
@app.route('/api/add_user_account', methods=['POST'])
def add_user_account():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    position = data.get('position')
    account_type = data.get('accountType')
    qr_code_data = data.get('qr_code_data')

    if not all([username, password, position, account_type, qr_code_data]):
        return jsonify({"success": False, "message": "All fields are required."}), 400

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, position, accountType, qrcode_data)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, password, position, account_type, qr_code_data))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "message": "User added successfully!"}), 201

    except mysql.connector.Error as err:
        return jsonify({"success": False, "message": str(err)}), 500
        
#API for selecting user qr code for Login
@app.route('/api/validate_qrCODE', methods=['POST', 'GET'])
def validate_qrCODE():
    data = request.json
    
    if not data:
        return jsonify({"error": "Invalid JSON or no data received."}), 400
        
    qr_code = data.get('qr_code')

    if not qr_code:
        return jsonify({"error": "QR code is missing."}), 400

    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()

        # Query the database
        cursor.execute("SELECT username, password FROM users WHERE qrcode_data = %s", (qr_code,))
        result = cursor.fetchone()

        if result:
            username, password = result
            return jsonify({"username": username, "password": password})
        else:
            return jsonify({"error": "Invalid QR code or credentials."}), 404

    except mysql.connector.Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500
        
        
# Endpoint to verify QR code for Lock/Unlock
@app.route('/api/verify_qrcode', methods=['POST'])
def verify_qrcode():
    try:
        data = request.json
        qrcode_data = data.get('qrcode_data')

        if not qrcode_data:
            return jsonify({'status': 'error', 'message': 'QR code is required'}), 400

        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()

        # Query to verify QR code
        query = "SELECT username, accountType, position FROM users WHERE qrcode_data = %s"
        cursor.execute(query, (qrcode_data,))
        result = cursor.fetchone()

        if result:
            username, accountType, position = result
            return jsonify({'status': 'success', 'data': {'username': username, 'accountType': accountType, 'position': position}}), 200
        else:
            return jsonify({'status': 'error', 'message': 'QR code not found'}), 404

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        
@app.route('/api/log_door_action', methods=['POST'])
def log_door_action():
    try:
        data = request.json
        username = data.get('username')
        accountType = data.get('accountType')
        position = data.get('position')
        action_taken = data.get('action_taken')

        # Check for missing fields
        if not all([username, accountType, position, action_taken]):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

        # Connect to the database
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()

        # Insert log into the door_logs table
        query = """
            INSERT INTO door_logs (username, accountType, position, date, time, action_taken)
            VALUES (%s, %s, %s, CURDATE(), CURTIME(), %s)
        """
        cursor.execute(query, (username, accountType, position, action_taken))
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Log inserted successfully'}), 200

    except Exception as e:
        app.logger.error(f"Error in log_door_action: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        cursor.close()
        conn.close()
        
#API for select query in validate_user_info() in System
@app.route('/api/query', methods=['POST'])
def query_database():
    data = request.json
    query = data.get('query')
    params = data.get('params', [])
    
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()

#API for selecting query in account settings - edit
@app.route('/api/get_users/<username>', methods=['GET'])
def get_users(username):
    conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
    cursor = conn.cursor()
    cursor.execute("SELECT id, position, accountType, password, qrcode_data, username FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({
            "id": user[0],
            "position": user[1],
            "accountType": user[2],
            "password": user[3],
            "qrcode_data": user[4],
            "username": user[5]
        })
    return jsonify({"error": "User not found"}), 404
    
@app.route('/api/update_user/<username>', methods=['PUT'])
def update_user(username):
    data = request.json
    conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users
            SET username = %s, password = %s, position = %s, accountType = %s
            WHERE username = %s
        """, (data['username'], data['password'], data['position'], data['accountType'], username))
        conn.commit()
        conn.close()
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
        
        
@app.route('/api/soon_to_expire', methods=['GET'])
def soon_to_expire():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        today = datetime.now().date()
        soon_date = today + timedelta(days=31)

        cursor.execute(
            "SELECT name, type, dosage, expiration_date FROM medicine_inventory WHERE expiration_date <= %s AND expiration_date >= %s ORDER BY expiration_date ASC",
            (soon_date, today)
        )
        medicines = cursor.fetchall()
        conn.close()

        return jsonify(medicines)
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/log_notification', methods=['POST'])
def log_notification():
    try:
        data = request.json
        medicine_id = data['medicine_id']
        medicine_name = data['medicine_name']
        med_type = data['med_type']
        dosage = data['dosage']
        expiration_date = data['expiration_date']
        notification_date = datetime.now().date()
        notification_time = datetime.now().time()
        days_left = data['days_left']

        conn = mysql.connector.connect(
            host="localhost",
            user="medcabinet",
            password="YKDCivJRUrptNK72eRyx",
            database="medcabinet"
        )
        cursor = conn.cursor()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM notification_logs WHERE medicine_id = %s",
            (medicine_id,)
        )
        already_logged = cursor.fetchone()[0]

        if already_logged == 0:
            cursor.execute(
                "INSERT INTO notification_logs (medicine_id, medicine_name, expiration_date, notification_date, notification_time, days_until_expiration) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (medicine_id, medicine_name, expiration_date, notification_date, notification_time, days_left)
            )
            conn.commit()

        conn.close()
        return jsonify({"message": "Notification logged successfully"})
    except Error as e:
        return jsonify({"error": str(e)}), 500
        
@app.route('/api/withdraw_medicine', methods=['POST'])
def withdraw_medicine():
    data = request.json
    qr_code = data.get('qr_code')

    if not qr_code:
        return jsonify({'error': 'QR code is required'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Dictionary cursor for easier JSON conversion

        # Fetch medicine by QR code
        cursor.execute("SELECT name, quantity, type, unit FROM medicine_inventory WHERE qr_code = %s", (qr_code,))
        medicine = cursor.fetchone()

        if not medicine:
            return jsonify({'error': 'QR code not found'}), 404

        # Update quantity if requested
        decrement = data.get('decrement', 0)
        if decrement:
            if medicine['quantity'] > 0:
                new_quantity = medicine['quantity'] - decrement
                if new_quantity > 0:
                    cursor.execute("UPDATE medicine_inventory SET quantity = %s WHERE qr_code = %s", (new_quantity, qr_code))
                else:
                    cursor.execute("DELETE FROM medicine_inventory WHERE qr_code = %s", (qr_code,))
                conn.commit()
                return jsonify({'message': 'Medicine updated', 'quantity': max(0, new_quantity)}), 200
            return jsonify({'error': 'Out of stock'}), 400

        # Return medicine details
        return jsonify(medicine), 200

    except mysql.connector.Error as err:
        return jsonify({'error': f"Database error: {err}"}), 500

    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    socketio.run(app, debug=True)