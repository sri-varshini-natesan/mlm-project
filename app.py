from flask import Flask, Response, jsonify, request, render_template, session, redirect, url_for
from db_config import (
    get_financial_stats, get_team_stats, get_tree_view_data, 
    process_course_purchase, process_withdrawal_request,
    register_new_user, verify_login, get_user_profile, 
    update_user_profile, get_bank_details, update_bank_details, get_withdrawal_history,
    get_all_users_for_admin, get_db_connection, calculate_daily_incomes # ADDED THIS IMPORT
)
import datetime
import os
from werkzeug.utils import secure_filename
import csv
import io

# --- NOTIFICATIONS ---
from apscheduler.schedulers.background import BackgroundScheduler
import notification

app = Flask(__name__)
app.secret_key = 'mlm_super_secure_key_2026_fixed_xyz987'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # False because using HTTP not HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

UPLOAD_FOLDER = 'static/uploads/kyc'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ==========================================
# ADMIN ROUTE PROTECTION GUARD
# ==========================================
@app.before_request
def require_admin_for_admin_routes():
    if request.path.startswith('/admin/'):
        if session.get('role') != 'admin':
            return redirect(url_for('login_page'))

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
    """Automatically sends these variables to EVERY HTML file"""
    user_name = session.get('user_name')
    img = session.get('profile_img')
    
    if not img:
        if user_name == "John Doe":
            img = "https://i.pravatar.cc/150?img=68"
        else:
            img = "https://cdn-icons-png.flaticon.com/512/149/149071.png"
            
    return {
        'user_name': user_name,
        'user_code': session.get('user_code'),
        'profile_img': img
    }
    
@app.route('/debug/init-and-check')
def debug_init():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # 1. Ensure the users table exists (in case Aiven is empty)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255),
            user_code VARCHAR(50) UNIQUE,
            password VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    
    # 2. Check what's in there
    cursor.execute("SELECT user_code, full_name FROM users")
    users = cursor.fetchall()
    
    cursor.close()
    db.close()
    return f"Current Users: {users}"
# ==========================================
# PAGE ROUTES
# ==========================================

@app.route('/')
def home():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    user_code = session.get('user_code')
    
    # Generate the Gold Standard Smart Links
    left_link = f"{request.host_url}signup/{user_code}?side=left"
    right_link = f"{request.host_url}signup/{user_code}?side=right"
    
    # Pass both links to the dashboard template
    return render_template('user/index.html', left_link=left_link, right_link=right_link)

@app.route('/profile')
def profile_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/profile.html')

@app.route('/courses')
def courses_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    return render_template('user/courses.html')

@app.route('/my-tree')
def my_tree():
    return render_template('user/my_tree.html', user_code=session.get('user_code'))

@app.route('/my-team')
def my_team():
    return render_template('user/my_team.html')

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

@app.route('/signup', defaults={'sponsor_code': ''})
@app.route('/signup/<sponsor_code>')
def signup_page(sponsor_code):
    # 1. Fallback just in case someone uses the old ?ref= format
    if not sponsor_code:
        sponsor_code = request.args.get('ref', '')
        
    # 2. Capture the 'side' from the URL (e.g., ?side=left)
    leg_side = request.args.get('side', '').lower()
    
    # 3. Pass both the sponsor code AND the leg side to the HTML form
    return render_template('user/signup.html', ref_code=sponsor_code, leg_side=leg_side)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# ==========================================
