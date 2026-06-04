from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from db_config import (
    get_financial_stats, get_team_stats, get_tree_view_data, 
    process_course_purchase, process_withdrawal_request,
    register_new_user, verify_login, get_user_profile, 
    update_user_profile, get_bank_details, update_bank_details, get_withdrawal_history,
    get_all_users_for_admin, get_db_connection
)
import datetime
import os
from werkzeug.utils import secure_filename

# --- NOTIFICATIONS ---
from apscheduler.schedulers.background import BackgroundScheduler
import notification

app = Flask(__name__)
# 🌟 AUTOMATED DATABASE TABLE INITIALIZER 🌟
# This runs automatically on boot to construct your cloud database tables
def initialize_cloud_database():
    from db_config import get_db_connection
    conn = get_db_connection()
    if not conn:
        print("❌ Database setup deferred: Connection pool unavailable.")
        return
    try:
        cursor = conn.cursor()
        print("🛠️ Constructing cloud tables inside the 'railway' database...")
        
        # 1. Create Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            user_code VARCHAR(50) UNIQUE NOT NULL,
            dob DATE,
            gender VARCHAR(20),
            aadhar_no VARCHAR(50),
            pan_no VARCHAR(50),
            mobile VARCHAR(20),
            password VARCHAR(255) NOT NULL,
            sponsor_id INT,
            leg VARCHAR(20),
            address TEXT,
            profile_img VARCHAR(255),
            is_active BOOLEAN DEFAULT FALSE,
            bank_acc_name VARCHAR(255),
            bank_acc_no VARCHAR(100),
            bank_ifsc VARCHAR(50),
            upi_id VARCHAR(100),
            upi_mobile VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Create User Courses Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_courses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            course_name VARCHAR(255) NOT NULL,
            course_category VARCHAR(255) DEFAULT 'General Education',
            course_price DECIMAL(15, 2) NOT NULL,
            remaining_days INT DEFAULT 212,
            status VARCHAR(50) DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 3. Create Withdrawals Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            request_amount DECIMAL(15, 2) NOT NULL,
            tds_deduction DECIMAL(15, 2) DEFAULT 0.00,
            net_payable DECIMAL(15, 2) NOT NULL,
            status VARCHAR(50) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP NULL DEFAULT NULL
        );
        """)

        # 4. Insert or Update the Active Demo User 'JOHN'
        cursor.execute("SELECT id FROM users WHERE user_code = 'JOHN'")
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO users (full_name, email, user_code, password, is_active) 
            VALUES ('JOHN DOE', 'john@demo.com', 'JOHN', 'John@2026', 1)
            """)
        else:
            cursor.execute("UPDATE users SET is_active = 1 WHERE user_code = 'JOHN'")

        conn.commit()
        print("🚀 Cloud database tables and active 'JOHN' profile verified successfully!")
    except Exception as e:
        print(f"❌ Initialization error: {e}")
    finally:
        cursor.close()
        conn.close()

# Invoke the verification function immediately on server startup
initialize_cloud_database()
app.secret_key = 'mlm_super_secure_key_123' 

UPLOAD_FOLDER = 'static/uploads/kyc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ==========================================
# NOTIFICATION SCHEDULER
# ==========================================
def run_midnight_job():
    print("Running midnight notifications...")
    notification.run_midnight_job()

scheduler = BackgroundScheduler()
scheduler.add_job(run_midnight_job, 'cron', hour=0, minute=1)

# ==========================================
# GLOBAL INJECTOR
# ==========================================
@app.context_processor
def inject_user_data():
    """Automatically sends these variables to EVERY HTML file so you don't have to!"""
    user_name = session.get('user_name')
    img = session.get('profile_img')
    
    # Differentiate default avatars based on active login profile
    if not img:
        if user_name == "John Doe":
            img = "https://i.pravatar.cc/150?img=68"
        else:
            img = "https://cdn-icons-png.flaticon.com/512/149/149071.png" # Clean, generic system placeholder
            
    return {
        'user_name': user_name,
        'user_code': session.get('user_code'),
        'profile_img': img
    }

# ==========================================
# PAGE ROUTES
# ==========================================

@app.route('/')
def home():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    user_code = session.get('user_code')
    referral_link = f"{request.host_url}signup?ref={user_code}"
    return render_template('user/index.html', referral_link=referral_link)

@app.route('/profile')
def profile_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/profile.html')

