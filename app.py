from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from io import BytesIO
import base64
import mysql.connector
import re

def generate_qr_base64(data):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# --- Database ---
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Blackjk",
        database="swiftcafe"
    )

# --- Validation helpers ---
def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def is_valid_name(name):
    return all(x.isalpha() or x.isspace() for x in name)

def is_valid_username(username):
    return re.match(r'^[A-Za-z0-9_]{3,}$', username)

def is_valid_phone(phone):
    return re.match(r'^[0-9]{10}$', phone)


# --- Routes ---
@app.route('/')
def landing_page():
    return render_template('landing.html')

@app.route('/home')
def home():
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login_page'))
    return render_template('home.html', user_name=session.get('name'))

@app.route('/about')
def about():
    return render_template('about.html')

#-----admin-----#
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login_page'))

    data = {
        'admin_name': session.get('name'),
        'total_users': 0,
        'total_bookings': 0,
        'total_food_orders': 0,
        'top_foods': [],
        'feedbacks': []
    }

    bookings = []
    food_orders = []

    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Total Registered Users
        cursor.execute("SELECT COUNT(*) AS total_users FROM users WHERE role='customer'")
        data['total_users'] = cursor.fetchone()['total_users']

        # Total Bookings
        cursor.execute("SELECT COUNT(*) AS total_bookings FROM bookings")
        data['total_bookings'] = cursor.fetchone()['total_bookings']

        # Total Booking Revenue
        cursor.execute("SELECT IFNULL(SUM(total_amount),0) AS booking_revenue FROM bookings")
        data['booking_revenue'] = cursor.fetchone()['booking_revenue']

        # Total Food Orders
        cursor.execute("SELECT COUNT(*) AS total_food_orders FROM food_orders")
        data['total_food_orders'] = cursor.fetchone()['total_food_orders']

        # Total Food Revenue
        cursor.execute("SELECT IFNULL(SUM(item_price*quantity),0) AS food_revenue FROM food_orders WHERE food_paid=1")
        data['food_revenue'] = cursor.fetchone()['food_revenue']

         # Total Revenue (Bookings + Food)
        data['total_revenue'] = data['booking_revenue'] + data['food_revenue']

        # Fetch all bookings
        cursor.execute("""
            SELECT id, name, email, phone, date, time, guests, table_no, category, subcategory, status, total_amount
            FROM bookings
            ORDER BY date DESC, time DESC
        """)
        bookings = cursor.fetchall()

        # Fetch all food orders with customer info
        cursor.execute("""
            SELECT f.id, f.booking_id, f.item_name, f.item_price, f.quantity, f.food_paid,
                   b.name AS customer_name, b.email AS customer_email
            FROM food_orders f
            JOIN bookings b ON f.booking_id = b.id
            ORDER BY f.created_at DESC
        """)
        food_orders = cursor.fetchall()
        

        # Top Ordered Foods
        cursor.execute("""
            SELECT item_name, SUM(quantity) AS total_quantity
            FROM food_orders
            GROUP BY item_name
            ORDER BY total_quantity DESC
            LIMIT 3
        """)
        data['top_foods'] = cursor.fetchall()

        # Latest Customer Feedbacks (limit 5)
        cursor.execute("""
            SELECT id, name, email, message, created_at
            FROM feedbacks
            ORDER BY created_at DESC
            LIMIT 5
        """)
        data['feedbacks'] = cursor.fetchall()

    except Exception as e:
        print("DB error:", e)

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    return render_template('admin.html',
                           data=data,
                           bookings=bookings,
                           food_orders=food_orders)



# --- Login & Register Pages ---
@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