# AUTHENTICATION API
# ==========================================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True)
    if not data:
        data = request.form

    raw_user = data.get('user_code') or data.get('username') or data.get('login_id') or data.get('email') or ''
    raw_pass = data.get('password') or ''
    
    user_code = str(raw_user).strip()
    password = str(raw_pass).strip()

    if not user_code or not password:
        return jsonify({"status": "error", "message": "Please enter both Login ID and Password."})
    
    if user_code == "ADMIN" and password == "Admin@2026!":
        session.permanent = True
        session['user_id'] = 0
        session['user_name'] = "Super Admin"
        session['user_code'] = "ADMIN"
        session['role'] = "admin"
        return jsonify({
            "status": "success",
            "message": "Welcome back, Admin!",
            "redirect": "/admin/dashboard"
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
    
    if user_code == "MLM87872" and password == "John@2026":
        session['user_id'] = 1 
        session['user_name'] = "John Doe"
        session['user_code'] = "MLM87872"
        session['role'] = "user"
        return jsonify({"status": "success", "message": "Welcome back, John!", "redirect": "/"})
    
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
@app.route('/api/courses/purchase', methods=['POST'])
def api_purchase_course():
    # 1. Security check: Is the user logged in?
    if 'user_id' not in session: 
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    # 2. Get the data from the frontend
    data = request.get_json()
    
    # IMPORTANT: Check what your frontend JS is sending. It might be 'course_id' or 'courseId'
    course_id = data.get('course_id') 
    
    if not course_id:
        return jsonify({"status": "error", "message": "Course ID is missing."})
        
    # 3. Send to the database engine
    try:
        # Call the new function you just put in db_config.py
        result = process_course_purchase(session['user_id'], course_id)
        return jsonify(result)
    except Exception as e:
        print(f"Purchase Error: {str(e)}")
        return jsonify({"status": "error", "message": "An internal server error occurred."}), 500
    
@app.route('/api/admin/tree-data/<user_code>')
def api_admin_tree_data(user_code):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    tree_data = get_tree_view_data(user_code)
    if tree_data:
        return jsonify(tree_data)
    else:
        return jsonify({"status": "error", "message": "User Code not found in database!"})

def get_user_node_data(user_code):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch the user with their Course and Join Date
    query = """
        SELECT 
            u.id, 
            u.name, 
            u.image, 
            u.active_status as active,
            u.created_at as join_date,
            c.name as course_name
        FROM users u
        LEFT JOIN user_courses uc ON u.id = uc.user_id
        LEFT JOIN courses c ON uc.course_id = c.id
        WHERE u.user_code = %s
    """
    cursor.execute(query, (user_code,))
    user = cursor.fetchone()
    
    if not user:
        return None
        
    # 2. Format the date to look clean (e.g., "08 Jun 2026")
    formatted_date = user['join_date'].strftime("%d %b %Y") if user['join_date'] else "Unknown"
        
    # 3. Return the dictionary with the NEW fields attached
    return {
        "id": user['id'],
        "name": user['name'],
        "image": user['image'] or "default_avatar.png",
        "active": bool(user['active']),
        "course": user['course_name'] or "Basic Package", # NEW
        "join_date": formatted_date # NEW
    }

@app.route('/income-history')
def income_history_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    bonus_type = request.args.get('type', 'UNKNOWN')

    title_map = {
        'DAILY_ROI': 'Self Staking Bonus History',
        'DIRECT_SPONSOR': 'Direct Sponsor Bonus History',
        'BINARY': 'Binary Bonus History',
        'REPURCHASE': 'Repurchase Bonus History',
        'ROYALTY': 'Captain Royalty Bonus History'
    }

    display_title = title_map.get(bonus_type, 'Income History')

    return render_template(
        'user/income_history.html',
        bonus_type=bonus_type,
        display_title=display_title
    )

# ==========================================
# DASHBOARD API
# ==========================================
@app.route('/api/dashboard/me', methods=['GET'])
def api_dashboard_me():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_id = session['user_id']
    user_name = session.get('user_name')
    financials = get_financial_stats(user_id)
    team = get_team_stats(user_id)
    
    if user_name == "John Doe":
        financials = {
            "total_income": 125450.00, "total_withdrawal": 68750.00, "current_balance": 56700.00, "cashback_bonus": 150.00,
            "staking_bonus": 45680.00, "sponsor_bonus": 12350.00, "binary_bonus": 18600.00, "repurchase_bonus": 5470.00, "royalty_bonus": 43200.00
        }
        team = { "direct_referrals": 125, "left_team": 1250, "right_team": 1380, "active_team": 1892, "non_active": 738, "total_team": 2630 }
        
    return jsonify({"status": "success", "data": {"financials": financials, "team": team}})

@app.route('/api/profile/me', methods=['GET'])
def api_get_profile():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_id = session['user_id']
    user_name = session.get('user_name')

    if user_name == "John Doe":
        return jsonify({"status": "success", "data": {
            "full_name": "John Doe", "email": "johndoe@mlm.com", "mobile": "9876543210", "aadhar_no": "[Aadhaar Redacted]", "pan_no": "ABCDE1234F", 
            "joined_date": "Joined Jan 12, 2024", "address": "123 Main Street, Tech City" , "is_active": True }})

    profile = get_user_profile(user_id)
    if profile:
        created = profile.get('created_at')
        if isinstance(created, datetime.datetime): profile['joined_date'] = created.strftime("Joined %b %d, %Y")
        elif created: profile['joined_date'] = f"Joined {str(created)[:10]}" 
        else: profile['joined_date'] = "Joined Recently"
        if isinstance(profile.get('dob'), datetime.date): profile['dob'] = profile['dob'].strftime('%Y-%m-%d')
        return jsonify({"status": "success", "data": profile})
    return jsonify({"status": "error", "message": "User not found"})

@app.route('/api/courses/my-packages', methods=['GET'])
def api_my_packages():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    if session.get('user_name') == "John Doe": 
        return jsonify({"status": "success", "owned_courses": ["Course BC2"], "purchased_today": []})
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # UPDATED: Now joins with the 'courses' table to get the name
        cursor.execute("""
            SELECT DISTINCT c.name as course_name 
            FROM user_courses uc 
            JOIN courses c ON uc.course_id = c.id 
            WHERE uc.user_id = %s AND uc.status = 'ACTIVE'
        """, (session['user_id'],))
        owned_courses = [r['course_name'] for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT DISTINCT c.name as course_name 
            FROM user_courses uc 
            JOIN courses c ON uc.course_id = c.id 
            WHERE uc.user_id = %s AND DATE(uc.created_at) = CURDATE()
        """, (session['user_id'],))
        purchased_today = [r['course_name'] for r in cursor.fetchall()]
        
        return jsonify({"status": "success", "owned_courses": owned_courses, "purchased_today": purchased_today})
    finally:
        cursor.close()
        db.close()

@app.route('/api/income-history', methods=['GET'])
def api_income_history():
    # 1. Ensure user is logged in
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'error': 'Not logged in'})

    user_id = session['user_id']
    
    # 2. Get the requested bonus type from the frontend URL and clean it
    requested_type = request.args.get('type', '').lower().strip()

    # 3. Bulletproof Mapping: Catch variations of the requested name
    db_bonus_type = None
    if 'staking' in requested_type or 'roi' in requested_type:
        db_bonus_type = 'STAKING_BONUS'
    elif 'sponsor' in requested_type or 'direct' in requested_type:
        db_bonus_type = 'DIRECT_SPONSOR'
    elif 'binary' in requested_type or 'match' in requested_type:
        db_bonus_type = 'BINARY_MATCH'
    elif 'cashback' in requested_type:
        db_bonus_type = 'CASHBACK'

    if not db_bonus_type:
        return jsonify({'status': 'error', 'error': f"Unknown bonus type: '{requested_type}'"})

    # 4. Fetch the data from the database
    db = get_db_connection()
    if not db:
        return jsonify({'status': 'error', 'error': 'Database connection failed'})
        
    cursor = db.cursor(dictionary=True)
    try:
        # Fetch only CREDITS matching the exact database bonus type
        cursor.execute("""
            SELECT amount, created_at, description 
            FROM wallet_transactions 
            WHERE user_id = %s AND transaction_type = 'CREDIT' AND bonus_type = %s
            ORDER BY created_at ASC
        """, (user_id, db_bonus_type))
        
        records = cursor.fetchall()

        # 5. Format the data EXACTLY how your frontend JavaScript expects it
        formatted_data = []
        for index, row in enumerate(records):
            formatted_data.append({
                "day_count": index + 1,
                "date": row['created_at'].strftime("%d %b %Y, %I:%M %p"), 
                "amount": float(row['amount']),
                "description": row['description']
            })

        # Reverse the list so newest entries show at the top
        formatted_data.reverse()

        return jsonify({
            'status': 'success',
            'data': formatted_data
        })

    except Exception as e:
        print(f"Error fetching income history: {e}")
        return jsonify({'status': 'error', 'error': 'Failed to load history'})
    finally:
        cursor.close()
        db.close()

@app.route('/api/withdraw/history')
def get_withdrawal_history_api():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    # Fetching history for the current logged-in user
    cursor.execute("""
        SELECT request_amount, net_payable, status, created_at 
        FROM withdrawals 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    
    history = cursor.fetchall()
    cursor.close()
    db.close()
    
    return jsonify({"status": "success", "history": history})

@app.route('/api/withdraw/request', methods=['POST'])
def api_withdraw_request():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    data = request.get_json()
    amount = float(data.get('amount', 0))
    user_id = session['user_id']
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Fetch exact balance from users table
        cursor.execute("SELECT wallet_balance FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user or float(user['wallet_balance']) < amount:
            return jsonify({"status": "error", "message": "Insufficient funds"})

        # 2. Save to withdrawals table (So it shows up on reload)
        cursor.execute("""
            INSERT INTO withdrawals (user_id, request_amount, net_payable, status, created_at) 
            VALUES (%s, %s, %s, 'PENDING', NOW())
        """, (user_id, amount, amount)) # Adjust if you have TDS/Admin fees
        
        # 3. Deduct from users table
        cursor.execute("UPDATE users SET wallet_balance = wallet_balance - %s WHERE id = %s", (amount, user_id))
        
        db.commit()
        return jsonify({"status": "success", "message": "Withdrawal requested successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/withdraw/me')
def api_withdraw_me():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # 1. Get balance from users table
    cursor.execute("SELECT wallet_balance FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    balance = float(user['wallet_balance']) if user else 0
    
    # 2. Get history from withdrawals table
    cursor.execute("""
        SELECT DATE_FORMAT(created_at, '%d %b %Y') as date, request_amount as amount, status 
        FROM withdrawals 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (session['user_id'],))
    history = cursor.fetchall()
    
    cursor.close(); db.close()
    return jsonify({"status": "success", "balance": balance, "history": history})

# ==========================================
# ADMIN API ENDPOINTS - WITH DUMMY BYPASS
# ==========================================

@app.route('/api/admin/debug/force-midnight', methods=['GET'])
def force_midnight():
    try:
        # Call your exact calculation function here
        calculate_daily_incomes() 
        return jsonify({
            "status": "success", 
            "message": "Midnight calculation executed successfully!"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Calculation failed: {str(e)}"
        }), 500
    
@app.route('/api/admin/dashboard-stats')
def api_admin_dashboard_stats():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok","total_users":25430,"active_users":18760,
            "inactive_users":6670,"today_joining":312,"total_deposits":1245680,
            "total_withdrawals":856210,"company_turnover":2875630,"income_distributed":1568950,
            "pending_withdrawals":125600,"today_roi":245300,"course_sales":8940,"monthly_revenue":432800})
    # DB Logic
    db = get_db_connection()
    if not db: return jsonify({"status":"error"})
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total = cursor.fetchone()['total']
        return jsonify({"status":"ok","total_users":total})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/users')
def api_admin_users():
    # --- DUMMY DATA BLOCK FOR ADMIN ---
    if session.get('user_name') == "Super Admin":
        dummy_users = [
            {"id": 1, "user_code": "MLM001", "full_name": "Ravi Kumar", "mobile": "9876543210", "email": "ravi@example.com", "is_active": 1, "created_at": "15 Jan 2024", "sponsor_code": "Admin", "status": "Active", "wallet_balance": 12450.0},
            {"id": 2, "user_code": "MLM002", "full_name": "Suresh Babu", "mobile": "9876543211", "email": "suresh@example.com", "is_active": 1, "created_at": "18 Jan 2024", "sponsor_code": "MLM001", "status": "Active", "wallet_balance": 8200.0},
            {"id": 3, "user_code": "MLM003", "full_name": "Priya Sharma", "mobile": "9876543212", "email": "priya@example.com", "is_active": 0, "created_at": "20 Jan 2024", "sponsor_code": "MLM001", "status": "Inactive", "wallet_balance": 3100.0},
            {"id": 4, "user_code": "MLM004", "full_name": "Arun Prakash", "mobile": "9876543213", "email": "arun@example.com", "is_active": 1, "created_at": "22 Jan 2024", "sponsor_code": "MLM002", "status": "Active", "wallet_balance": 18750.0},
            {"id": 5, "user_code": "MLM005", "full_name": "Karthik Raja", "mobile": "9876543214", "email": "karthik@example.com", "is_active": 1, "created_at": "25 Jan 2024", "sponsor_code": "MLM001", "status": "Active", "wallet_balance": 6900.0}
        ]
        return jsonify({"status":"ok","users":dummy_users,"total":5,"active":4,"inactive":1,"today":0,"page":1,"per_page":20})

    # --- REAL DATABASE LOGIC ---
    db = get_db_connection()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    offset = (page - 1) * per_page
    
    if not db:
        return jsonify({"status":"error","message":"DB unavailable","users":[],"total":0})
    
    cursor = db.cursor(dictionary=True)
    try:
        where = []
        params = []
        if search:
            where.append("(u.full_name LIKE %s OR u.user_code LIKE %s OR u.mobile LIKE %s OR u.email LIKE %s)")
            s = f"%{search}%"
            params += [s, s, s, s]
        if status_filter == 'Active':
            where.append("u.is_active=1")
        elif status_filter == 'Inactive':
            where.append("u.is_active=0")
        
        where_str = "WHERE " + " AND ".join(where) if where else ""
        
        # Get count
        cursor.execute(f"SELECT COUNT(*) as total FROM users u {where_str}", params)
        total = cursor.fetchone()['total']
        
        # Get actual data with join for sponsor code and subquery for wallet balance
        cursor.execute(f"""
            SELECT u.id, u.user_code, u.full_name, u.mobile, u.email, u.is_active, 
                   u.created_at, s.user_code as sponsor_code,
                   COALESCE((SELECT SUM(CASE WHEN transaction_type='CREDIT' THEN amount ELSE -amount END) 
                             FROM wallet_transactions WHERE user_id=u.id),0) as wallet_balance
            FROM users u 
            LEFT JOIN users s ON u.sponsor_id = s.id
            {where_str} 
            ORDER BY u.created_at DESC LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        
        rows = cursor.fetchall()
        for r in rows:
            if isinstance(r.get('created_at'), datetime.datetime):
                r['created_at'] = r['created_at'].strftime('%d %b %Y')
            r['status'] = 'Active' if r['is_active'] else 'Inactive'
            r['wallet_balance'] = float(r['wallet_balance'] or 0)
            
        return jsonify({
            "status": "ok",
            "users": rows,
            "total": total,
            "page": page,
            "per_page": per_page
        })
    finally:
        cursor.close()
        db.close()

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
def api_admin_get_user(user_id):
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "user": {
            "full_name": "Ravi Kumar", "user_code": "MLM001", "mobile": "9876543210", "email": "ravi@example.com",
            "aadhar_no": "[Aadhaar Redacted]", "pan_no": "ABCDE1234F", "is_active": True, "created_at": "15 Jan 2024"
        }})

@app.route('/api/admin/users/<int:user_id>/update', methods=['POST'])
def api_admin_update_user(user_id):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db_connection()
    if not db: return jsonify({"status":"error", "message": "DB error"})
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE users SET full_name=%s, mobile=%s, is_active=%s WHERE id=%s
        """, (data.get('full_name'), data.get('mobile'), data.get('is_active'), user_id))
        db.commit()
        return jsonify({"status":"ok", "message":"User updated successfully"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/users/<int:user_id>/suspend', methods=['POST'])
def api_admin_suspend_user(user_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"User suspended (Demo Mode)"})

@app.route('/api/admin/users/<int:user_id>/activate', methods=['POST'])
def api_admin_activate_user(user_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"User activated (Demo Mode)"})

@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
def api_admin_reset_password(user_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Password reset (Demo Mode)"})

@app.route('/api/admin/users/<int:user_id>/delete', methods=['POST'])
def api_admin_delete_user(user_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"User deleted (Demo Mode)"})

@app.route('/api/admin/users/<int:user_id>/wallet')
def api_admin_user_wallet(user_id):
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok","balance":12450.00,"transactions":[
            {"transaction_type": "CREDIT", "amount": 2500, "bonus_type": "ROI", "created_at": "04 Jun 2026"},
            {"transaction_type": "DEBIT", "amount": 1000, "bonus_type": "WITHDRAWAL", "created_at": "01 Jun 2026"}
        ]})

@app.route('/api/admin/users/<int:user_id>/income-history')
def api_admin_user_income(user_id):
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok","history":[
            {"bonus_type": "ROI", "amount": 2500, "created_at": "04 Jun 2026"},
            {"bonus_type": "DIRECT", "amount": 1500, "created_at": "03 Jun 2026"}
        ]})

@app.route('/api/admin/kyc')
def api_admin_kyc_list():
    # --- ADDED: DUMMY BYPASS FOR ADMIN PANEL TESTING ---
    if session.get('user_name') == "Super Admin":
        dummy_kyc = [
            {"id": 1, "full_name": "Ravi Kumar", "user_code": "MLM001", "document_type": "Aadhar Card", "document_number": "[Aadhaar Redacted]", "submitted_at": "04 Jun 2026", "status": "PENDING", "document_image": "test.jpg"},
            {"id": 2, "full_name": "Priya Sharma", "user_code": "MLM003", "document_type": "PAN Card", "document_number": "ABCDE1234F", "submitted_at": "03 Jun 2026", "status": "PENDING", "document_image": "test.jpg"}
        ]
        return jsonify({"status":"ok", "kyc": dummy_kyc, "total": 2})

    # --- REAL DATABASE LOGIC ---
    db = get_db_connection()
    status_filter = request.args.get('status','pending')
    page = int(request.args.get('page',1))
    per_page = 20
    offset = (page-1)*per_page
    if not db: return jsonify({"status":"error","kyc":[],"total":0})
    cursor = db.cursor(dictionary=True)
    try:
        kyc_status = status_filter.upper() if status_filter != 'pending' else 'PENDING'
        cursor.execute(f"""SELECT k.*, u.full_name, u.user_code 
                           FROM kyc_verifications k 
                           JOIN users u ON k.user_id=u.id 
                           WHERE k.status=%s 
                           ORDER BY k.submitted_at DESC LIMIT %s OFFSET %s""", 
                       (kyc_status, per_page, offset))
        rows = cursor.fetchall()
        for r in rows:
            for k,v in r.items():
                if isinstance(v, datetime.datetime): r[k] = str(v)
        cursor.execute("SELECT COUNT(*) as total FROM kyc_verifications WHERE status=%s", (kyc_status,))
        total = cursor.fetchone()['total']
        return jsonify({"status":"ok","kyc":rows,"total":total})
    finally:
        cursor.close(); db.close()
        
@app.route('/api/admin/kyc/<int:kyc_id>/approve', methods=['POST'])
def api_admin_kyc_approve(kyc_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"KYC Approved (Demo Mode)"})

@app.route('/api/admin/kyc/<int:kyc_id>/reject', methods=['POST'])
def api_admin_kyc_reject(kyc_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"KYC Rejected (Demo Mode)"})

@app.route('/api/admin/kyc/export')
def api_admin_kyc_export():
    # --- ADDED: DUMMY BYPASS FOR ADMIN EXPORT ---
    if session.get('user_name') == "Super Admin":
        import csv, io
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['user_code', 'full_name', 'document_type', 'document_number', 'status', 'submitted_at'])
        writer.writerow(['MLM001', 'Ravi Kumar', 'Aadhar Card', '[Aadhaar Redacted]', 'PENDING', '2026-06-04'])
        return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=kyc_demo.csv"})

    db = get_db_connection()
    if not db: return "DB Error", 500
    cursor = db.cursor(dictionary=True)
    status = request.args.get('status','PENDING').upper()
    try:
        cursor.execute("""SELECT u.user_code, u.full_name, k.document_type, k.document_number, k.status, k.submitted_at
            FROM kyc_verifications k JOIN users u ON k.user_id=u.id WHERE k.status=%s""", (status,))
        rows = cursor.fetchall()
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['user_code','full_name','document_type','document_number','status','submitted_at'])
        writer.writeheader()
        for r in rows:
            if isinstance(r.get('submitted_at'), datetime.datetime): r['submitted_at'] = str(r['submitted_at'])
            writer.writerow(r)
        return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=kyc.csv"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/packages')
def api_admin_packages_list():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "packages": [
            {"id": 1, "name": "Basic Package", "price": 5000, "roi_percent": 1.0, "duration_days": 250, "status": "Active"},
            {"id": 2, "name": "Master Package", "price": 12000, "roi_percent": 1.2, "duration_days": 250, "status": "Active"},
            {"id": 3, "name": "Advanced Package", "price": 25000, "roi_percent": 1.5, "duration_days": 250, "status": "Active"}
        ]})

@app.route('/api/admin/packages/create', methods=['POST'])
def api_admin_package_create():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Package Created (Demo Mode)"})

# Route to fetch a single package for Edit
@app.route('/api/admin/packages/<int:pid>')
def api_get_package(pid):
    # Matches the exact 3 demo packages from your list
    if session.get('user_name') == "Super Admin":
        demo_packages = {
            1: {"id": 1, "name": "Basic Package", "price": 5000, "roi_percent": 1.0, "duration_days": 250, "status": "Active"},
            2: {"id": 2, "name": "Master Package", "price": 12000, "roi_percent": 1.2, "duration_days": 250, "status": "Active"},
            3: {"id": 3, "name": "Advanced Package", "price": 25000, "roi_percent": 1.5, "duration_days": 250, "status": "Active"}
        }
        
        if pid in demo_packages:
            return jsonify({"status": "ok", "package": demo_packages[pid]})
        else:
            return jsonify({"status": "error", "message": "Package not found"}), 404

    # Real Database Logic
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM packages WHERE id=%s", (pid,))
    pkg = cursor.fetchone()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "package": pkg})

# Route to delete a package
@app.route('/api/admin/packages/<int:pid>/delete', methods=['POST'])
def api_delete_package(pid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM packages WHERE id=%s", (pid,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Package deleted successfully"})

@app.route('/api/admin/packages/<int:pid>/update', methods=['POST'])
def api_update_package(pid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE packages SET name=%s, price=%s WHERE id=%s", 
                   (data['name'], data['price'], pid))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Package updated successfully!"})

@app.route('/api/admin/binary-data')
def api_admin_binary_data():
    if session.get('user_name') == "Super Admin":
        return jsonify({
            "status": "ok",
            "total": 2, 
            "stats": {"left_bv": 145230, "right_bv": 180200, "matching_income": 325450},
            "history": [
                {
                    "user_code": "MLM001", 
                    "full_name": "Ravi Kumar", 
                    "left_bv": 45000, 
                    "right_bv": 62000, 
                    "matched_bv": 45000, 
                    "carry_forward": "17,000 (R)", 
                    "income": 4500, 
                    "date": "04 Jun 2026"
                },
                {
                    "user_code": "MLM002", 
                    "full_name": "Suresh Babu", 
                    "left_bv": 30000, 
                    "right_bv": 28000, 
                    "matched_bv": 28000, 
                    "carry_forward": "2,000 (L)", 
                    "income": 2800, 
                    "date": "04 Jun 2026"
                }
            ]
        })
    return jsonify({"status": "error", "message": "Unauthorized"}), 401

@app.route('/api/admin/binary/settings', methods=['POST'])
def api_admin_binary_settings():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "message":"Binary Settings Saved (Demo Mode)"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/binary/recalculate', methods=['POST'])
def api_admin_binary_recalculate():
    if session.get('user_name') == "Super Admin":
        data = request.get_json()
        uc = data.get('user_code', 'User')
        return jsonify({"status":"ok", "message":f"Binary recalculated for {uc} (Demo Mode)"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/binary/flush', methods=['POST'])
def api_admin_binary_flush():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "message":"All Carry Forward Volumes Flushed (Demo Mode)"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/binary/export')
def api_admin_binary_export():
    if session.get('user_name') == "Super Admin":
        import csv, io
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['User Code', 'Full Name', 'Left Volume', 'Right Volume', 'Matched', 'Carry Forward', 'Matching Income', 'Date'])
        writer.writerow(['MLM001', 'Ravi Kumar', '45000', '62000', '45000', '17,000 (R)', '4500', '04 Jun 2026'])
        writer.writerow(['MLM002', 'Suresh Babu', '30000', '28000', '28000', '2,000 (L)', '2800', '04 Jun 2026'])
        return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=binary_report.csv"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/tree/<user_code>')
def api_admin_tree_view(user_code):
    # This calls your database function
    data = get_tree_view_data(user_code) 
    if data:
        return jsonify(data)
    return jsonify({"status": "error", "message": "Tree data not found"}), 404

@app.route('/api/admin/team-list/<category>')
def get_team_list(category):
    user_id = session.get('user_id') 
    if not user_id:
        return jsonify({"members": []}), 401

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    if category == 'directs':
        # Added JOIN to courses table
        cursor.execute("""
            SELECT u.user_code as id, u.full_name as name, u.is_active, u.leg, c.name as course 
            FROM users u 
            LEFT JOIN user_courses uc ON u.id = uc.user_id AND uc.status = 'ACTIVE'
            LEFT JOIN courses c ON uc.course_id = c.id
            WHERE u.sponsor_id = %s
        """, (user_id,))
        members = cursor.fetchall()
        
    else:
        start_leg = 'left' if category == 'left' else 'right' if category == 'right' else None
        
        if start_leg:
            cursor.execute("SELECT id FROM users WHERE placement_id = %s AND leg = %s", (user_id, start_leg))
        else:
            cursor.execute("SELECT id FROM users WHERE placement_id = %s", (user_id,))
            
        start_nodes = cursor.fetchall()
        members = []
        
        for node in start_nodes:
            # Added JOIN to courses table in the recursive query
            query = """
                WITH RECURSIVE downline AS (
                    SELECT id, user_code, full_name, is_active, leg FROM users WHERE id = %s
                    UNION ALL
                    SELECT u.id, u.user_code, u.full_name, u.is_active, d.leg 
                    FROM users u INNER JOIN downline d ON u.placement_id = d.id
                )
                SELECT d.user_code as id, d.full_name as name, d.is_active, d.leg, c.name as course 
                FROM downline d
                LEFT JOIN user_courses uc ON d.id = uc.user_id AND uc.status = 'ACTIVE'
                LEFT JOIN courses c ON uc.course_id = c.id
                WHERE 1=1
            """
            
            if category == 'active': query += " AND d.is_active = 1"
            elif category == 'inactive': query += " AND d.is_active = 0"
            
            cursor.execute(query, (node['id'],))
            members.extend(cursor.fetchall())

    cursor.close()
    db.close()
    
    return jsonify({"members": members})

@app.route('/api/admin/level-bonus/update', methods=['POST'])
def api_admin_level_update():
    if session.get('user_name') == "Super Admin":
        data = request.get_json()
        return jsonify({"status":"ok", "message": f"Level {data['level']} updated!"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/level-bonus/export')
def api_admin_level_export():
    if session.get('user_name') == "Super Admin":
        import csv, io
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['User', 'From User', 'Level', 'Amount', 'Date'])
        writer.writerow(['MLM001', 'MLM211', 'Level 1', '250', '04 Jun 2026'])
        return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=level_bonus.csv"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/repurchase/settings', methods=['POST'])
def api_admin_repurchase_settings():
    if session.get('user_name') == "Super Admin":
        # Add your DB update logic here
        return jsonify({"status": "ok", "message": "Repurchase settings saved!"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/repurchase/export')
def api_admin_repurchase_export():
    if session.get('user_name') == "Super Admin":
        import csv, io
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['User', 'Previous Package', 'New Package', 'Bonus Paid', 'Date', 'Status'])
        writer.writerow(['MLM001', 'Basic', 'Master', '700', '04 Jun 2026', 'Approved'])
        return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=repurchase_report.csv"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/royalty/ranks/<int:rid>', methods=['GET'])
def api_admin_get_rank(rid):
    # Add DB query to fetch rank details
    return jsonify({"status": "ok", "rank": {"id": rid, "name": "Silver Captain", "royalty_percent": 0.5}})

@app.route('/api/admin/royalty/ranks/<int:rid>/delete', methods=['POST'])
def api_admin_delete_rank(rid):
    # Add DB query to delete rank
    return jsonify({"status": "ok", "message": "Rank deleted successfully"})

@app.route('/api/admin/royalty/export')
def api_admin_royalty_export():
    # 1. Create the CSV data in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['User', 'Rank', 'Left Team', 'Right Team', 'Achieved On', 'Monthly Royalty', 'Status'])
    writer.writerow(['Ravi Kumar', 'Diamond Captain', '2,450', '1,980', 'Jan 2024', '12,400', 'Active'])
    
    # 2. Return a Response that triggers a download
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=royalty_report.csv"}
    )

@app.route('/api/admin/deposits')
def api_admin_deposits():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "total": 48, "deposits": [
            {"id": 1, "user_code": "MLM211", "full_name": "Muthu Kumar", "amount": 5000, "payment_method": "UPI", "txn_ref": "TXN123456", "created_at": "04 Jun 2026", "status": "PENDING"},
            {"id": 2, "user_code": "MLM212", "full_name": "Lakshmi R", "amount": 12000, "payment_method": "NEFT", "txn_ref": "TXN123457", "created_at": "04 Jun 2026", "status": "PENDING"}
        ]})

@app.route('/api/admin/deposits/<int:dep_id>/approve', methods=['POST'])
def api_admin_deposit_approve(dep_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Deposit Approved (Demo Mode)"})

@app.route('/api/admin/deposits/<int:dep_id>/reject', methods=['POST'])
def api_admin_deposit_reject(dep_id):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Deposit Rejected (Demo Mode)"})

@app.route('/api/admin/deposits/manual', methods=['POST'])
def api_admin_manual_deposit():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Manual Deposit Created (Demo Mode)"})

@app.route('/api/admin/deposits/export')
def api_admin_deposits_export():
    import csv, io
    from flask import Response
    
    # 1. Prepare CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['User', 'Amount', 'Method', 'Txn ID', 'Submitted', 'Status'])
    
    # Replace this with your actual database query
    writer.writerow(['MLM211', '5000', 'UPI', 'TXN123456', '04 Jun 2026', 'PENDING'])
    
    # 2. Return as a file download
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=deposits_report.csv"}
    )

#---WITHDRAWALS---
@app.route('/api/admin/withdrawals')
def api_admin_withdrawals():
    USE_DEMO_DATA = True 

    if USE_DEMO_DATA:
        return jsonify({
            "status": "ok", 
            "total": 2, 
            "withdrawals": [
                {
                    "id": 1, 
                    "user_code": "MLM001", 
                    "full_name": "Ravi Kumar", 
                    "request_amount": 10000, 
                    "tds_detection": 500, 
                    "net_payable": 8800, 
                    "created_at": "04 Jun 2026", 
                    "status": "PENDING",
                    # --- ADD THESE FIELDS ---
                    "account_holder": "Ravi Kumar",
                    "bank_name": "State Bank of India",
                    "account_no": "123456789012",
                    "ifsc_code": "SBIN0001234"
                },
                {
                    "id": 2, 
                    "user_code": "MLM004", 
                    "full_name": "Arun Prakash", 
                    "request_amount": 5000, 
                    "tds_detection": 250, 
                    "net_payable": 4400, 
                    "created_at": "03 Jun 2026", 
                    "status": "APPROVED",
                    # --- ADD THESE FIELDS ---
                    "account_holder": "Arun Prakash",
                    "bank_name": "HDFC Bank",
                    "account_no": "987654321098",
                    "ifsc_code": "HDFC0000567"
                }
            ]
        })

    # DATABASE MODE
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db_connection()
    if not db: return jsonify({"status": "error", "message": "DB error"}), 500
    
    cursor = db.cursor(dictionary=True)
    status_filter = request.args.get('status', 'PENDING').upper()
    
    try:
        cursor.execute("""
            SELECT w.id, w.request_amount, w.tds_detection, w.net_payable, 
                w.created_at, w.status, u.user_code, u.full_name,
                b.account_holder, b.bank_name, b.account_no, b.ifsc_code
            FROM withdrawals w
            JOIN users u ON w.user_id = u.id
            LEFT JOIN bank_details b ON w.user_id = b.user_id
            WHERE w.status = %s
            ORDER BY w.created_at DESC
        """, (status_filter,))
        
        withdrawals = cursor.fetchall()
        return jsonify({"status": "ok", "total": len(withdrawals), "withdrawals": withdrawals})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/api/admin/withdrawals/<int:wid>/approve', methods=['POST'])
def api_admin_withdrawal_approve(wid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db_connection()
    cursor = db.cursor()
    # Update status in DB
    cursor.execute("UPDATE withdrawals SET status='APPROVED' WHERE id=%s", (wid,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Withdrawal Approved"})

@app.route('/api/admin/withdrawals/<int:wid>/reject', methods=['POST'])
def api_admin_withdrawal_reject(wid):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Withdrawal Rejected (Demo Mode)"})

@app.route('/api/admin/withdrawals/<int:wid>/hold', methods=['POST'])
def api_admin_withdrawal_hold(wid):
    if session.get('user_name') == "Super Admin":
        # Add your database 'UPDATE' logic here
        return jsonify({"status": "ok", "message": "Withdrawal held successfully!"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/withdrawals/<int:wid>')
def api_admin_get_withdrawal(wid):
    # DEMO MODE
    if session.get('user_name') == "Super Admin":
        dummy_data = {
            1: {
            "id": 1, "user_code": "MLM001", "full_name": "Ravi Kumar", 
            "request_amount": 10000, "tds_detection": 500, "net_payable": 8800, 
            "created_at": "04 Jun 2026", "status": "PENDING",
            "account_holder": "Ravi Kumar", "bank_name": "SBI", 
            "account_no": "123456789012", "ifsc_code": "SBIN0001234"
        },
        2: {
            "id": 2, "user_code": "MLM004", "full_name": "Arun Prakash", 
            "request_amount": 5000, "tds_detection": 250, "net_payable": 4400, 
            "created_at": "03 Jun 2026", "status": "APPROVED",
            "account_holder": "Arun Prakash", "bank_name": "HDFC Bank", 
            "account_no": "987654321098", "ifsc_code": "HDFC0000567"
        }
        }
        if wid in dummy_data:
            return jsonify({"status": "ok", "withdrawal": dummy_data[wid]})
        return jsonify({"status": "error", "message": "Not found"}), 404

    # REAL DB MODE
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # We explicitly join the bank_details table here
        cursor.execute("""
            SELECT w.*, u.full_name, u.user_code, 
                   b.account_holder, b.bank_name, b.account_no, b.ifsc_code 
            FROM withdrawals w 
            JOIN users u ON w.user_id = u.id 
            LEFT JOIN bank_details b ON w.user_id = b.user_id 
            WHERE w.id = %s
        """, (wid,))
        withdrawal = cursor.fetchone()
        
        if not withdrawal:
            return jsonify({"status": "error", "message": "Not found"}), 404
            
        # Ensure dates are strings for JSON
        if isinstance(withdrawal.get('created_at'), datetime.datetime):
             withdrawal['created_at'] = withdrawal['created_at'].strftime('%d %b %Y')
             
        return jsonify({"status": "ok", "withdrawal": withdrawal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/withdrawals/export')
def api_admin_withdrawals_export():
    if session.get('role') != 'admin': return "Unauthorized", 401
    
    # Simple CSV Export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['User Code', 'Full Name', 'Amount', 'TDS', 'Net Payable', 'Status', 'Date'])
    
    # Use dummy data or DB query here
    writer.writerow(['MLM001', 'Ravi Kumar', '10000', '500', '8800', 'PENDING', '04 Jun 2026'])
    
    return Response(output.getvalue(), mimetype='text/csv', 
                    headers={"Content-Disposition": "attachment;filename=withdrawals.csv"})

@app.route('/api/admin/wallet/credit', methods=['POST'])
def api_admin_wallet_credit():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Wallet Credited (Demo Mode)"})

@app.route('/api/admin/wallet/debit', methods=['POST'])
def api_admin_wallet_debit():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Wallet Debited (Demo Mode)"})

@app.route('/api/admin/wallet/ledger')
def api_admin_wallet_ledger():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok","transactions":[
            {"user_code":"MLM001", "full_name":"Ravi Kumar", "transaction_type":"CREDIT", "amount": 375, "remarks":"Daily ROI", "created_at":"04 Jun 2026"},
            {"user_code":"MLM002", "full_name":"Suresh Babu", "transaction_type":"DEBIT", "amount": 5000, "remarks":"Bank Transfer", "created_at":"03 Jun 2026"}
        ]})

# TREE
@app.route('/api/admin/tree/move', methods=['POST'])
def api_admin_move_user():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    user_id = data.get('user_id')
    new_parent_code = data.get('new_parent_code')
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Find the new parent ID
        cursor.execute("SELECT id FROM users WHERE user_code = %s", (new_parent_code,))
        parent = cursor.fetchone()
        
        if not parent:
            return jsonify({"status": "error", "message": "New parent not found!"}), 404
        
        # 2. Update the user's parent/sponsor in the database
        cursor.execute("UPDATE users SET sponsor_id = %s WHERE id = %s", (parent['id'], user_id))
        db.commit()
        
        return jsonify({"status": "ok", "message": "User moved successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()
# --- ROI -----

@app.route('/api/admin/roi/logs')
def api_admin_roi_logs():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok","logs":[
            {"user_code":"MLM001", "full_name":"Ravi Kumar", "package_name": "Advanced", "roi_percent": 1.5, "amount": 375, "created_at":"04 Jun 2026", "status": "Credited"},
            {"user_code":"MLM002", "full_name":"Suresh Babu", "package_name": "Master", "roi_percent": 1.2, "amount": 144, "created_at":"04 Jun 2026", "status": "Credited"},
            {"user_code":"MLM005", "full_name":"Karthik Raja", "package_name": "Basic", "roi_percent": 1.0, "amount": 50, "created_at":"04 Jun 2026", "status": "Credited"}
        ]})
    return jsonify({"status": "error", "message": "Database not implemented yet"})

@app.route('/api/admin/roi/manual-credit', methods=['POST'])
def api_admin_roi_manual_credit():
    if session.get('user_name') == "Super Admin": 
        return jsonify({"status":"ok","message":"Manual ROI Credited (Demo Mode)"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/roi/engine', methods=['POST'])
def api_admin_roi_engine():
    if session.get('user_name') == "Super Admin":
        action = request.json.get('action', 'update').upper()
        return jsonify({"status": "ok", "message": f"ROI Engine {action}D successfully (Demo Mode)"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/roi/export')
def api_admin_roi_export():
    if session.get('user_name') == "Super Admin":
        import csv, io
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['user_code', 'full_name', 'package', 'roi_percent', 'amount', 'date', 'status'])
        writer.writerow(['MLM001', 'Ravi Kumar', 'Advanced', '1.5%', '375', '04 Jun 2026', 'Credited'])
        writer.writerow(['MLM002', 'Suresh Babu', 'Master', '1.2%', '144', '04 Jun 2026', 'Credited'])
        return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=roi_logs.csv"})
    return jsonify({"error": "Unauthorized"}), 401

# --- DIRECT BONUS ---
@app.route('/api/admin/direct-bonus/settings', methods=['POST'])
def api_admin_direct_bonus_settings():
    if session.get('user_name') == "Super Admin":
        data = request.get_json()
        # Add your database logic here to save these percentages
        return jsonify({"status": "ok", "message": "Settings saved successfully!"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/api/admin/direct-bonus/export')
def api_admin_direct_bonus_export():
    fmt = request.args.get('format', 'excel') # 'excel' or 'pdf'
    
    # 1. Create a memory buffer for the CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 2. Add header row
    writer.writerow(['User', 'Referred', 'Package', 'Bonus %', 'Amount', 'Date', 'Status'])
    
    # 3. Add sample data (Replace this with your real DB query later)
    writer.writerow(['Ravi Kumar', 'MLM211', 'Advanced', '10%', '2500', '04 Jun 2026', 'Credited'])
    writer.writerow(['Suresh Babu', 'MLM212', 'Master', '8%', '960', '03 Jun 2026', 'Credited'])
    
    # 4. Return the data as a downloadable file
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=direct_bonus_report.{fmt}"
    return response

@app.route('/api/admin/reports/income')
def api_admin_income_reports():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "total": 18760, "rows": [
            {"user_code": "MLM001", "full_name": "Ravi Kumar", "bonus_type": "ROI", "amount": 93750, "created_at": "04 Jun 2026"},
            {"user_code": "MLM002", "full_name": "Suresh Babu", "bonus_type": "DIRECT", "amount": 18000, "created_at": "03 Jun 2026"},
            {"user_code": "MLM003", "full_name": "Arun Prakash", "bonus_type": "BINARY", "amount": 28780, "created_at": "02 Jun 2026"}
        ]})

@app.route('/api/admin/reports/income/export')
def api_admin_income_reports_export():
    if session.get('role') != 'admin': return "Unauthorized", 401
    
    # In a real app, query your DB here. For now, using your data format:
    data = [
        {"user_code": "MLM001", "full_name": "Ravi Kumar", "bonus_type": "ROI", "amount": 93750, "created_at": "04 Jun 2026"},
        {"user_code": "MLM002", "full_name": "Suresh Babu", "bonus_type": "DIRECT", "amount": 18000, "created_at": "03 Jun 2026"},
        {"user_code": "MLM003", "full_name": "Arun Prakash", "bonus_type": "BINARY", "amount": 28780, "created_at": "02 Jun 2026"}
    ]
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['User Code', 'Name', 'Type', 'Amount', 'Date'])
    for r in data:
        writer.writerow([r['user_code'], r['full_name'], r['bonus_type'], r['amount'], r['created_at']])
    
    return Response(output.getvalue(), mimetype='text/csv', 
                    headers={"Content-Disposition": "attachment;filename=income_report.csv"})

@app.route('/api/admin/audit-logs')
def api_admin_audit_logs():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "logs": [
            {"log_type": "LOGIN", "action": "Admin Login", "detail": "Super Admin logged in from IP 122.160.x.x", "created_at": "04 Jun 2026"},
            {"log_type": "WALLET", "action": "Wallet Credited", "detail": "₹375 credited to Ravi Kumar", "created_at": "04 Jun 2026"},
            {"log_type": "WITHDRAWAL", "action": "Withdrawal Approved", "detail": "₹4,400 paid to Arun Prakash", "created_at": "03 Jun 2026"}
        ]})
@app.route('/api/admin/audit-logs/all')
def api_admin_audit_logs_all():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    
    # Replace this with your actual database query
    # Example: cursor.execute("SELECT user_name, action, ip_address, created_at FROM audit_logs")
    logs = [
        {"user_name": "Admin", "action": "Logged in", "ip_address": "192.168.1.1", "created_at": "2026-06-07 10:00"},
        {"user_name": "Ravi Kumar", "action": "Updated profile", "ip_address": "103.22.1.5", "created_at": "2026-06-07 12:30"}
    ]
    
    return jsonify({"status": "ok", "logs": logs})

@app.route('/api/admin/tickets')
def api_admin_tickets():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "total": 24, "tickets": [
            {"id": 1042, "user_code": "MLM001", "full_name": "Ravi Kumar", "subject": "ROI not credited", "priority": "High", "status": "OPEN", "created_at": "04 Jun 2026"},
            {"id": 1041, "user_code": "MLM003", "full_name": "Priya Sharma", "subject": "Withdrawal missing", "priority": "Medium", "status": "OPEN", "created_at": "03 Jun 2026"}
        ]})

@app.route('/api/admin/tickets/<int:tid>/reply', methods=['POST'])
def api_admin_ticket_reply(tid):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Reply sent"})

@app.route('/api/admin/tickets/<int:tid>/close', methods=['POST'])
def api_admin_ticket_close(tid):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Ticket closed"})

@app.route('/api/admin/notifications/send', methods=['POST'])
def api_admin_send_notification():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Notification Broadcasted"})

@app.route('/api/admin/holidays')
def api_admin_holidays():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "holidays": [
            {"id": 1, "name": "Gandhi Jayanti", "holiday_date": "02 Oct 2026", "type": "ROI Pause"},
            {"id": 2, "name": "Diwali", "holiday_date": "20 Oct 2026", "type": "ROI Pause"}
        ]})

@app.route('/api/admin/holidays/add', methods=['POST'])
def api_admin_add_holiday():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status": "ok", "message": "Holiday added"})

    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO holidays (name, holiday_date, type, description) 
            VALUES (%s, %s, %s, %s)
        """, (data['name'], data['date'], data['type'], data['description']))
        db.commit()
        return jsonify({"status": "ok", "message": "Holiday added successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/settings/update', methods=['POST'])
def api_admin_update_settings():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json()
    section = data.get('section')
    
    # Logic: print the data to see what's arriving in your terminal
    print(f"Saving {section} data:", data)
    
    # TODO: Add your SQL UPDATE queries here
    # Example:
    # if section == 'company_info':
    #     cursor.execute("UPDATE system_settings SET company_name=%s ...", (data['company_name'],))
    
    return jsonify({"status": "ok", "message": f"{section.replace('_', ' ').capitalize()} updated!"})

#--- CRON JOBS 
@app.route('/api/admin/cron/run', methods=['POST'])
def api_admin_run_cron():
    # You must trigger your actual background task here
    return jsonify({"status": "ok", "message": "Job triggered successfully!"})

@app.route('/api/admin/cron/logs')
def api_admin_cron_logs():
    # Return your log data here
    return jsonify({
        "status": "ok",
        "logs": [
            {"job": "ROI Cron", "executed_at": "04 Jun 2026", "duration": "42 sec", "records": "18,760", "status": "Success"}
        ]
    })

@app.route('/api/admin/admins/<int:aid>')
def get_admin(aid):
    # Return dummy data for testing
    return jsonify({"status": "ok", "admin": {"id": aid, "name": "Admin User", "email": "admin@test.com", "role": "Super Admin"}})

@app.route('/api/admin/admins/<int:aid>/delete', methods=['POST'])
def delete_admin(aid):
    # Perform your DB DELETE here
    return jsonify({"status": "ok", "message": "Admin deleted successfully!"})

@app.route('/api/admin/sub-admins')
def api_admin_sub_admins_list():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "admins": [
            {"id": 1, "name": "Super Admin", "email": "admin@mlmsystem.com", "role": "Super Admin", "status": "Active"},
            {"id": 2, "name": "Manager Admin", "email": "manager@mlmsystem.com", "role": "Sub Admin", "status": "Active"}
        ]})

@app.route('/api/admin/sub-admins/create', methods=['POST'])
def api_admin_sub_admin_create():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Admin Created (Demo Mode)"})

@app.route('/api/admin/sub-admins/<int:aid>/delete', methods=['POST'])
def api_admin_sub_admin_delete(aid):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Admin Deleted (Demo Mode)"})

@app.route('/api/admin/royalty/ranks')
def api_admin_royalty_ranks():
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "ranks": [
            {"id": 1, "name": "Silver Captain", "royalty_percent": 0.5},
            {"id": 2, "name": "Gold Captain", "royalty_percent": 1.0},
            {"id": 3, "name": "Diamond Captain", "royalty_percent": 2.0}
        ]})

@app.route('/api/admin/royalty/ranks/create', methods=['POST'])
def api_admin_royalty_rank_create():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Rank Created (Demo Mode)"})

@app.route('/api/admin/royalty/ranks/<int:rid>/delete', methods=['POST'])
def api_admin_royalty_rank_delete(rid):
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Rank Deleted (Demo Mode)"})

@app.route('/api/admin/courses')
def api_admin_courses_list():
    # DUMMY BYPASS FOR ADMIN PANEL TESTING
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "total": 3, "courses": [
            {"id": 1, "name": "MLM Business Basics", "category": "Business", "price": 5000, "total_cnt": 3120, "visibility": "Public", "status": "Active"},
            {"id": 2, "name": "Advanced Marketing Strategies", "category": "Marketing", "price": 12000, "total_cnt": 5640, "visibility": "Public", "status": "Active"},
            {"id": 3, "name": "Financial Freedom Masterclass", "category": "Finance", "price": 25000, "total_cnt": 2180, "visibility": "App Only", "status": "Active"}
        ]})

    # REAL DATABASE LOGIC
    db = get_db_connection()
    if not db: 
        return jsonify({"status":"error", "message": "Database connection failed"}), 500
    
    cursor = db.cursor(dictionary=True)
    try:
        # Assuming you have a 'courses' table with columns: id, name, category, price, total_cnt, visibility, status
        cursor.execute("""
            SELECT id, name, category, price, total_cnt, visibility, status 
            FROM courses 
            ORDER BY id DESC
        """)
        courses = cursor.fetchall()
        return jsonify({"status": "ok", "courses": courses})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        db.close()

# Route to fetch a single course for View/Edit
# Updated Route to fetch a single course (Secured)
@app.route('/api/admin/courses/<int:cid>')
def api_get_course(cid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    
    # Bypass for Demo Mode
    if session.get('user_name') == "Super Admin":
        return jsonify({"status":"ok", "course": {"id": cid, "name": "MLM Business Basics", "price": 5000}})
        
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM courses WHERE id=%s", (cid,))
    course = cursor.fetchone()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "course": course})