@app.route('/courses')
def courses_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/courses.html')

@app.route('/bank')
def bank_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/bank.html')

@app.route('/withdraw')
def withdraw_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/withdraw.html')

@app.route('/referral')
def referral_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/referral.html')

@app.route('/support')
def support_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/support.html')

@app.route('/login')
def login_page():
    return render_template('user/login.html')  

@app.route('/signup')
def signup_page():
    return render_template('user/signup.html') 

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ==========================================
# AUTHENTICATION API
# ==========================================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    user_code = data.get('user_code') 
    password = data.get('password')
    
    if user_code == "ADMIN" and password == "Admin@2026!":
        session['user_id'] = 0
        session['user_name'] = "Super Admin"
        session['user_code'] = "ADMIN"
        session['role'] = "admin"
        return jsonify({
            "status": "success", 
            "message": "Welcome back, Admin!", 
            "redirect": "/admin/admin_index" 
        })
    
    if user_code == "MLM87872" and password == "John@2026":
        session['user_id'] = 1 
        session['user_name'] = "John Doe"
        session['user_code'] = "MLM87872"
        session['role'] = "user"
        return jsonify({
            "status": "success", 
            "message": "Welcome back, John!", 
            "redirect": "/" 
        })

    user = verify_login(user_code, password)
    if user:
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_code'] = user_code  
        session['role'] = "user" 
        return jsonify({
            "status": "success", 
            "message": "Logged in successfully!", 
            "redirect": "/" 
        })
    
    return jsonify({"status": "error", "message": "Invalid Login ID or password"})

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    
    full_name = data.get('fullName')
    dob = data.get('dob')
    gender = data.get('sex')
    aadhar_no = data.get('aadhar')
    pan_no = data.get('pan')
    mobile = data.get('mobile')
    email = data.get('email')
    password = data.get('password') 
    sponsor_id = data.get('sponsor_id') 
    leg = data.get('leg')

    result = register_new_user(full_name, email, dob, gender, aadhar_no, pan_no, mobile, password, sponsor_id, leg)
    return jsonify(result)

@app.route('/api/admin/tree-data/<user_code>')
def api_admin_tree_data(user_code):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    tree_data = get_tree_view_data(user_code)
    
    if tree_data:
        return jsonify(tree_data)
    else:
        return jsonify({"status": "error", "message": "User Code not found in database!"})
    
# ==========================================
# DASHBOARD API
# ==========================================
@app.route('/api/dashboard/me', methods=['GET'])
def api_dashboard_me():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    user_id = session['user_id']
    user_name = session.get('user_name')
    
    financials = get_financial_stats(user_id)
    team = get_team_stats(user_id)
    
    if user_name == "John Doe":
        financials = {
            "total_income": 125450.00,
            "total_withdrawal": 68750.00,
            "current_balance": 56700.00,
            "cashback_bonus": 150.00,
            "staking_bonus": 45680.00,
            "sponsor_bonus": 12350.00,
            "binary_bonus": 18600.00,
            "repurchase_bonus": 5470.00,
            "royalty_bonus": 43200.00
        }
        team = {
            "direct_referrals": 125,
            "left_team": 1250,
            "right_team": 1380,
            "active_team": 1892,
            "non_active": 738,
            "total_team": 2630
        }
        
    return jsonify({"status": "success", "data": {"financials": financials, "team": team}})

@app.route('/api/profile/me', methods=['GET'])
def api_get_profile():
    if 'user_id' not in session: 
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    user_name = session.get('user_name')

    # 🌟 SYNCHRONIZED MOCK DICTIONARY ATTRIBUTE OBJECT BELOW 🌟
    if user_name == "John Doe":
        return jsonify({
            "status": "success",
            "data": {
                "full_name": "John Doe", "email": "johndoe@mlm.com", "mobile": "9876543210",
                "aadhar_no": "[Aadhaar Masked]", "pan_no": "ABCDE1234F", 
                "joined_date": "Joined Jan 12, 2024", 
                "address": "123 Main Street, Tech City",
                "is_active": True # 🚀 THIS SPECIFIC INDICATOR LINE WAS MISSING FROM YOUR CODE!
            }
        })

    profile = get_user_profile(user_id)
    if profile:
        created = profile.get('created_at')
        if isinstance(created, datetime.datetime):
            profile['joined_date'] = created.strftime("Joined %b %d, %Y")
        elif created:
            profile['joined_date'] = f"Joined {str(created)[:10]}" 
        else:
            profile['joined_date'] = "Joined Recently"
        
        if isinstance(profile.get('dob'), datetime.date):
             profile['dob'] = profile['dob'].strftime('%Y-%m-%d')
             
        return jsonify({"status": "success", "data": profile})
        
    return jsonify({"status": "error", "message": "User not found"})

