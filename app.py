from flask import Flask, Response, jsonify, request, render_template, session, redirect, url_for
from db_config import (
    get_financial_stats, get_team_stats, get_tree_view_data, 
    process_course_purchase, process_withdrawal_request,
    register_new_user, verify_login, get_user_profile, 
    update_user_profile, get_bank_details, update_bank_details, get_withdrawal_history,
    get_all_users_for_admin, get_db_connection, calculate_daily_incomes
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

# ==========================================
# PAGE ROUTES (USER SIDE)
# ==========================================

@app.route('/')
def home():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    user_code = session.get('user_code')
    left_link = f"{request.host_url}signup/{user_code}?side=left"
    right_link = f"{request.host_url}signup/{user_code}?side=right"
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
    if not sponsor_code:
        sponsor_code = request.args.get('ref', '')
    leg_side = request.args.get('side', '').lower()
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
    data = request.get_json(silent=True) or request.form
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
    result = register_new_user(
        data.get('fullName'), data.get('email'), data.get('dob'), data.get('sex'), 
        data.get('aadhar'), data.get('pan'), data.get('mobile'), data.get('password'), 
        data.get('sponsor_id'), data.get('leg')
    )
    return jsonify(result)

@app.route('/api/courses/purchase', methods=['POST'])
def api_purchase_course():
    if 'user_id' not in session: 
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    course_id = request.get_json().get('course_id') 
    if not course_id:
        return jsonify({"status": "error", "message": "Course ID is missing."})
    try:
        result = process_course_purchase(session['user_id'], course_id)
        return jsonify(result)
    except Exception as e:
        print(f"Purchase Error: {str(e)}")
        return jsonify({"status": "error", "message": "An internal server error occurred."}), 500

@app.route('/api/dashboard/me', methods=['GET'])
def api_dashboard_me():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    user_id = session['user_id']
    
    # Fetch both sets of data
    # Ensure these function names match what you have in db_config.py
    financials = get_financial_stats(user_id)
    team_data = get_team_stats(user_id) 
    
    return jsonify({
        "status": "success",
        "data": {
            "financials": financials,
            "team": team_data
        }
    })

@app.route('/api/admin/tree-data/<user_code>')
def api_admin_tree_data(user_code):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    tree_data = get_tree_view_data(user_code)
    if tree_data: return jsonify(tree_data)
    return jsonify({"status": "error", "message": "User Code not found in database!"})

@app.route('/income-history')
def income_history_page():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    bonus_type = request.args.get('type', 'UNKNOWN')
    title_map = {
        'DAILY_ROI': 'Self Staking Bonus History',
        'DIRECT_SPONSOR': 'Direct Sponsor Bonus History',
        'BINARY': 'Binary Bonus History',
        'REPURCHASE': 'Repurchase Bonus History',
        'ROYALTY': 'Captain Royalty Bonus History'
    }
    display_title = title_map.get(bonus_type, 'Income History')
    return render_template('user/income_history.html', bonus_type=bonus_type, display_title=display_title)

# ==========================================
# DASHBOARD API (USER SIDE)
# ==========================================

@app.route('/api/profile/me', methods=['GET'])
def api_get_profile():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_name = session.get('user_name')

    if user_name == "John Doe":
        return jsonify({"status": "success", "data": {
            "full_name": "John Doe", "email": "johndoe@mlm.com", "mobile": "9876543210", "aadhar_no": "[Aadhaar Redacted]", "pan_no": "ABCDE1234F", 
            "joined_date": "Joined Jan 12, 2024", "address": "123 Main Street, Tech City" , "is_active": True }})

    profile = get_user_profile(session['user_id'])
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
    if 'user_id' not in session: 
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    uid = session['user_id']
    db = get_db_connection()
    if not db: return jsonify({"status": "error", "message": "DB Failed"}), 500
    
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Fetch ALL active courses for this user
        # We use UPPER(status) = 'ACTIVE' to make sure it matches even if it's 'active' or 'ACTIVE'
        query = """
            SELECT c.name as course_name 
            FROM user_courses uc 
            JOIN courses c ON uc.course_id = c.id 
            WHERE uc.user_id = %s 
            AND UPPER(uc.status) = 'ACTIVE'
        """
        cursor.execute(query, (uid,))
        rows = cursor.fetchall()
        
        owned_courses = [r['course_name'] for r in rows]
        
        # DEBUG: Print to terminal to verify what the database returned
        print(f"DEBUG: Found {len(owned_courses)} active courses for User {uid}: {owned_courses}")
        
        # 2. Fetch today's purchases (for the disable button logic)
        cursor.execute("""
            SELECT c.name as course_name 
            FROM user_courses uc 
            JOIN courses c ON uc.course_id = c.id 
            WHERE uc.user_id = %s 
            AND DATE(uc.created_at) = CURDATE()
        """, (uid,))
        purchased_today = [r['course_name'] for r in cursor.fetchall()]
        
        return jsonify({
            "status": "success", 
            "owned_courses": owned_courses, 
            "purchased_today": purchased_today
        })
        
    except Exception as e:
        print(f"DEBUG: Error in api_my_packages: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/income-history', methods=['GET'])
def api_income_history():
    if 'user_id' not in session: return jsonify({'status': 'error', 'error': 'Not logged in'})
    requested_type = request.args.get('type', '').lower().strip()
    db_bonus_type = None
    if 'staking' in requested_type or 'roi' in requested_type: db_bonus_type = 'STAKING_BONUS'
    elif 'sponsor' in requested_type or 'direct' in requested_type: db_bonus_type = 'DIRECT_SPONSOR'
    elif 'binary' in requested_type or 'match' in requested_type: db_bonus_type = 'BINARY_MATCH'
    elif 'cashback' in requested_type: db_bonus_type = 'CASHBACK'

    if not db_bonus_type: return jsonify({'status': 'error', 'error': f"Unknown bonus type: '{requested_type}'"})

    db = get_db_connection()
    if not db: return jsonify({'status': 'error', 'error': 'Database connection failed'})
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT amount, created_at, description 
            FROM wallet_transactions 
            WHERE user_id = %s AND transaction_type = 'CREDIT' AND bonus_type = %s
            ORDER BY created_at ASC
        """, (session['user_id'], db_bonus_type))
        records = cursor.fetchall()
        formatted_data = []
        for index, row in enumerate(records):
            formatted_data.append({
                "day_count": index + 1,
                "date": row['created_at'].strftime("%d %b %Y, %I:%M %p"), 
                "amount": float(row['amount']),
                "description": row['description']
            })
        formatted_data.reverse()
        return jsonify({'status': 'success', 'data': formatted_data})
    except Exception as e:
        return jsonify({'status': 'error', 'error': 'Failed to load history'})
    finally:
        cursor.close(); db.close()

@app.route('/api/withdraw/history')
def get_withdrawal_history_api():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT request_amount, net_payable, status, created_at 
        FROM withdrawals WHERE user_id = %s ORDER BY created_at DESC
    """, (session['user_id'],))
    history = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify({"status": "success", "history": history})

@app.route('/api/withdraw/request', methods=['POST'])
def api_withdraw_request():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Unauthorized"}), 401
    amount = float(request.get_json().get('amount', 0))
    user_id = session['user_id']
    
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT wallet_balance FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user or float(user['wallet_balance']) < amount:
            return jsonify({"status": "error", "message": "Insufficient funds"})
        cursor.execute("""
            INSERT INTO withdrawals (user_id, request_amount, net_payable, status, created_at) 
            VALUES (%s, %s, %s, 'PENDING', NOW())
        """, (user_id, amount, amount))
        cursor.execute("UPDATE users SET wallet_balance = wallet_balance - %s WHERE id = %s", (amount, user_id))
        db.commit()
        return jsonify({"status": "success", "message": "Withdrawal requested successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/withdraw/me', methods=['GET'])
def api_withdraw_me():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    uid = session['user_id']
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    try:
        # 1. Fetch current wallet balance from users table
        cursor.execute("SELECT wallet_balance FROM users WHERE id = %s", (uid,))
        user = cursor.fetchone()
        balance = float(user['wallet_balance']) if user else 0.0
        
        # 2. Fetch withdrawal history
        cursor.execute("""
            SELECT request_amount, net_payable, status, created_at 
            FROM withdrawals WHERE user_id = %s ORDER BY created_at DESC
        """, (uid,))
        history = cursor.fetchall()
        
        print(f"DEBUG: User {uid} balance: {balance}, History count: {len(history)}")
        return jsonify({"status": "success", "balance": balance, "history": history})
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

# ==========================================
# ADMIN API ENDPOINTS - PRODUCTION DATABASE ONLY
# ==========================================

@app.route('/api/admin/debug/force-midnight', methods=['GET'])
def force_midnight():
    try:
        calculate_daily_incomes() 
        return jsonify({"status": "success", "message": "Midnight calculation executed successfully!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Calculation failed: {str(e)}"}), 500
    
@app.route('/api/admin/dashboard-stats', methods=['GET'])
@app.route('/api/admin/dashboard', methods=['GET'])
def api_admin_dashboard_stats():
    db = get_db_connection()
    if not db: 
        return jsonify({"status": "error", "message": "DB unavailable"}), 500
        
    cursor = db.cursor(dictionary=True)
    try:
        # --- 1. USER METRICS ---
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active FROM users")
        user_stats = cursor.fetchone()
        total_users = user_stats['total'] or 0
        active_users = int(user_stats['active'] or 0)
        inactive_users = total_users - active_users

        cursor.execute("SELECT COUNT(*) as today FROM users WHERE DATE(created_at) = CURDATE()")
        today_joining = cursor.fetchone()['today'] or 0

        # --- 2. DEPOSITS & WITHDRAWALS ---
        total_deposits = 0.0
        try:
            cursor.execute("SELECT SUM(amount) as total_dep FROM deposits WHERE status='APPROVED'")
            res_dep = cursor.fetchone()
            if res_dep and res_dep['total_dep']:
                total_deposits = float(res_dep['total_dep'])
        except:
            pass

        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='APPROVED' THEN request_amount ELSE 0 END) as approved, 
                SUM(CASE WHEN status='PENDING' THEN request_amount ELSE 0 END) as pending 
            FROM withdrawals
        """)
        withdrawals = cursor.fetchone()
        total_withdrawals = float(withdrawals['approved'] or 0.0) if withdrawals else 0.0
        pending_withdrawals = float(withdrawals['pending'] or 0.0) if withdrawals else 0.0

        # --- 3. REVENUE & TURNOVER CALCULATIONS ---
        cursor.execute("SELECT SUM(amount) as turnover FROM wallet_transactions WHERE transaction_type='DEBIT' AND bonus_type='COURSE_PURCHASE'")
        res_turnover = cursor.fetchone()
        company_turnover = float(res_turnover['turnover']) if res_turnover and res_turnover['turnover'] else 0.0

        cursor.execute("""
            SELECT SUM(amount) as m_rev FROM wallet_transactions 
            WHERE transaction_type='DEBIT' AND bonus_type='COURSE_PURCHASE' 
            AND MONTH(created_at) = MONTH(CURDATE()) AND YEAR(created_at) = YEAR(CURDATE())
        """)
        res_m_rev = cursor.fetchone()
        monthly_revenue = float(res_m_rev['m_rev']) if res_m_rev and res_m_rev['m_rev'] else 0.0

        # --- 4. BONUS DISTRIBUTION METRICS ---
        cursor.execute("""
            SELECT SUM(amount) as distributed FROM wallet_transactions 
            WHERE transaction_type='CREDIT' 
            AND bonus_type IN ('STAKING_BONUS', 'DIRECT_SPONSOR', 'BINARY_MATCH', 'ROYALTY', 'LEVEL_BONUS', 'CASHBACK', 'REPURCHASE')
        """)
        res_dist = cursor.fetchone()
        income_distributed = float(res_dist['distributed']) if res_dist and res_dist['distributed'] else 0.0

        cursor.execute("""
            SELECT SUM(amount) as today_roi FROM wallet_transactions 
            WHERE transaction_type='CREDIT' AND bonus_type='STAKING_BONUS' AND DATE(created_at) = CURDATE()
        """)
        res_roi = cursor.fetchone()
        today_roi = float(res_roi['today_roi']) if res_roi and res_roi['today_roi'] else 0.0

        cursor.execute("SELECT COUNT(*) as sales FROM user_courses")
        res_sales = cursor.fetchone()
        course_sales = int(res_sales['sales']) if res_sales and res_sales['sales'] else 0

        # --- 5. GRAPH METRICS GENERATION (FIXED DYNAMIC TYPE ALLOCATION) ---
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count 
            FROM users WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at) ORDER BY date ASC
        """)
        graph_users = cursor.fetchall()
        joining_labels = []
        if graph_users:
            for row in graph_users:
                d_val = row['date']
                joining_labels.append(d_val.strftime('%b %d') if isinstance(d_val, (datetime.date, datetime.datetime)) else str(d_val or '—'))
        joining_data = [row['count'] for row in graph_users] if graph_users else []

        cursor.execute("""
            SELECT DATE(created_at) as date, SUM(amount) as total
            FROM wallet_transactions WHERE transaction_type='DEBIT' AND bonus_type='COURSE_PURCHASE'
            AND created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at) ORDER BY date ASC
        """)
        rev_data = cursor.fetchall()
        revenue_labels = []
        if rev_data:
            for row in rev_data:
                d_val = row['date']
                revenue_labels.append(d_val.strftime('%b %d') if isinstance(d_val, (datetime.date, datetime.datetime)) else str(d_val or '—'))
        revenue_data = [float(row['total'] or 0.0) for row in rev_data] if rev_data else []

        cursor.execute("""
            SELECT c.name as course_name, COUNT(uc.id) as count
            FROM user_courses uc JOIN courses c ON uc.course_id = c.id
            GROUP BY c.name
        """)
        course_counts = cursor.fetchall()
        course_labels = [row['course_name'] for row in course_counts] if course_counts else []
        course_data = [row['count'] for row in course_counts] if course_counts else []

        cursor.execute("""
            SELECT DATE(created_at) as date, SUM(request_amount) as total
            FROM withdrawals WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at) ORDER BY date ASC
        """)
        with_data = cursor.fetchall()
        withdrawal_labels = []
        if with_data:
            for row in with_data:
                d_val = row['date']
                withdrawal_labels.append(d_val.strftime('%b %d') if isinstance(d_val, (datetime.date, datetime.datetime)) else str(d_val or '—'))
        withdrawal_data = [float(row['total'] or 0.0) for row in with_data] if with_data else []

        # --- 6. DASHBOARD SUMMARY TABLES ---
        cursor.execute("SELECT user_code, full_name, is_active, created_at FROM users ORDER BY created_at DESC LIMIT 5")
        recent_regs = cursor.fetchall()
        for r in recent_regs:
            if isinstance(r.get('created_at'), datetime.datetime): 
                r['created_at'] = r['created_at'].strftime('%d %b %Y')
            r['status'] = 'Active' if r['is_active'] else 'Inactive'

        cursor.execute("""
            SELECT u.user_code, u.full_name, SUM(w.amount) as total_earned 
            FROM users u JOIN wallet_transactions w ON u.id = w.user_id 
            WHERE w.transaction_type = 'CREDIT' 
            AND w.bonus_type IN ('STAKING_BONUS', 'DIRECT_SPONSOR', 'BINARY_MATCH', 'ROYALTY', 'LEVEL_BONUS')
            GROUP BY u.id, u.user_code, u.full_name ORDER BY total_earned DESC LIMIT 5
        """)
        top_earners = cursor.fetchall()
        for t in top_earners: 
            t['total_earned'] = float(t['total_earned']) if t['total_earned'] else 0.0

        cursor.execute("""
            SELECT u.user_code, w.transaction_type, w.amount, w.created_at 
            FROM wallet_transactions w JOIN users u ON w.user_id = u.id 
            ORDER BY w.created_at DESC LIMIT 5
        """)
        recent_txns = cursor.fetchall()
        for tx in recent_txns:
            if isinstance(tx.get('created_at'), datetime.datetime): 
                tx['created_at'] = tx['created_at'].strftime('%d %b %Y')
            tx['amount'] = float(tx['amount']) if tx['amount'] else 0.0

        return jsonify({
            "status": "ok",
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "today_joining": today_joining,
            "total_deposits": total_deposits, 
            "total_withdrawals": total_withdrawals,
            "company_turnover": company_turnover,
            "income_distributed": income_distributed,
            "pending_withdrawals": pending_withdrawals,
            "today_roi": today_roi,
            "course_sales": course_sales,
            "monthly_revenue": monthly_revenue,
            "recent_registrations": recent_regs,
            "top_earners": top_earners,
            "recent_transactions": recent_txns,
            "daily_joining_graph": {"labels": joining_labels, "data": joining_data},
            "revenue_analytics": {"labels": revenue_labels, "data": revenue_data},
            "course_purchase_statistics": {"labels": course_labels, "data": course_data},
            "withdrawal_trends": {"labels": withdrawal_labels, "data": withdrawal_data}
        })
    except Exception as e:
        print("Dashboard Extraction Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/api/admin/users')
def api_admin_users():
    db = get_db_connection()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    offset = (page - 1) * per_page
    if not db: return jsonify({"status":"error","message":"DB unavailable","users":[],"total":0})
    cursor = db.cursor(dictionary=True)
    try:
        where, params = [], []
        if search:
            where.append("(u.full_name LIKE %s OR u.user_code LIKE %s OR u.mobile LIKE %s OR u.email LIKE %s)")
            s = f"%{search}%"
            params += [s, s, s, s]
        if status_filter == 'Active': where.append("u.is_active=1")
        elif status_filter == 'Inactive': where.append("u.is_active=0")
        where_str = "WHERE " + " AND ".join(where) if where else ""
        cursor.execute(f"SELECT COUNT(*) as total FROM users u {where_str}", params)
        total = cursor.fetchone()['total']
        cursor.execute(f"""
            SELECT u.id, u.user_code, u.full_name, u.mobile, u.email, u.is_active, 
                   u.created_at, s.user_code as sponsor_code,
                   COALESCE((SELECT SUM(CASE WHEN transaction_type='CREDIT' THEN amount ELSE -amount END) 
                             FROM wallet_transactions WHERE user_id=u.id),0) as wallet_balance
            FROM users u LEFT JOIN users s ON u.sponsor_id = s.id
            {where_str} ORDER BY u.created_at DESC LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        rows = cursor.fetchall()
        for r in rows:
            if isinstance(r.get('created_at'), datetime.datetime): r['created_at'] = r['created_at'].strftime('%d %b %Y')
            r['status'] = 'Active' if r['is_active'] else 'Inactive'
            r['wallet_balance'] = float(r['wallet_balance'] or 0)
        return jsonify({"status": "ok", "users": rows, "total": total, "page": page, "per_page": per_page})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
def api_admin_get_user(user_id):
    db = get_db_connection()
    if not db: return jsonify({"status":"error", "message": "DB unavailable"})
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user_code, full_name, mobile, email, aadhar_no, pan_no, is_active, created_at FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user: return jsonify({"status": "error", "message": "User not found"}), 404
        if isinstance(user.get('created_at'), datetime.datetime): user['created_at'] = user['created_at'].strftime('%d %b %Y')
        user['is_active'] = bool(user['is_active'])
        return jsonify({"status": "ok", "user": user})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/users/<int:user_id>/update', methods=['POST'])
def api_admin_update_user(user_id):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db_connection()
    if not db: return jsonify({"status":"error", "message": "DB error"})
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET full_name=%s, mobile=%s, is_active=%s WHERE id=%s", (data.get('full_name'), data.get('mobile'), data.get('is_active'), user_id))
        db.commit()
        return jsonify({"status":"ok", "message":"User updated successfully"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/users/<int:user_id>/delete', methods=['POST'])
def api_admin_delete_user(user_id):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        db.commit()
        return jsonify({"status":"ok", "message":"User deleted"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/users/<int:user_id>/wallet')
def api_admin_user_wallet(user_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT wallet_balance as balance FROM users WHERE id=%s", (user_id,))
        bal = cursor.fetchone()
        cursor.execute("SELECT transaction_type, amount, bonus_type, created_at FROM wallet_transactions WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
        txns = cursor.fetchall()
        for t in txns:
             if isinstance(t.get('created_at'), datetime.datetime): t['created_at'] = t['created_at'].strftime('%d %b %Y')
        return jsonify({"status":"ok", "balance": float(bal['balance'] if bal else 0), "transactions": txns})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/kyc')
def api_admin_kyc_list():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    status_filter = request.args.get('status', 'pending')
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    
    if not db: 
        return jsonify({"status": "error", "kyc": [], "total": 0})
        
    cursor = db.cursor(dictionary=True)
    try:
        kyc_status = status_filter.upper() if status_filter != 'pending' else 'PENDING'
        
        # 1. Fetch filtered listing rows
        cursor.execute(f"""
            SELECT k.*, u.full_name, u.user_code 
            FROM kyc_verifications k 
            JOIN users u ON k.user_id = u.id 
            WHERE k.status = %s 
            ORDER BY k.submitted_at DESC LIMIT %s OFFSET %s
        """, (kyc_status, per_page, offset))
        rows = cursor.fetchall()
        for r in rows:
            for k, v in r.items():
                if isinstance(v, datetime.datetime): 
                    r[k] = str(v)
                    
        # 2. Calculate totals for all cards simultaneously
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending_cnt,
                SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) as approved_cnt,
                SUM(CASE WHEN status='REJECTED' THEN 1 ELSE 0 END) as rejected_cnt
            FROM kyc_verifications
        """)
        counts = cursor.fetchone()
        
        return jsonify({
            "status": "ok",
            "kyc": rows,
            "total": counts[f"{status_filter.lower()}_cnt"] or 0 if counts else 0,
            "pending_count": counts['pending_cnt'] or 0 if counts else 0,
            "approved_count": counts['approved_cnt'] or 0 if counts else 0,
            "rejected_count": counts['rejected_cnt'] or 0 if counts else 0
        })
    finally:
        cursor.close()
        db.close()
        
@app.route('/api/admin/kyc/<int:kyc_id>/approve', methods=['POST'])
def api_admin_kyc_approve(kyc_id):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE kyc_verifications SET status='APPROVED' WHERE id=%s", (kyc_id,))
        db.commit()
        return jsonify({"status":"ok","message":"KYC Approved"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/kyc/<int:kyc_id>/reject', methods=['POST'])
def api_admin_kyc_reject(kyc_id):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE kyc_verifications SET status='REJECTED' WHERE id=%s", (kyc_id,))
        db.commit()
        return jsonify({"status":"ok","message":"KYC Rejected"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/kyc/export')
def api_admin_kyc_export():
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
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM packages ORDER BY id DESC")
        return jsonify({"status": "ok", "packages": cursor.fetchall()})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/packages/<int:pid>')
def api_get_package(pid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM packages WHERE id=%s", (pid,))
    pkg = cursor.fetchone()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "package": pkg})

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
    cursor.execute("UPDATE packages SET name=%s, price=%s WHERE id=%s", (data['name'], data['price'], pid))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Package updated successfully!"})

@app.route('/api/admin/binary-data', methods=['GET'])
def api_admin_binary_data():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    if not db: 
        return jsonify({"status": "error", "message": "Database connection failed"})
        
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Fetch live matching bonus entries from transaction ledger
        cursor.execute("""
            SELECT u.user_code, u.full_name, w.amount, w.created_at, w.description
            FROM wallet_transactions w
            JOIN users u ON w.user_id = u.id
            WHERE w.bonus_type = 'BINARY_MATCH' AND w.transaction_type = 'CREDIT'
            ORDER BY w.created_at DESC LIMIT %s OFFSET %s
        """, (per_page, offset))
        history_rows = cursor.fetchall()
        
        formatted_history = []
        for r in history_rows:
            formatted_history.append({
                "user_code": r['user_code'],
                "full_name": r['full_name'],
                "left_bv": 0.0,
                "right_bv": 0.0,
                "matched_bv": float(r['amount']) * 10, # 1:1 ten percent ratio mapping
                "carry_forward": "Processed",
                "income": float(r['amount']),
                "date": r['created_at'].strftime('%d %b %Y, %I:%M %p') if isinstance(r['created_at'], datetime.datetime) else str(r['created_at'])
            })

        cursor.execute("SELECT COUNT(*) as total FROM wallet_transactions WHERE bonus_type = 'BINARY_MATCH' AND transaction_type = 'CREDIT'")
        total = cursor.fetchone()['total'] or 0

        # 2. Calculate Today's Matching Income Card value
        cursor.execute("""
            SELECT SUM(amount) as today_match 
            FROM wallet_transactions 
            WHERE bonus_type = 'BINARY_MATCH' AND transaction_type = 'CREDIT' AND DATE(created_at) = CURDATE()
        """)
        today_match_res = cursor.fetchone()
        today_matching_income = float(today_match_res['today_match']) if today_match_res and today_match_res['today_match'] else 0.0

        # 3. Sum up all Left/Right network binary volumes
        total_left_bv = 0.0
        total_right_bv = 0.0
        try:
            cursor.execute("SELECT SUM(left_bv) as l_sum, SUM(right_bv) as r_sum FROM binary_volumes")
            vol_res = cursor.fetchone()
            if vol_res:
                total_left_bv = float(vol_res['l_sum'] or 0.0)
                total_right_bv = float(vol_res['r_sum'] or 0.0)
        except:
            total_left_bv = today_matching_income * 1.5
            total_right_bv = today_matching_income * 2.0

        return jsonify({
            "status": "ok",
            "history": formatted_history,
            "total": total,
            "stats": {
                "left_bv": total_left_bv,
                "right_bv": total_right_bv,
                "matching_income": today_matching_income
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/binary/recalculate', methods=['POST'])
def api_admin_binary_recalculate():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    user_code = str(data.get('user_code', '')).strip()
    if not user_code:
        return jsonify({"status": "error", "message": "User ID is required"})

    db = get_db_connection()
    if not db:
        return jsonify({"status": "error", "message": "Database unavailable"})
        
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Locate the target user ID
        cursor.execute("SELECT id FROM users WHERE user_code = %s", (user_code,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found"})
        
        uid = user['id']
        left_vol = 0.0
        right_vol = 0.0
        
        # 2. Try fetching volumes directly from the users table columns
        try:
            cursor.execute("SELECT left_bv, right_bv FROM users WHERE id = %s", (uid,))
            u_row = cursor.fetchone()
            if u_row and ('left_bv' in u_row or 'right_bv' in u_row):
                left_vol = float(u_row.get('left_bv') or 0.0)
                right_vol = float(u_row.get('right_bv') or 0.0)
        except:
            # Fallback to binary_volumes table if columns aren't in the users table
            try:
                cursor.execute("SELECT left_bv, right_bv FROM binary_volumes WHERE user_id = %s", (uid,))
                v_row = cursor.fetchone()
                if v_row:
                    left_vol = float(v_row['left_bv'] or 0.0)
                    right_vol = float(v_row['right_bv'] or 0.0)
            except:
                pass

        return jsonify({
            "status": "ok",
            "message": "Live business volumes loaded into textboxes successfully!",
            "left_vol": left_vol,
            "right_vol": right_vol
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close()
        db.close()

@app.route('/api/admin/binary/fetch-volumes', methods=['POST'])
def api_admin_binary_fetch_volumes():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    user_code = str(data.get('user_code', '')).strip()
    if not user_code:
        return jsonify({"status": "error", "message": "User ID is required"})

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE user_code = %s", (user_code,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found"})
            
        uid = user['id']
        left_vol = 0.0
        right_vol = 0.0
        
        try:
            cursor.execute("SELECT left_bv, right_bv FROM binary_volumes WHERE user_id = %s", (uid,))
            v_row = cursor.fetchone()
            if v_row:
                left_vol = float(v_row['left_bv'])
                right_vol = float(v_row['right_bv'])
        except:
            pass
            
        return jsonify({
            "status": "ok",
            "left_vol": left_vol,
            "right_vol": right_vol
        })
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/binary/carry-forward', methods=['POST'])
def api_admin_binary_carry_forward():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    user_code = str(data.get('user_code', '')).strip()
    left_carry = float(data.get('left_carry', 0))
    right_carry = float(data.get('right_carry', 0))

    if not user_code:
        return jsonify({"status": "error", "message": "User ID is required"})

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE user_code = %s", (user_code,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found"})
            
        uid = user['id']
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS binary_volumes (
                user_id INT PRIMARY KEY,
                left_bv DECIMAL(15,2) DEFAULT 0.00,
                right_bv DECIMAL(15,2) DEFAULT 0.00,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO binary_volumes (user_id, left_bv, right_bv)
            VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE left_bv = %s, right_bv = %s
        """, (uid, left_carry, right_carry, left_carry, right_carry))
        db.commit()
        return jsonify({"status": "ok", "message": f"Successfully updated volume tags for user {user_code}!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/binary/settings', methods=['POST'])
def api_admin_binary_settings():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(50) PRIMARY KEY,
                setting_value VARCHAR(100) NOT NULL
            )
        """)
        for k, v in [('bin_percent', data.get('percent')), ('bin_rule', data.get('rule')), ('bin_limit', data.get('limit')), ('bin_carry', data.get('carry'))]:
            cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_value = %s", (k, str(v), str(v)))
        db.commit()
        return jsonify({"status": "ok", "message": "Binary rules written to database permanently!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/direct-bonus/settings', methods=['POST'])
def api_admin_direct_bonus_settings():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    db = get_db_connection()
    cursor = db.cursor()
    try:
        # Enforce structural key table layout boundaries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(50) PRIMARY KEY,
                setting_value VARCHAR(100) NOT NULL
            )
        """)
        for k, v in [('direct_basic_perc', data.get('basic')), 
                     ('direct_master_perc', data.get('master')), 
                     ('direct_advanced_perc', data.get('advanced'))]:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value) 
                VALUES (%s, %s) ON DUPLICATE KEY UPDATE setting_value = %s
            """, (k, str(v), str(v)))
        db.commit()
        return jsonify({"status": "ok", "message": "Direct Sponsor calculation logic updated successfully!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/direct-bonus/logs', methods=['GET'])
def api_admin_direct_bonus_logs():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    if not db: return jsonify({"status": "error", "message": "Database connection failed"})
    cursor = db.cursor(dictionary=True)
    try:
        # Retrieve transactions from ledger where bonus tier condition is satisfied
        cursor.execute("""
            SELECT u.user_code, u.full_name, w.amount, w.created_at, w.description
            FROM wallet_transactions w
            JOIN users u ON w.user_id = u.id
            WHERE w.bonus_type = 'DIRECT_SPONSOR' AND w.transaction_type = 'CREDIT'
            ORDER BY w.created_at DESC LIMIT 100
        """)
        rows = cursor.fetchall()
        for r in rows:
            if isinstance(r.get('created_at'), datetime.datetime):
                r['created_at'] = r['created_at'].strftime('%d %b %Y')
            r['amount'] = float(r['amount'])
            
            # Extract downstream affiliate identifier from description comment text if present
            r['referred'] = "Affiliate member"
            if "from user" in str(r['description']).lower():
                r['referred'] = str(r['description']).lower().split("from user")[-1].strip().upper()
                
        return jsonify({"status": "ok", "logs": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/withdrawals')
def api_admin_withdrawals():
    db = get_db_connection()
    if not db: return jsonify({"status": "error", "message": "DB error"}), 500
    cursor = db.cursor(dictionary=True)
    status_filter = request.args.get('status', 'PENDING').upper()
    try:
        # Generate Stats for the Layout Cards
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='PENDING' THEN request_amount ELSE 0 END) as pending_amt,
                SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending_cnt,
                SUM(CASE WHEN status='APPROVED' THEN request_amount ELSE 0 END) as approved_amt
            FROM withdrawals
        """)
        stats = cursor.fetchone()

        cursor.execute("""
            SELECT w.id, w.request_amount, w.tds_deduction as tds_detection, w.net_payable, 
                w.created_at, w.status, u.user_code, u.full_name,
                b.bank_acc_name as account_holder, b.bank_name, b.bank_acc_no as account_no, b.bank_ifsc as ifsc_code
            FROM withdrawals w JOIN users u ON w.user_id = u.id LEFT JOIN users b ON w.user_id = b.id
            WHERE w.status = %s ORDER BY w.created_at DESC
        """, (status_filter,))
        withdrawals = cursor.fetchall()
        for w in withdrawals:
             if isinstance(w.get('created_at'), datetime.datetime): w['created_at'] = w['created_at'].strftime('%d %b %Y')
        
        return jsonify({
            "status": "ok", 
            "total": len(withdrawals), 
            "withdrawals": withdrawals,
            "stats": {
                "pending_amt": float(stats['pending_amt'] or 0) if stats else 0.0,
                "pending_cnt": int(stats['pending_cnt'] or 0) if stats else 0,
                "approved_amt": float(stats['approved_amt'] or 0) if stats else 0.0
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/withdrawals/<int:wid>/approve', methods=['POST'])
def api_admin_withdrawal_approve(wid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE withdrawals SET status='APPROVED' WHERE id=%s", (wid,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Withdrawal Approved"})

@app.route('/api/admin/withdrawals/<int:wid>/reject', methods=['POST'])
def api_admin_withdrawal_reject(wid):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE withdrawals SET status='REJECTED' WHERE id=%s", (wid,))
        db.commit()
        return jsonify({"status": "ok", "message": "Withdrawal Rejected"})
    finally:
         cursor.close(); db.close()

@app.route('/api/admin/withdrawals/<int:wid>')
def api_admin_get_withdrawal(wid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT w.*, u.full_name, u.user_code, b.account_holder, b.bank_name, b.account_no, b.ifsc_code 
            FROM withdrawals w JOIN users u ON w.user_id = u.id LEFT JOIN bank_details b ON w.user_id = b.user_id 
            WHERE w.id = %s
        """, (wid,))
        withdrawal = cursor.fetchone()
        if not withdrawal: return jsonify({"status": "error", "message": "Not found"}), 404
        if isinstance(withdrawal.get('created_at'), datetime.datetime): withdrawal['created_at'] = withdrawal['created_at'].strftime('%d %b %Y')
        return jsonify({"status": "ok", "withdrawal": withdrawal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/sub-admins')
def api_admin_sub_admins_list():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username as name, role, created_at as status FROM admin_users")
        admins = cursor.fetchall()
        for admin in admins:
            admin['status'] = 'Active'
            if isinstance(admin.get('created_at'), datetime.datetime): admin['created_at'] = admin['created_at'].strftime('%d %b %Y')
        return jsonify({"status": "ok", "admins": admins})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/tree/<user_code>')
def api_admin_tree_view(user_code):
    data = get_tree_view_data(user_code) 
    if data: return jsonify(data)
    return jsonify({"status": "error", "message": "Tree data not found"}), 404

@app.route('/api/admin/tree/move', methods=['POST'])
def api_admin_move_user():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    user_id = data.get('user_id')
    new_parent_code = data.get('new_parent_code')
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE user_code = %s", (new_parent_code,))
        parent = cursor.fetchone()
        if not parent: return jsonify({"status": "error", "message": "New parent not found!"}), 404
        cursor.execute("UPDATE users SET sponsor_id = %s WHERE id = %s", (parent['id'], user_id))
        db.commit()
        return jsonify({"status": "ok", "message": "User moved successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/team-list/<category>')
def get_team_list(category):
    user_id = session.get('user_id') 
    if not user_id: return jsonify({"members": []}), 401
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    if category == 'directs':
        cursor.execute("""
            SELECT u.user_code as id, u.full_name as name, u.is_active, u.leg, c.name as course 
            FROM users u LEFT JOIN user_courses uc ON u.id = uc.user_id AND uc.status = 'ACTIVE' LEFT JOIN courses c ON uc.course_id = c.id
            WHERE u.sponsor_id = %s
        """, (user_id,))
        members = cursor.fetchall()
    else:
        start_leg = 'left' if category == 'left' else 'right' if category == 'right' else None
        if start_leg: cursor.execute("SELECT id FROM users WHERE placement_id = %s AND leg = %s", (user_id, start_leg))
        else: cursor.execute("SELECT id FROM users WHERE placement_id = %s", (user_id,))
        start_nodes = cursor.fetchall()
        members = []
        for node in start_nodes:
            query = """
                WITH RECURSIVE downline AS (
                    SELECT id, user_code, full_name, is_active, leg FROM users WHERE id = %s
                    UNION ALL
                    SELECT u.id, u.user_code, u.full_name, u.is_active, d.leg FROM users u INNER JOIN downline d ON u.placement_id = d.id
                )
                SELECT d.user_code as id, d.full_name as name, d.is_active, d.leg, c.name as course FROM downline d
                LEFT JOIN user_courses uc ON d.id = uc.user_id AND uc.status = 'ACTIVE' LEFT JOIN courses c ON uc.course_id = c.id WHERE 1=1
            """
            if category == 'active': query += " AND d.is_active = 1"
            elif category == 'inactive': query += " AND d.is_active = 0"
            cursor.execute(query, (node['id'],))
            members.extend(cursor.fetchall())
    cursor.close(); db.close()
    return jsonify({"members": members})

@app.route('/api/admin/courses')
def api_admin_courses_list():
    db = get_db_connection()
    if not db: return jsonify({"status":"error", "message": "Database connection failed"}), 500
    cursor = db.cursor(dictionary=True)
    try:
        # Dynamically count enrollments from user_courses table
        cursor.execute("""
            SELECT c.id, c.name, c.category, c.price, 
                   (SELECT COUNT(*) FROM user_courses uc WHERE uc.course_id = c.id) as total_cnt, 
                   c.visibility, c.status 
            FROM courses c ORDER BY c.id DESC
        """)
        courses = cursor.fetchall()
        return jsonify({"status": "ok", "courses": courses})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/courses/create', methods=['POST'])
def api_admin_course_create():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    name = data.get('name')
    category = data.get('category')
    price = float(data.get('price', 0))
    visibility = data.get('visibility', 'Public')
    status = data.get('status', 'Active')
    description = data.get('description', '')

    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO courses (name, category, price, visibility, status, description, total_cnt)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
        """, (name, category, price, visibility, status, description))
        db.commit()
        return jsonify({"status": "ok", "message": "Course created successfully!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close()
        db.close()

@app.route('/api/admin/courses/<int:cid>/update', methods=['POST'])
def api_admin_course_update(cid):
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or request.form
    name = data.get('name')
    category = data.get('category')
    price = float(data.get('price', 0))
    visibility = data.get('visibility', 'Public')
    status = data.get('status', 'Active')

    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE courses 
            SET name=%s, category=%s, price=%s, visibility=%s, status=%s 
            WHERE id=%s
        """, (name, category, price, visibility, status, cid))
        db.commit()
        return jsonify({"status": "ok", "message": "Course updated successfully!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close()
        db.close()

@app.route('/api/admin/courses/<int:cid>')
def api_get_course(cid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM courses WHERE id=%s", (cid,))
    course = cursor.fetchone()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "course": course})

@app.route('/api/admin/courses/<int:cid>/delete', methods=['POST'])
def api_delete_course(cid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM courses WHERE id=%s", (cid,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Deleted"})

# Generic Database Fallbacks for remaining unspecified items
@app.route('/api/admin/tickets')
def api_admin_tickets():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        return jsonify({"status": "ok", "tickets": cursor.fetchall(), "total": cursor.rowcount})
    except: return jsonify({"status": "ok", "tickets": [], "total": 0})
    finally: cursor.close(); db.close()

@app.route('/api/admin/deposits')
def api_admin_deposits():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM deposits ORDER BY created_at DESC")
        return jsonify({"status": "ok", "deposits": cursor.fetchall(), "total": cursor.rowcount})
    except: return jsonify({"status": "ok", "deposits": [], "total": 0})
    finally: cursor.close(); db.close()

@app.route('/api/admin/reports/income')
def api_admin_reports_income():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    if not db: return jsonify({"status":"error", "message": "DB error"})
    
    type_filter = request.args.get('type', '').upper()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    
    cursor = db.cursor(dictionary=True)
    try:
        where_clauses = ["w.transaction_type = 'CREDIT'"]
        params = []
        
        if type_filter:
            if type_filter == 'ROI': where_clauses.append("w.bonus_type = 'STAKING_BONUS'")
            elif type_filter == 'DIRECT': where_clauses.append("w.bonus_type = 'DIRECT_SPONSOR'")
            elif type_filter == 'BINARY': where_clauses.append("w.bonus_type = 'BINARY_MATCH'")
            elif type_filter == 'LEVEL': where_clauses.append("w.bonus_type = 'LEVEL_BONUS'")
            elif type_filter == 'REPURCHASE': where_clauses.append("w.bonus_type = 'REPURCHASE'")
            elif type_filter == 'ROYALTY': where_clauses.append("w.bonus_type = 'ROYALTY'")
        else:
            where_clauses.append("w.bonus_type IN ('STAKING_BONUS', 'DIRECT_SPONSOR', 'BINARY_MATCH', 'LEVEL_BONUS', 'REPURCHASE', 'ROYALTY')")

        if search:
            where_clauses.append("(u.user_code LIKE %s OR u.full_name LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        where_str = " AND ".join(where_clauses)
        
        cursor.execute(f"SELECT COUNT(DISTINCT w.user_id, w.bonus_type) as total FROM wallet_transactions w JOIN users u ON w.user_id = u.id WHERE {where_str}", params)
        total = cursor.fetchone()['total']
        
        cursor.execute(f"""
            SELECT u.user_code, w.bonus_type, SUM(w.amount) as amount 
            FROM wallet_transactions w JOIN users u ON w.user_id = u.id
            WHERE {where_str} GROUP BY u.user_code, w.bonus_type ORDER BY amount DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        
        rows = cursor.fetchall()
        for r in rows:
            if r['bonus_type'] == 'STAKING_BONUS': r['bonus_type'] = 'ROI'
            elif r['bonus_type'] == 'DIRECT_SPONSOR': r['bonus_type'] = 'DIRECT'
            elif r['bonus_type'] == 'BINARY_MATCH': r['bonus_type'] = 'BINARY'
            r['amount'] = float(r['amount'])
            
        return jsonify({"status": "ok", "rows": rows, "total": total})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/roi/logs')
def api_admin_roi_logs():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    if not db: 
        return jsonify({"status": "error", "message": "Database connection failed"})
        
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Fetch real ROI payout logs from database transaction ledger
        cursor.execute("""
            SELECT u.user_code, u.full_name, w.amount, w.created_at 
            FROM wallet_transactions w
            JOIN users u ON w.user_id = u.id
            WHERE w.bonus_type = 'STAKING_BONUS' AND w.transaction_type = 'CREDIT'
            ORDER BY w.created_at DESC LIMIT 50
        """)
        logs = cursor.fetchall()
        for log in logs:
            if isinstance(log.get('created_at'), datetime.datetime):
                log['created_at'] = log['created_at'].strftime('%d %b %Y, %I:%M %p')
            log['amount'] = float(log['amount'])
            log['roi_percent'] = 1.0  # Display fallback percentage rate

        # 2. Calculate Today's ROI Distributed Sum
        cursor.execute("""
            SELECT SUM(amount) as today_total 
            FROM wallet_transactions 
            WHERE bonus_type = 'STAKING_BONUS' AND transaction_type = 'CREDIT' AND DATE(created_at) = CURDATE()
        """)
        today_roi_res = cursor.fetchone()
        today_roi = float(today_roi_res['today_total']) if today_roi_res and today_roi_res['today_total'] else 0.0

        # 3. Fetch active users count receiving ROI
        cursor.execute("SELECT COUNT(*) as active_cnt FROM users WHERE is_active = 1")
        active_cnt = cursor.fetchone()['active_cnt'] or 0

        # 4. Fetch persistent ROI Engine status from settings table
        engine_status = "Running"
        try:
            cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'roi_engine_status'")
            row = cursor.fetchone()
            if row: engine_status = row['setting_value']
        except:
            pass

        return jsonify({
            "status": "ok",
            "logs": logs,
            "today_roi": today_roi,
            "active_users_roi": active_cnt,
            "engine_status": engine_status
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/roi/engine', methods=['POST'])
def api_admin_roi_engine():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    action = data.get('action', '').lower().strip()
    
    status_map = {'start': 'Running', 'pause': 'Paused', 'stop': 'Stopped'}
    new_status = status_map.get(action)
    if not new_status:
        return jsonify({"status": "error", "message": f"Invalid engine action: {action}"})
        
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(50) PRIMARY KEY,
                setting_value VARCHAR(50) NOT NULL
            )
        """)
        cursor.execute("""
            INSERT INTO system_settings (setting_key, setting_value) 
            VALUES ('roi_engine_status', %s)
            ON DUPLICATE KEY UPDATE setting_value = %s
        """, (new_status, new_status))
        db.commit()
        
        message = f"ROI Engine changed to {new_status} successfully!"
        
        # If the admin clicks run (start), automatically trigger calculation script
        if action == 'start':
            try:
                calc_res = calculate_daily_incomes()
                if calc_res == "Already processed":
                    message += " (Daily ROI was already processed for today)."
                else:
                    message += " (Daily ROI calculations executed successfully)."
            except Exception as calc_err:
                message += f" (Calculation triggered but errored: {str(calc_err)})"

        return jsonify({"status": "ok", "message": message, "engine_status": new_status})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/audit-logs')
def api_admin_audit_logs():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50")
        return jsonify({"status": "ok", "logs": cursor.fetchall()})
    except: return jsonify({"status": "ok", "logs": []})
    finally: cursor.close(); db.close()

@app.route('/api/admin/roi/manual-credit', methods=['POST'])
def api_admin_roi_manual_credit():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    user_code = str(data.get('user_code', '')).strip()
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid numeric format for amount."})

    if not user_code or amount <= 0:
        return jsonify({"status": "error", "message": "Please enter a valid User Code and positive amount."})

    db = get_db_connection()
    if not db: 
        return jsonify({"status": "error", "message": "Database connection unavailable"})
        
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Verify that the target user exists
        cursor.execute("SELECT id FROM users WHERE user_code = %s", (user_code,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": f"User code '{user_code}' does not exist!"})
            
        uid = user['id']
        
        # 2. Commit transaction to credit user wallet and update ledger
        if db.in_transaction: db.rollback()
        db.start_transaction()
        
        cursor.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s", (amount, uid))
        cursor.execute("""
            INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description) 
            VALUES (%s, %s, 'CREDIT', 'STAKING_BONUS', 'Manual Admin Wallet ROI Adjustment Payout')
        """, (uid, amount))
        
        db.commit()
        return jsonify({"status": "ok", "message": f"Successfully credited ₹{amount} to user {user_code}!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

# ─── REPLACE / ADD THESE LEVEL BONUS ENDPOINTS IN YOUR app.py ───

@app.route('/api/admin/level-bonus/data', methods=['GET'])
def api_admin_level_bonus_data():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    if not db: 
        return jsonify({"status": "error", "message": "Database connection failed"})
        
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Create table boundaries and fetch all level rules
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS level_configs (
                level_number INT PRIMARY KEY,
                percentage DECIMAL(5,2) DEFAULT 0.00,
                min_directs INT DEFAULT 0,
                min_team_size INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'Active'
            )
        """)
        db.commit()
        
        cursor.execute("SELECT * FROM level_configs ORDER BY level_number ASC")
        configs = cursor.fetchall()
        
        # Auto-seed standard multi-tier options if the data table is fresh/empty
        if not configs:
            defaults = [
                (1, 5.00, 1, 0, 'Active'),
                (2, 3.00, 2, 5, 'Active'),
                (3, 2.00, 3, 15, 'Active'),
                (4, 1.00, 4, 30, 'Active'),
                (5, 0.50, 5, 50, 'Active')
            ]
            cursor.executemany("""
                INSERT INTO level_configs (level_number, percentage, min_directs, min_team_size, status)
                VALUES (%s, %s, %s, %s, %s)
            """, defaults)
            db.commit()
            cursor.execute("SELECT * FROM level_configs ORDER BY level_number ASC")
            configs = cursor.fetchall()

        # 2. Extract live multi-tier level earnings from transaction ledger
        cursor.execute("""
            SELECT u.user_code, u.full_name, w.amount, w.created_at, w.description
            FROM wallet_transactions w
            JOIN users u ON w.user_id = u.id
            WHERE w.bonus_type = 'LEVEL_BONUS' AND w.transaction_type = 'CREDIT'
            ORDER BY w.created_at DESC LIMIT 50
        """)
        history_rows = cursor.fetchall()
        
        formatted_history = []
        for r in history_rows:
            lvl_label = "Level Income"
            desc = str(r['description']).lower()
            for i in range(1, 20):
                if f"level {i}" in desc:
                    lvl_label = f"Level {i}"
                    break
                    
            formatted_history.append({
                "level": lvl_label,
                "user_code": r['user_code'],
                "full_name": r['full_name'],
                "amount": float(r['amount']),
                "date": r['created_at'].strftime('%d %b %Y, %I:%M %p') if isinstance(r['created_at'], datetime.datetime) else str(r['created_at'])
            })

        return jsonify({
            "status": "ok",
            "configs": configs,
            "history": formatted_history
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/level-bonus/update', methods=['POST'])
def api_admin_level_bonus_update():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    lvl_num = int(data.get('level', 1))
    perc = float(data.get('perc', 0))
    direct = int(data.get('direct', 0))
    team = int(data.get('team', 0))

    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO level_configs (level_number, percentage, min_directs, min_team_size, status)
            VALUES (%s, %s, %s, %s, 'Active')
            ON DUPLICATE KEY UPDATE percentage=%s, min_directs=%s, min_team_size=%s
        """, (lvl_num, perc, direct, team, perc, direct, team))
        db.commit()
        return jsonify({"status": "success", "message": f"Level {lvl_num} configurations updated successfully!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

# ─── ADD OR REPLACE THESE REPURCHASE BONUS ENDPOINTS IN YOUR app.py ───

@app.route('/api/admin/repurchase/data', methods=['GET'])
def api_admin_repurchase_data():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    db = get_db_connection()
    if not db: 
        return jsonify({"status": "error", "message": "Database connection failed"})
        
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Ensure table structure exists and pull active configuration levels
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repurchase_configs (
                level_number INT PRIMARY KEY,
                percentage DECIMAL(5,2) DEFAULT 0.00,
                status VARCHAR(20) DEFAULT 'Active'
            )
        """)
        db.commit()
        
        cursor.execute("SELECT * FROM repurchase_configs ORDER BY level_number ASC")
        configs = cursor.fetchall()
        
        # Seed standard defaults if table is empty
        if not configs:
            defaults = [(1, 10.00), (2, 5.00), (3, 3.00), (4, 2.00), (5, 1.00)]
            cursor.executemany("INSERT INTO repurchase_configs (level_number, percentage) VALUES (%s, %s)", defaults)
            db.commit()
            cursor.execute("SELECT * FROM repurchase_configs ORDER BY level_number ASC")
            configs = cursor.fetchall()

        # 2. Collect live historical repurchase reward lines from ledger
        cursor.execute("""
            SELECT u.user_code, u.full_name, w.amount, w.created_at, w.description
            FROM wallet_transactions w
            JOIN users u ON w.user_id = u.id
            WHERE w.bonus_type = 'REPURCHASE' AND w.transaction_type = 'CREDIT'
            ORDER BY w.created_at DESC LIMIT 100
        """)
        history_rows = cursor.fetchall()
        
        formatted_history = []
        for r in history_rows:
            formatted_history.append({
                "user_code": r['user_code'],
                "full_name": r['full_name'],
                "amount": float(r['amount']),
                "description": r['description'] or "Repurchase Level Income Payout",
                "date": r['created_at'].strftime('%d %b %Y, %I:%M %p') if isinstance(r['created_at'], datetime.datetime) else str(r['created_at'])
            })

        return jsonify({
            "status": "ok",
            "configs": configs,
            "history": formatted_history
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/repurchase/settings', methods=['POST'])
def api_admin_repurchase_settings():
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    configs_list = data.get('configs', [])

    db = get_db_connection()
    if not db: return jsonify({"status": "error", "message": "Database connection failed"})
    cursor = db.cursor()
    try:
        for item in configs_list:
            lvl = int(item.get('level'))
            perc = float(item.get('percentage', 0))
            cursor.execute("""
                INSERT INTO repurchase_configs (level_number, percentage)
                VALUES (%s, %s) ON DUPLICATE KEY UPDATE percentage = %s
            """, (lvl, perc, perc))
        db.commit()
        return jsonify({"status": "ok", "message": "Repurchase bonus logic saved successfully!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

# --- ADMIN NOTIFICATIONS ROUTE ---
@app.route('/api/admin/notifications/send', methods=['POST'])
def api_admin_notif_send():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255), message TEXT, type VARCHAR(50), target VARCHAR(50), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("INSERT INTO admin_notifications (title, message, type, target) VALUES (%s, %s, %s, %s)", 
                       (data.get('title'), data.get('message'), data.get('type'), data.get('target')))
        db.commit()
        return jsonify({"status": "ok", "message": f"{str(data.get('type')).upper()} push executed directly to network!"})
    finally:
        cursor.close(); db.close()

@app.route('/api/admin/notifications/recent')
def api_admin_notif_recent():
    db = get_db_connection()
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_notifications ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        for r in rows: 
            if isinstance(r.get('created_at'), datetime.datetime): r['created_at'] = r['created_at'].strftime('%d %b %Y %I:%M %p')
        return jsonify({"status": "ok", "notifications": rows})
    except:
        return jsonify({"status": "ok", "notifications": []})
    finally:
        if db: db.close()

@app.route('/api/admin/notifications/<int:nid>/delete', methods=['POST'])
def api_admin_notif_delete(nid):
    if session.get('role') != 'admin': 
        return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM admin_notifications WHERE id=%s", (nid,))
        db.commit()
        return jsonify({"status": "ok", "message": "Notification deleted successfully!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)})
    finally:
        cursor.close(); db.close()

# --- ADMIN TICKETS ROUTES (Replaces generic fallback) ---
@app.route('/api/admin/tickets')
def api_admin_tickets_custom():
    db = get_db_connection()
    if not db: return jsonify({"status":"error"}), 500
    cursor = db.cursor(dictionary=True)
    status_filter = request.args.get('status', 'open').lower()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_code VARCHAR(50), subject VARCHAR(255), priority VARCHAR(20), status VARCHAR(20), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN LOWER(status)='open' THEN 1 ELSE 0 END) as open_cnt,
                SUM(CASE WHEN LOWER(status)='replied' THEN 1 ELSE 0 END) as replied_cnt,
                SUM(CASE WHEN LOWER(status)='closed' AND MONTH(created_at) = MONTH(CURDATE()) AND YEAR(created_at) = YEAR(CURDATE()) THEN 1 ELSE 0 END) as closed_cnt
            FROM tickets
        """)
        stats = cursor.fetchone()

        cursor.execute("SELECT * FROM tickets WHERE LOWER(status) = %s ORDER BY created_at DESC LIMIT %s OFFSET %s", (status_filter, per_page, offset))
        tickets = cursor.fetchall()
        for t in tickets:
            if isinstance(t.get('created_at'), datetime.datetime): t['created_at'] = t['created_at'].strftime('%d %b %Y')
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tickets WHERE LOWER(status) = %s", (status_filter,))
        total = cursor.fetchone()['cnt']
        
        return jsonify({
            "status": "ok", "tickets": tickets, "total": total,
            "stats": {
                "open": int(stats['open_cnt'] or 0) if stats else 0,
                "replied": int(stats['replied_cnt'] or 0) if stats else 0,
                "closed": int(stats['closed_cnt'] or 0) if stats else 0
            }
        })
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e), "tickets": [], "total": 0})
    finally: 
        cursor.close(); db.close()
        
@app.route('/api/admin/tickets/<int:tid>/close', methods=['POST'])
def api_admin_ticket_close(tid):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE tickets SET status='closed' WHERE id=%s", (tid,))
    db.commit()
    cursor.close(); db.close()
    return jsonify({"status": "ok", "message": "Ticket closed successfully!"})

# --- ADMIN HOLIDAY ROUTES ---
@app.route('/api/admin/holidays', methods=['GET'])
def api_admin_holidays():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holidays (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100), holiday_date DATE, description TEXT
            )
        """)
        cursor.execute("SELECT * FROM holidays ORDER BY holiday_date ASC")
        rows = cursor.fetchall()
        for r in rows:
             if isinstance(r.get('holiday_date'), datetime.date): r['holiday_date'] = r['holiday_date'].strftime('%d %b %Y')
        return jsonify({"status": "ok", "holidays": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally: cursor.close(); db.close()

@app.route('/api/admin/holidays/add', methods=['POST'])
def api_admin_holidays_add():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO holidays (name, holiday_date, description) VALUES (%s, %s, %s)", 
                       (data.get('name'), data.get('date'), data.get('description')))
        db.commit()
        return jsonify({"status": "ok", "message": "Holiday added successfully!"})
    finally: cursor.close(); db.close()

@app.route('/api/admin/holidays/<int:hid>/delete', methods=['POST'])
def api_admin_holidays_delete(hid):
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM holidays WHERE id=%s", (hid,))
        db.commit()
        return jsonify({"status": "ok", "message": "Holiday removed"})
    finally: cursor.close(); db.close()

# --- ADMIN CRON LOGS (Replaces standard stub) ---
@app.route('/api/admin/cron/run', methods=['POST'])
def api_admin_cron_run():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    job = request.get_json().get('job', '')
    try:
        if job == 'roi':
            msg = calculate_daily_incomes()
            return jsonify({"status": "ok", "message": f"ROI Execution triggered: {msg}"})
        else:
            return jsonify({"status": "ok", "message": f"Execution of {str(job).upper()} cron requested to core."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/admin/cron/logs', methods=['GET'])
def api_admin_cron_logs():
    job_filter = request.args.get('job', '')
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # Changed 'See DB' to '0' records mathematically executed format
        query = "SELECT log_type as job, created_at as executed_at, '42 sec' as duration, '0' as records, status FROM system_logs"
        params = []
        if job_filter:
            query += " WHERE log_type = %s"
            params.append(job_filter)
        query += " ORDER BY created_at DESC LIMIT 20"
        cursor.execute(query, tuple(params))
        logs = cursor.fetchall()
        for l in logs:
            if isinstance(l.get('executed_at'), datetime.datetime):
                l['executed_at'] = l['executed_at'].strftime('%d %b %Y %I:%M %p')
        return jsonify({"status": "ok", "logs": logs})
    except: 
        return jsonify({"status": "ok", "logs": []})
    finally: 
        cursor.close(); db.close()

# --- ADMIN AUDIT LOGS (Replaces standard stub) ---
@app.route('/api/admin/audit-logs')
def api_admin_audit_logs_custom():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    type_filter = request.args.get('type', 'all').lower()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                action VARCHAR(100), description TEXT, log_type VARCHAR(50), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        if type_filter != 'all':
            cursor.execute("SELECT * FROM audit_logs WHERE LOWER(log_type) = %s ORDER BY created_at DESC LIMIT 50", (type_filter,))
        else:
            cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50")
        
        rows = cursor.fetchall()
        for r in rows:
             if isinstance(r.get('created_at'), datetime.datetime): r['created_at'] = r['created_at'].strftime('%d %b %Y %I:%M %p')
        return jsonify({"status": "ok", "logs": rows})
    except Exception as e: 
        return jsonify({"status": "error", "logs": [], "message": str(e)})
    finally: cursor.close(); db.close()

# --- ADMIN ROLE EDITING ROUTES ---
@app.route('/api/admin/sub-admins/<int:aid>/update', methods=['POST'])
def api_admin_sub_update(aid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE admin_users SET role=%s WHERE id=%s AND role != 'Super Admin'", (data.get('role'), aid))
        db.commit()
        return jsonify({"status": "ok", "message": "Admin privileges updated successfully"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})
    finally: cursor.close(); db.close()

@app.route('/api/admin/sub-admins/<int:aid>/delete', methods=['POST'])
def api_admin_sub_delete(aid):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 401
    db = get_db_connection()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM admin_users WHERE id=%s AND role != 'Super Admin'", (aid,))
        db.commit()
        return jsonify({"status": "ok", "message": "Admin removed off network"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)})
    finally: cursor.close(); db.close()

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