# Updated Route to delete (Secured)
@app.route('/api/admin/courses/<int:cid>/delete', methods=['POST'])
def api_delete_course(cid):
    # Security Check
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    
    # Bypass for Demo Mode
    if session.get('user_name') == "Super Admin":
        return jsonify({"status": "ok", "message": "Deleted in Demo Mode"})
        
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM courses WHERE id=%s", (cid,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Deleted"})

@app.route('/api/admin/courses/create', methods=['POST'])
def api_admin_course_create():
    if session.get('user_name') == "Super Admin": return jsonify({"status":"ok","message":"Course Created (Demo Mode)"})

# ==========================================
# PAGE ROUTING FOR ADMIN
# ==========================================

def admin_render(section):
    return render_template('admin/admin_panel_complete.html', active=section)

@app.route('/admin/dashboard')
@app.route('/admin/admin_index')
def admin_dashboard(): return admin_render('dashboard')
@app.route('/admin/users')
def admin_users(): return admin_render('users')
@app.route('/admin/kyc')
def admin_kyc(): return admin_render('kyc')
@app.route('/admin/courses')
def admin_courses(): return admin_render('courses')
@app.route('/admin/packages')
def admin_packages(): return admin_render('packages')
@app.route('/admin/roi')
def admin_roi(): return admin_render('roi')
@app.route('/admin/binary')
def admin_binary(): return admin_render('binary')
@app.route('/admin/direct-bonus')
def admin_direct(): return admin_render('direct')
@app.route('/admin/level-bonus')
def admin_level(): return admin_render('level')
@app.route('/admin/repurchase')
def admin_repurchase(): return admin_render('repurchase')
@app.route('/admin/royalty')
def admin_royalty(): return admin_render('royalty')
@app.route('/admin/wallet')
def admin_wallet(): return admin_render('wallet')
@app.route('/admin/deposits')
def admin_deposits(): return admin_render('deposits')
@app.route('/admin/withdrawals')
def admin_withdrawals(): return admin_render('withdrawals')
@app.route('/admin/tree-view')
@app.route('/admin/tree')
def admin_tree(): return admin_render('tree')
@app.route('/admin/reports')
def admin_reports(): return admin_render('reports')
@app.route('/admin/notifications')
def admin_notifications(): return admin_render('notifications')
@app.route('/admin/tickets')
def admin_tickets(): return admin_render('tickets')
@app.route('/admin/holidays')
def admin_holidays(): return admin_render('holidays')
@app.route('/admin/settings')
def admin_settings(): return admin_render('settings')
@app.route('/admin/cron')
def admin_cron(): return admin_render('cron')
@app.route('/admin/audit')
def admin_audit(): return admin_render('audit')
@app.route('/admin/admins')
def admin_admins(): return admin_render('admins')

if __name__ == '__main__':
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.start()
        print("🚀 Notification Scheduler initialized successfully.")

    print("🚀 Secure Server starting! Open http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