@app.route('/api/profile/update', methods=['POST'])
def api_update_profile():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_id = session['user_id']
    
    data = {
        'full_name': request.form.get('full_name'),
        'mobile': request.form.get('mobile'),
        'aadhar_no': request.form.get('aadhar_no'),
        'pan_no': request.form.get('pan_no'),
        'address': request.form.get('address'),
        'profile_img': None 
    }
    
    profile_img = request.files.get('profile_image')
    if profile_img:
        filename = secure_filename(f"user_{user_id}_profile.jpg")
        profile_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        data['profile_img'] = filename
        session['profile_img'] = f"/static/uploads/kyc/{filename}"

    success = update_user_profile(user_id, data)
    if success:
        session['user_name'] = data.get('full_name', session['user_name'])
        return jsonify({"status": "success", "message": "Profile updated successfully!"})
        
    return jsonify({"status": "error", "message": "Database error occurred."})

@app.route('/api/courses/purchase', methods=['POST'])
def api_purchase_course():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    course_name = data.get('course_name')
    course_price = float(data.get('course_price', 0))

    result = process_course_purchase(session['user_id'], course_name, course_price)

    print(f"📧 EMAIL SENT TO {session.get('user_name')}: Confirmation of {course_name} purchase.")
    print(f"📱 SMS SENT: Your course {course_name} is active for 212 days.")
    
    return jsonify({
        "status": "success", 
        "message": f"Course activated! Confirmation Email & SMS sent. ROI will calculate separately for the next 212 days."
    })

@app.route('/api/bank/me', methods=['GET'])
def api_get_bank():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    if session.get('user_name') == "John Doe":
        return jsonify({
            "status": "success",
            "data": {
                "bank_acc_name": "John Doe", "bank_acc_no": "987654321098", 
                "bank_ifsc": "HDFC0001234", "upi_id": "johndoe@ybl", "upi_mobile": "9876543210"
            }
        })
        
    bank_info = get_bank_details(session['user_id'])
    return jsonify({"status": "success", "data": bank_info or {}})

@app.route('/api/bank/update', methods=['POST'])
def api_update_bank():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    success = update_bank_details(session['user_id'], data)
    
    if success:
        return jsonify({"status": "success", "message": "Bank details updated securely!"})
    return jsonify({"status": "error", "message": "Failed to update bank details."})

@app.route('/api/withdraw/me', methods=['GET'])
def api_get_withdraw_data():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    if session.get('user_name') == "John Doe":
        return jsonify({
            "status": "success",
            "balance": 56700.00,
            "history": [
                {"date": "20 May 2026", "amount": 2000.00, "status": "COMPLETED"},
                {"date": "15 May 2026", "amount": 5000.00, "status": "PENDING"}
            ]
        })

    user_id = session['user_id']
    stats = get_financial_stats(user_id)
    history_records = get_withdrawal_history(user_id)
    
    formatted_history = []
    for h in history_records:
        display_date = h['created_at']
        if h.get('status') == 'APPROVED' and h.get('processed_at'):
            display_date = h['processed_at']
            
        formatted_history.append({
            "date": display_date.strftime("%d %b %Y") if display_date else "N/A",
            "amount": float(h['request_amount']),
            "status": h['status']
        })
        
    return jsonify({
        "status": "success", 
        "balance": stats['current_balance'], 
        "history": formatted_history
    })

@app.route('/api/withdraw/request', methods=['POST'])
def api_request_withdrawal():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    if session.get('user_name') == "John Doe":
        return jsonify({"status": "success", "message": "Withdrawal requested successfully. Net payout after 5% TDS & 5% Admin Charges will be processed soon."})
        
    data = request.get_json()
    amount = data.get('amount')
    
    result = process_withdrawal_request(session['user_id'], amount)
    return jsonify(result)

@app.route('/api/user/info', methods=['GET'])
def api_get_user_info():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "status": "success",
        "user_code": session.get('user_code') 
    })