# --- API: Register ---
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get('username', '').strip()
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    role = data.get('role', 'customer')
    password = data.get('password', '')

    if not (username and full_name and email and phone and password):
        return jsonify({"success": False, "message": "All fields are required"}), 400
    if not is_valid_username(username):
        return jsonify({"success": False, "message": "Invalid username"}), 400
    if not is_valid_name(full_name):
        return jsonify({"success": False, "message": "Invalid name"}), 400
    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Invalid email"}), 400
    if not is_valid_phone(phone):
        return jsonify({"success": False, "message": "Invalid phone"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password too short"}), 400

    hashed_password = generate_password_hash(password)

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, name, email, role, password, phone, created_at) VALUES (%s,%s,%s,%s,%s,%s,NOW())",
            (username, full_name, email, role, hashed_password, phone)
        )
        conn.commit()
    except mysql.connector.IntegrityError:
        return jsonify({"success": False, "message": "Username or Email already exists"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    return jsonify({"success": True, "message": "User registered successfully!"})

# --- API: Login ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['name'] = user['name']
        session['email'] = user['email']
        session["phone"] = user["phone"]   # ✅ Added phone to session
        session['role'] = user['role']
        return jsonify({"success": True, "role": user['role']})
    else:
        return jsonify({"success": False, "message": "Invalid email or password"}), 401

# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing_page'))

# Contact Us Route
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    success = None
    error = None
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip()
        subject = request.form.get('subject').strip()
        message = request.form.get('message').strip()

        if not (name and email and subject and message):
            error = "All fields are required!"
        else:
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO contact_messages (name, email, subject, message) VALUES (%s, %s, %s, %s)",
                    (name, email, subject, message)
                )
                conn.commit()
                cursor.close()
                conn.close()
                success = "Your message has been sent successfully!"
            except Exception as e:
                error = f"Error: {str(e)}"

    return render_template('contact.html', success=success, error=error)

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            return render_template('feedback.html', error="All fields are required.")

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedbacks (name, email, message) VALUES (%s, %s, %s)",
                (name, email, message)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return render_template('feedback.html', success="Thank you for your feedback!")
        except Exception as e:
            print("DB Error:", e)
            return render_template('feedback.html', error="Something went wrong. Try again.")
    
    return render_template('feedback.html')

# ------------------- PROFILE PAGE -------------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # ✅ Getting user data directly from session
    user = {
        "name": session.get("name"),
        "email": session.get("email"),
        "phone": session.get("phone"),
        "role": session.get("role"),
        "username": session.get("username"),
    }
    return render_template("profile.html", user=user)

# Swiftcafe: Booking route with slots + table availability
ALL_SLOTS = [
    "10:00 AM - 12:00 PM",
    "12:00 PM - 2:00 PM",
    "2:00 PM - 4:00 PM",
    "4:00 PM - 6:00 PM",
    "6:00 PM - 8:00 PM",
    "8:00 PM - 10:00 PM"
]

ALL_TABLES = [1, 2, 3, 4, 5]  # Example: 5 tables

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Default available slots & tables
    available_slots = ALL_SLOTS[:]
    available_tables = ALL_TABLES[:]

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        date = request.form['date']
        time = request.form['time']
        guests = request.form['guests']
        category = request.form['category']
        subcategory = request.form['subcategory']
        table_no = int(request.form['table_no'])

        # ✅ Double-check slot + table availability
        cursor.execute("""
            SELECT id FROM bookings 
            WHERE date=%s AND time=%s AND table_no=%s
        """, (date, time, table_no))
        conflict = cursor.fetchone()

        if conflict:
            cursor.close()
            conn.close()
            return "Sorry, this table is already booked for the selected time. Please choose another slot."

        # Insert booking
        cursor.execute("""
            INSERT INTO bookings 
            (name, email, phone, date, time, guests, table_no, category, subcategory, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, email, phone, date, time, guests, table_no, category, subcategory, 'pending'))

        booking_id = cursor.lastrowid
        conn.commit()

        cursor.close()
        conn.close()

        session['booking_id'] = booking_id
        session['customer_name'] = name
        return redirect(url_for('booking_payment'))

    # --- GET request ---
    date = request.args.get("date")
    time = request.args.get("time")

    if date:
        # Exclude slots already booked (all tables taken)
        cursor.execute("""
            SELECT time, COUNT(table_no) as booked_tables
            FROM bookings
            WHERE date=%s
            GROUP BY time
        """, (date,))
        booked_data = cursor.fetchall()

        # If all tables are booked for a slot → remove it
        for row in booked_data:
            if row['booked_tables'] >= len(ALL_TABLES):
                if row['time'] in available_slots:
                    available_slots.remove(row['time'])

    if date and time:
        # Exclude tables booked for selected slot
        cursor.execute("""
            SELECT table_no FROM bookings WHERE date=%s AND time=%s
        """, (date, time))
        booked_tables = [row['table_no'] for row in cursor.fetchall()]
        available_tables = [t for t in ALL_TABLES if t not in booked_tables]

    cursor.close()
    conn.close()

    return render_template('booking.html', slots=available_slots, tables=available_tables)

# ---------------- UPI Payment ----------------
UPI_ID = "sakshiparab639@oksbi"  # Replace with your UPI ID


# ---------------- Booking Payment ----------------
@app.route('/booking_payment', methods=['GET','POST'])
def booking_payment():
    if 'booking_id' not in session:
        return redirect(url_for('booking'))

    booking_id = session['booking_id']
    customer_name = session.get('customer_name')
    table_price = 500  # Fixed table price

    upi_uri = f"upi://pay?pa={UPI_ID}&pn=Swift Cafe&am={table_price}&cu=INR"
    qr_link = generate_qr_base64(upi_uri)

    if request.method == 'POST':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE bookings SET status='paid' WHERE id=%s", (booking_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('menu'))

    return render_template('food_payment.html',  # Using universal template
                           payment_type='booking',
                           total_price=table_price,
                           customer_name=customer_name,
                           qr_link=qr_link,
                           upi_uri=upi_uri)


# ---------------- Menu ----------------
@app.route('/menu', methods=['GET', 'POST'])
def menu():
    if 'booking_id' not in session:
        return redirect(url_for('booking'))

    booking_id = session['booking_id']
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        action = request.form.get('action')
        order_id = request.form.get('order_id')
        item_name = request.form.get('item_name')
        item_price = request.form.get('item_price')

        try:
            # ---------- ADD ITEM ----------
            if action == 'add' and item_name and item_price:
                item_price = float(item_price)

                # Check if item already exists
                cursor.execute(
                    "SELECT * FROM food_orders WHERE booking_id=%s AND item_name=%s",
                    (booking_id, item_name)
                )
                existing = cursor.fetchone()

                if existing:
                    # Update quantity
                    new_qty = existing['quantity'] + 1
                    cursor.execute(
                        "UPDATE food_orders SET quantity=%s WHERE id=%s",
                        (new_qty, existing['id'])
                    )
                else:
                    # Insert new row
                    cursor.execute("""
                        INSERT INTO food_orders 
                        (booking_id, item_name, item_price, food_paid, quantity)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (booking_id, item_name, item_price, 0, 1))

            # ---------- INCREASE QUANTITY ----------
            elif action == 'increase' and order_id:
                cursor.execute("SELECT * FROM food_orders WHERE id=%s", (order_id,))
                order = cursor.fetchone()
                if order:
                    new_qty = order['quantity'] + 1
                    cursor.execute(
                        "UPDATE food_orders SET quantity=%s WHERE id=%s",
                        (new_qty, order_id)
                    )

            # ---------- DECREASE QUANTITY ----------
            elif action == 'decrease' and order_id:
                cursor.execute("SELECT * FROM food_orders WHERE id=%s", (order_id,))
                order = cursor.fetchone()
                if order:
                    if order['quantity'] > 1:
                        new_qty = order['quantity'] - 1
                        cursor.execute(
                            "UPDATE food_orders SET quantity=%s WHERE id=%s",
                            (new_qty, order_id)
                        )
                    else:
                        cursor.execute("DELETE FROM food_orders WHERE id=%s", (order_id,))

            # ---------- DELETE ITEM ----------
            elif action == 'delete' and order_id:
                cursor.execute("DELETE FROM food_orders WHERE id=%s", (order_id,))

            conn.commit()

        except Exception as e:
            conn.rollback()
            print("Error storing food order:", e)

        return redirect(url_for('menu'))

    # ---------- FETCH CURRENT ORDERS ----------
    cursor.execute(
        "SELECT id, item_name, item_price, quantity FROM food_orders WHERE booking_id=%s",
        (booking_id,)
    )
    orders = cursor.fetchall()

    # Calculate total dynamically
    total = sum(order['quantity'] * float(order['item_price']) for order in orders)

    cursor.close()
    conn.close()

    # ---------- STATIC MENU ITEMS ----------
    menu_items = {
        "Pizza": [
            {"name": "Margherita", "price": 200, "image": "margherita.jpg"},
            {"name": "Pepperoni", "price": 250, "image": "pepperoni.jpg"},
            {"name": "Paneer Tikka", "price": 250, "image": "paneer_tikka.jpg"},
            {"name": "BBQ Chicken", "price": 300, "image": "bbq_chicken.jpg"},
            {"name": "Peri Peri", "price": 280, "image": "peri_peri.jpg"},
            {"name": "Cheese Burst", "price": 320, "image": "cheese_burst.jpg"},
            {"name": "Mexican Green Wave", "price": 290, "image": "mexican_green_wave.jpg"},
            {"name": "Farmhouse", "price": 260, "image": "farmhouse.jpg"},
            {"name": "Veggie Delight", "price": 240, "image": "veggie_delight.jpg"},
            {"name": "Tandoori Paneer", "price": 270, "image": "tandoori_paneer.jpg"}
        ],
        "Drinks": [
            {"name": "Coke", "price": 50, "image": "coke.jpg"},
            {"name": "Lemonade", "price": 60, "image": "lemonade.jpg"},
            {"name": "Smoothies", "price": 85, "image": "smoothie.jpg"},
            {"name": "Milkshake", "price": 100, "image": "milkshake.jpg"},
            {"name": "Mojito", "price": 80, "image": "mojito.jpg"},
            {"name": "Expresso", "price": 90, "image": "espresso.jpg"},
            {"name": "Cold Coffee", "price": 110, "image": "cold_coffee.jpg"},
            {"name": "Iced Tea", "price": 70, "image": "iced_tea.jpg"},
            {"name": "Hot Chocolate", "price": 95, "image": "hot_chocolate.jpg"},
            {"name": "Green Tea", "price": 60, "image": "green_tea.jpg"},
            {"name": "Blue Lagoon", "price": 130, "image": "blue_lagoon.jpg"}
        ],
        "Entradas": [
            {"name": "Nachos", "price": 120, "image": "nachos.jpg"},
            {"name": "Spring Rolls", "price": 150, "image": "spring_rolls.jpg"},
            {"name": "Cheese Balls", "price": 130, "image": "cheese_balls.jpg"},
            {"name": "Garlic Bread", "price": 100, "image": "garlic_bread.jpg"},
            {"name": "French Fries", "price": 90, "image": "french_fries.jpg"},
            {"name": "Tomato Salad", "price": 80, "image": "tomato_salad.jpg"},
            {"name": "Tandoori Momos", "price": 140, "image": "tandoori_momos.jpg"},
            {"name": "Stuffed Mushroom", "price": 160, "image": "stuffed_mushrooms.jpg"},
            {"name": "Loaded Nachos", "price": 180, "image": "loaded_nachos.jpg"},
            {"name": "Bruschetta", "price": 120, "image": "bruschetta.jpg"}
        ]
    }
    return render_template("menu.html", orders=orders, menu_items=menu_items, total=total)


# ---------------- Food Payment ----------------
@app.route('/food_payment', methods=['GET','POST'])
def food_payment():
    booking_id = session.get('booking_id')
    if not booking_id:
        return redirect(url_for('booking'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM food_orders WHERE booking_id=%s", (booking_id,))
    food_orders = cursor.fetchall()
    total_price = sum(o['item_price']*o['quantity'] for o in food_orders)
    cursor.close()
    conn.close()

    upi_uri = f"upi://pay?pa={UPI_ID}&pn=Swift Cafe&am={total_price}&cu=INR"
    qr_link = generate_qr_base64(upi_uri)

    if request.method == 'POST' and total_price > 0:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE food_orders SET food_paid=1 WHERE booking_id=%s", (booking_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('order_success'))

    return render_template('food_payment.html',
                           payment_type='food',
                           total_price=total_price,
                           customer_name=session.get('customer_name'),
                           qr_link=qr_link,
                           upi_uri=upi_uri,
                           food_orders=food_orders)

# ---------------- Order_sucess ----------------
@app.route('/order_success')
def order_success():
    return render_template('order_success.html')


# ---------------- Customer: My Bookings ----------------
@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login_page'))

    user_email = session.get('email')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, date, time, table_no, guests, category, subcategory, status, total_amount
        FROM bookings
        WHERE email=%s AND status='paid'
        ORDER BY date DESC, time DESC
    """, (user_email,))
    bookings = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('my_bookings.html', bookings=bookings)


# ---------------- Customer: My Orders ----------------
@app.route('/my_orders')
def my_orders():
    # Check if user is logged in
    if 'email' not in session:
        return redirect(url_for('login'))

    user_email = session['email']

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Fetch orders for the logged-in user
    query = """
        SELECT 
            f.id AS order_id,
            f.item_name,
            f.item_price,
            f.quantity,
            (f.item_price * f.quantity) AS total_amount,
            f.food_paid,
            f.created_at,
            b.id AS booking_id,
            b.date,
            b.time,
            b.table_no,
            b.status,
            b.total_amount AS booking_total
        FROM bookings b
        JOIN food_orders f ON f.booking_id = b.id
        WHERE b.email = %s
        ORDER BY f.created_at DESC
    """

    cursor.execute(query, (user_email,))
    orders = cursor.fetchall()

    return render_template('my_orders.html', orders=orders)

# --- Run ---#
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)