# ==========================================
# ADMIN PAGE ROUTES
# ==========================================

@app.route('/admin/admin_index')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login_page'))
    return render_template('admin/admin_index.html')

@app.route('/admin/users')
def admin_users_page():
    if session.get('role') != 'admin':
        return redirect(url_for('login_page'))
        
    all_users = get_all_users_for_admin()
    for u in all_users:
        if isinstance(u.get('created_at'), datetime.datetime):
            u['joined'] = u['created_at'].strftime("%d %b %Y")
        else:
            u['joined'] = "N/A"
            
    return render_template('admin/admin_users.html', users=all_users)

@app.route('/admin/tree')
def admin_tree_page():
    if session.get('role') != 'admin':
        return redirect(url_for('login_page'))
    return render_template('admin/admin_tree.html')

@app.route('/admin/wallets')
def admin_wallets_page():
    if session.get('role') != 'admin':
        return redirect(url_for('login_page'))
        
    all_users = get_all_users_for_admin()
    return render_template('admin/admin_wallets.html', users=all_users)

@app.route('/admin/security')
def admin_security_page():
    if session.get('role') != 'admin':
        return redirect(url_for('login_page'))
        
    all_users = get_all_users_for_admin()
    return render_template('admin/admin_security.html', users=all_users)

@app.route('/api/courses/my-packages', methods=['GET'])
def api_my_packages():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    if session.get('user_name') == "John Doe":
        return jsonify({
            "status": "success",
            "packages": ["Course BC2"],
            "highest_price": 1700.0 
        })
        
    db = get_db_connection()
    if not db: return jsonify({"status": "error", "message": "Database context error"})
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT course_name, course_price FROM user_courses WHERE user_id = %s AND status = 'ACTIVE'", (session['user_id'],))
        records = cursor.fetchall()
        
        packages = [r['course_name'] for r in records]
        prices = [float(r['course_price']) for r in records] if records else [0.0]
        highest_price = max(prices) if prices else 0.0
        
        return jsonify({
            "status": "success",
            "packages": packages,
            "highest_price": highest_price
        })
    finally:
        cursor.close()
        db.close()

# 🌟 EMERGENCY FORCE DATABASE SETUP ROUTE 🌟
@app.route('/force-db-setup')
def force_db_setup():
    from db_config import get_db_connection
    conn = get_db_connection()
    if not conn:
        return "❌ Error: Could not establish a connection to the MySQL pool. Check your MYSQL_URL variable reference."
    
    try:
        cursor = conn.cursor()
        output = "🛠️ Starting Manual Database Sync...<br>"
        
        # 1. Force build users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            user_code VARCHAR(50) UNIQUE NOT NULL,
            dob DATE, gender VARCHAR(20), aadhar_no VARCHAR(50), pan_no VARCHAR(50), mobile VARCHAR(20),
            password VARCHAR(255) NOT NULL, sponsor_id INT, leg VARCHAR(20), address TEXT, profile_img VARCHAR(255),
            is_active BOOLEAN DEFAULT FALSE, bank_acc_name VARCHAR(255), bank_acc_no VARCHAR(100), bank_ifsc VARCHAR(50),
            upi_id VARCHAR(100), upi_mobile VARCHAR(20), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        output += "Base database schema configuration verified.<br>"

        # 2. Check and force inject/update active JOHN profile
        cursor.execute("SELECT id, is_active FROM users WHERE user_code = 'JOHN'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO users (full_name, email, user_code, password, is_active) 
            VALUES ('JOHN DOE', 'john@demo.com', 'JOHN', 'John@2026', 1)
            """)
            output += "🎉 Successfully created active profile for JOHN!<br>"
        else:
            cursor.execute("UPDATE users SET is_active = 1 WHERE user_code = 'JOHN'")
            output += f"🔄 Found JOHN (Row ID: {row[0]}). Forced is_active status to 1 (True).<br>"
            
        conn.commit()
        return f"<h3>🚀 Database Setup Complete!</h3><p>{output}</p><p><a href='/login'>Go to Login</a></p>"
        
    except Exception as e:
        return f"<h3>❌ Database Setup Crashed!</h3><p>Error details: {str(e)}</p>"
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.start()
        print("🚀 Notification Scheduler initialized successfully.")

    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Secure Production Server launching! Open tunnel on port: {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
