import mysql.connector
from mysql.connector import Error
from mysql.connector import pooling
import random
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import requests
from werkzeug.security import generate_password_hash, check_password_hash

try:
    db_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="mlm_pool",
        pool_size=32,
        pool_reset_session=True,
        host='localhost',
        database='mlm_database',
        user='root',
        password='' 
    )
    print("Database Connection Pool initialized successfully.")
except Error as e:
    print(f"Failed to initialize Connection Pool: {e}")
    db_pool = None

def get_db_connection():
    if not db_pool: return None
    try:
        return db_pool.get_connection()
    except Error as e:
        print(f"Pool exhaustion error: {e}")
        return None

def calculate_daily_incomes():
    db = get_db_connection()
    if not db: raise Exception("Database connection failed during income calculation.")
    cursor = db.cursor(dictionary=True)
    today = datetime.date.today()

    try:
        cursor.execute("SELECT id FROM system_logs WHERE log_type = 'daily_payout' AND DATE(created_at) = %s", (today,))
        if cursor.fetchone(): return "Already processed"

        if db.in_transaction: db.rollback() 
        db.start_transaction()

        # 1. DAILY ROI: Updated to JOIN with courses table
        cursor.execute("""
            SELECT uc.user_id, c.name as course_name, c.roi_percent as roi_percentage, c.price as course_price 
            FROM user_courses uc
            JOIN courses c ON uc.course_id = c.id
            WHERE uc.status = 'ACTIVE' AND uc.expires_at >= CURDATE()
        """)
        active_packages = cursor.fetchall()
        
        for pkg in active_packages:
            uid = pkg['user_id']
            price = float(pkg['course_price'] or 0.0)
            roi = float(pkg['roi_percentage'] or 0.0)
            roi_amount = price * (roi / 100.0)
            
            if roi_amount > 0:
                cursor.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s", (roi_amount, uid))
                cursor.execute("""
                    INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description) 
                    VALUES (%s, %s, 'CREDIT', 'STAKING_BONUS', %s)
                """, (uid, roi_amount, f"Daily ROI for {pkg['course_name']}"))

        # 2. BINARY MATCH: Updated to use left_volume and right_volume instead of carry
        cursor.execute("""
            SELECT id, left_volume, right_volume 
            FROM users 
            WHERE left_volume > 0 AND right_volume > 0
        """)
        binary_users = cursor.fetchall()
        
        BINARY_MATCH_PERCENTAGE = 0.10 
        
        for user in binary_users:
            uid = user['id']
            left = float(user['left_volume'])
            right = float(user['right_volume'])
            
            match_volume = min(left, right)
            binary_income = match_volume * BINARY_MATCH_PERCENTAGE
            
            cursor.execute("""
                UPDATE users 
                SET wallet_balance = wallet_balance + %s,
                    left_volume = left_volume - %s,
                    right_volume = right_volume - %s
                WHERE id = %s
            """, (binary_income, match_volume, match_volume, uid))
            
            cursor.execute("""
                INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description) 
                VALUES (%s, %s, 'CREDIT', 'BINARY_MATCH', %s)
            """, (uid, binary_income, f"Matched {match_volume} BV"))

        cursor.execute("INSERT INTO system_logs (log_type, status, message) VALUES ('daily_payout', 'SUCCESS', 'Daily incomes calculated successfully')")
        db.commit() 
        return "Success"

    except Exception as e:
        db.rollback() 
        raise e
    finally:
        cursor.close()
        db.close()

def send_welcome_email(to_email, user_name, user_code, password):
    sender_email = "your_company_email@gmail.com" 
    sender_password = "your_16_character_app_password" 

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = "Welcome to Our Platform - Login Details inside!"

    body = f"""Hello {user_name},
Congratulations! Your registration was successful.
Login ID: {user_code}
Password: {password}
Please log in and change your password immediately.
Regards,
The Admin Team"""
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"Success: Welcome email sent to {to_email}")
    except Exception as e:
        print(f"Error: Failed to send email to {to_email}. Reason: {e}")


def send_welcome_sms(mobile, user_code):
    url = "https://www.fast2sms.com/dev/bulkV2"
    api_key = "YOUR_FAST2SMS_API_KEY" 
    
    message = f"Welcome! Your account is active. Your Login ID is {user_code}. Please keep your password secure."
    
    querystring = {"authorization": api_key, "message": message, "language": "english", "route": "q", "numbers": mobile}
    
    try:
        response = requests.request("GET", url, headers={"cache-control": "no-cache"}, params=querystring)
        print(f"Success: SMS sent to {mobile}. API Response: {response.text}")
    except Exception as e:
        print(f"Error: Failed to send SMS to {mobile}. Reason: {e}")

def find_user_by_user_code(user_code):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE user_code = %s", (user_code,))
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()

def get_team_stats(user_id):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Direct Referrals (Using sponsor_id)
        cursor.execute("SELECT COUNT(*) as directs FROM users WHERE sponsor_id = %s", (user_id,))
        directs = cursor.fetchone()['directs']

        # 2. Get both Left and Right nodes in a single, safe query execution
        cursor.execute("SELECT id, leg FROM users WHERE placement_id = %s AND leg IN ('left', 'right')", (user_id,))
        children = cursor.fetchall()
        
        left_child_id = None
        right_child_id = None
        
        for child in children:
            if child['leg'] == 'left':
                left_child_id = child['id']
            elif child['leg'] == 'right':
                right_child_id = child['id']

        # 3. Dedicated internal function to consume and close tracking data sequentially
        def count_downline(start_id):
            if not start_id: return {"total": 0, "active": 0, "inactive": 0}
            
            query = """
                WITH RECURSIVE downline AS (
                    SELECT id, is_active FROM users WHERE id = %s
                    UNION ALL
                    SELECT u.id, u.is_active FROM users u INNER JOIN downline d ON u.placement_id = d.id
                )
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active, 
                       SUM(CASE WHEN is_active=0 THEN 1 ELSE 0 END) as inactive 
                FROM downline;
            """
            # Using a temporary clean cursor to avoid cross-contamination of unread results
            sub_cursor = db.cursor(dictionary=True)
            sub_cursor.execute(query, (start_id,))
            res = sub_cursor.fetchone()
            sub_cursor.close()
            
            return {
                "total": int(res['total'] or 0), 
                "active": int(res['active'] or 0), 
                "inactive": int(res['inactive'] or 0)
            }

        left_stats = count_downline(left_child_id)
        right_stats = count_downline(right_child_id)

        return {
            "direct_referrals": directs,
            "left_team": left_stats['total'],
            "right_team": right_stats['total'],
            "active_team": left_stats['active'] + right_stats['active'],
            "non_active": left_stats['inactive'] + right_stats['inactive'],
            "total_team": left_stats['total'] + right_stats['total']
        }
    finally:
        cursor.close()
        db.close()

def get_financial_stats(user_id):
    db = get_db_connection()
    if not db: 
        return {"total_income": 0, "total_withdrawal": 0, "current_balance": 0, "cashback_bonus": 0, "staking_bonus": 0, "sponsor_bonus": 0, "binary_bonus": 0}
    
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Get Total Income & Withdrawals
        cursor.execute("SELECT SUM(amount) as total FROM wallet_transactions WHERE user_id = %s AND transaction_type = 'CREDIT'", (user_id,))
        total_income = float(cursor.fetchone()['total'] or 0.00)

        cursor.execute("SELECT SUM(request_amount) as total FROM withdrawals WHERE user_id = %s AND status IN ('APPROVED', 'PENDING')", (user_id,))
        total_withdraw = float(cursor.fetchone()['total'] or 0.00)

        # 2. Automatically sum up ALL different bonus types!
        cursor.execute("""
            SELECT bonus_type, SUM(amount) as total_bonus 
            FROM wallet_transactions 
            WHERE user_id = %s AND transaction_type = 'CREDIT'
            GROUP BY bonus_type
        """, (user_id,))
        bonuses = cursor.fetchall()

        # Initialize the dictionary with zeros
        stats = {
            "total_income": round(total_income, 2),
            "total_withdrawal": round(total_withdraw, 2),
            "current_balance": round(total_income - total_withdraw, 2),
            "cashback_bonus": 0.00,
            "staking_bonus": 0.00,
            "sponsor_bonus": 0.00,
            "binary_bonus": 0.00,
            "repurchase_bonus": 0.00,
            "royalty_bonus": 0.00
        }

        # Dynamically fill in the actual money earned!
        for b in bonuses:
            b_type = b['bonus_type']
            amt = float(b['total_bonus'] or 0.00)
            
            if b_type == 'CASHBACK': stats['cashback_bonus'] = round(amt, 2)
            elif b_type == 'STAKING_BONUS': stats['staking_bonus'] = round(amt, 2)
            elif b_type == 'DIRECT_SPONSOR': stats['sponsor_bonus'] = round(amt, 2)
            elif b_type == 'BINARY_MATCH': stats['binary_bonus'] = round(amt, 2)

        return stats
    finally:
        cursor.close()
        db.close()

def get_tree_view_data(user_code):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)

    def get_img_url(img_filename):
        if img_filename: return f"/static/uploads/kyc/{img_filename}"
        return "https://cdn-icons-png.flaticon.com/512/149/149071.png"

    try:
        # Added JOIN to courses table
        cursor.execute("""
            SELECT u.id, u.user_code, u.full_name, u.is_active, u.profile_img, u.created_at, c.name as course_name 
            FROM users u
            LEFT JOIN user_courses uc ON u.id = uc.user_id AND uc.status = 'ACTIVE'
            LEFT JOIN courses c ON uc.course_id = c.id
            WHERE u.user_code = %s
        """, (user_code,))
        root_user = cursor.fetchone()

        if not root_user: return None

        def build_node(user_record):
            # Added JOIN to courses table for downlines
            cursor.execute("""
                SELECT u.id, u.user_code, u.full_name, u.is_active, u.leg, u.profile_img, u.created_at, c.name as course_name 
                FROM users u
                LEFT JOIN user_courses uc ON u.id = uc.user_id AND uc.status = 'ACTIVE'
                LEFT JOIN courses c ON uc.course_id = c.id
                WHERE u.placement_id = %s
            """, (user_record['id'],))
            children_records = cursor.fetchall()

            node_data = {
                "id": user_record['user_code'],
                "name": user_record['full_name'],
                "active": user_record['is_active'],
                "image": get_img_url(user_record['profile_img']),
                "course": user_record.get('course_name') or "Not Enrolled",
                "join_date": user_record['created_at'].strftime("%d %b %Y") if user_record.get('created_at') else "N/A",
                "children": { "left": None, "right": None }
            }

            for child in children_records:
                position = child['leg'].lower() if child['leg'] else ''
                if position == 'left':
                    node_data["children"]["left"] = build_node(child)
                elif position == 'right':
                    node_data["children"]["right"] = build_node(child)

            return node_data

        tree_structure = build_node(root_user)
        tree_structure["status"] = "success"
        return tree_structure
    except Exception as e:
        print("Tree View Error:", e)
        return None
    finally:
        cursor.close()
        db.close()

def process_withdrawal_request(user_id, request_amount):
    db = get_db_connection()
    if not db: return {"status": "error", "message": "Database error"}
    cursor = db.cursor(dictionary=True)
    try:
        request_amount = float(request_amount)
        if request_amount < 100: return {"status": "error", "message": "Minimum withdrawal amount is ₹100."}
            
        stats = get_financial_stats(user_id)
        if request_amount > float(stats['current_balance']):
            return {"status": "error", "message": f"Insufficient funds. Balance: ₹{stats['current_balance']}."}
            
        tds_amount = request_amount * 0.05
        admin_amount = request_amount * 0.05
        total_deductions = tds_amount + admin_amount
        net_payable = request_amount - total_deductions
        
        cursor.execute("""
            INSERT INTO withdrawals (user_id, request_amount, tds_deduction, net_payable, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
        """, (user_id, request_amount, total_deductions, net_payable))
        db.commit()
        return {"status": "success", "message": f"Withdrawal requested. Net payout: ₹{net_payable}."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        db.close()

def process_course_purchase(user_id, course_id):
    db = get_db_connection()
    if not db: return {"status": "error", "message": "Database error"}
    cursor = db.cursor(dictionary=True)
    
    try:
        # 1. Fetch course details directly from courses
        cursor.execute("SELECT id, name, price, duration_days FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        if not course: return {"status": "error", "message": "Invalid course selection."}
            
        course_price = float(course['price'])
        course_name = course['name']
        duration = int(course.get('duration_days', 250))

        cursor.execute("SELECT wallet_balance, sponsor_id, leg FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user or float(user['wallet_balance']) < course_price:
            return {"status": "error", "message": f"Insufficient funds. Course costs ₹{course_price}."}

        if db.in_transaction: 
            db.rollback() # Clear any stuck transactions first!
        db.start_transaction()

        cursor.execute("UPDATE users SET wallet_balance = wallet_balance - %s, is_active = 1 WHERE id = %s", (course_price, user_id))
        
        cursor.execute("""
            INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description) 
            VALUES (%s, %s, 'DEBIT', 'COURSE_PURCHASE', %s)
        """, (user_id, course_price, f"Purchased {course_name}"))

        # 2. Give the Course (LEAN SCHEMA: using expires_at)
        cursor.execute("""
            INSERT INTO user_courses (user_id, course_id, status, created_at, expires_at) 
            VALUES (%s, %s, 'ACTIVE', NOW(), DATE_ADD(NOW(), INTERVAL %s DAY))
        """, (user_id, course_id, duration))

        if user['sponsor_id']:
            sponsor_bonus = course_price * 0.10
            cursor.execute("UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s", (sponsor_bonus, user['sponsor_id']))
            cursor.execute("""
                INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description) 
                VALUES (%s, %s, 'CREDIT', 'DIRECT_SPONSOR', %s)
            """, (user['sponsor_id'], sponsor_bonus, f"Direct Referral Bonus for {course_name}"))

        # 3. BINARY VOLUME ROLL-UP ENGINE (Removed redundant left_carry/right_carry)
        current_upline_id = user['sponsor_id']
        current_leg = user['leg']
        
        while current_upline_id and current_leg:
            if current_leg.lower() == 'left':
                cursor.execute("UPDATE users SET left_volume = left_volume + %s WHERE id = %s", (course_price, current_upline_id))
            elif current_leg.lower() == 'right':
                cursor.execute("UPDATE users SET right_volume = right_volume + %s WHERE id = %s", (course_price, current_upline_id))
            
            cursor.execute("SELECT sponsor_id, leg FROM users WHERE id = %s", (current_upline_id,))
            next_upline = cursor.fetchone()
            
            if next_upline and next_upline['sponsor_id']:
                current_upline_id = next_upline['sponsor_id']
                current_leg = next_upline['leg']
            else:
                break 

        db.commit()
        return {"status": "success", "message": f"{course_name} activated successfully!"}
        
    except Exception as e:
        db.rollback()
        print("Purchase Error:", e)
        return {"status": "error", "message": "An error occurred during purchase."}
    finally:
        cursor.close()
        db.close()

def register_new_user(full_name, email, dob, gender, aadhar_no, pan_no, mobile, password, sponsor_id, leg):
    db = get_db_connection()
    if not db: return {"status": "error", "message": "Database error"}
    
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone(): return {"status": "error", "message": "Email is already registered!"}
        
        real_sponsor_id = None
        if sponsor_id:
            cursor.execute("SELECT id FROM users WHERE user_code = %s", (sponsor_id,))
            sponsor_record = cursor.fetchone()
            if sponsor_record: real_sponsor_id = sponsor_record['id']
            else: return {"status": "error", "message": "Invalid Sponsor ID!"}
        
        user_code = f"MLM{random.randint(10000, 99999)}"
        
        # --- 🌟 THE SPILLOVER ENGINE 🌟 ---
        leg = str(leg).lower().strip()
        if leg not in ['left', 'right']: leg = 'left' # Fallback
        
        placement_id = real_sponsor_id
        
        # This loop finds the absolute bottom of the specified leg
        if placement_id:
            while True:
                # Look for someone already in this slot
                cursor.execute("SELECT id FROM users WHERE placement_id = %s AND leg = %s", (placement_id, leg))
                child = cursor.fetchone()
                if child:
                    # Slot taken, move down to that child and repeat
                    placement_id = child['id']
                else:
                    # Found an empty slot at the bottom!
                    break 
        
        cursor.execute("""
            INSERT INTO users (full_name, email, user_code, dob, gender, aadhar_no, pan_no, mobile, password, sponsor_id, placement_id, leg) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (full_name, email, user_code, dob, gender, aadhar_no, pan_no, mobile, password, real_sponsor_id, placement_id, leg))
        
        db.commit() 
        # Optional: threading.Thread(target=send_welcome_email, ...).start()
        
        return {"status": "success", "message": f"Registration successful!\nYour Login ID is: {user_code}"}
        
    except mysql.connector.IntegrityError as e:
        db.rollback()
        return {"status": "error", "message": "Account details already exist."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": "Registration error."}
    finally:
        cursor.close()
        db.close()

def verify_login(user_code, password):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        # DOWNGRADED: Checking the raw password directly in the SQL query
        cursor.execute("SELECT id, full_name as name, user_code, is_active FROM users WHERE user_code = %s AND password = %s", (user_code, password))
        user = cursor.fetchone()
        
        if user:
            return user
        return None
    except Exception as e:
        print("Login Error:", e)
        return None
    finally:
        cursor.close()
        db.close()

def get_user_profile(user_id):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT full_name, email, mobile, dob, gender, aadhar_no, pan_no, address, profile_img, created_at, is_active FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()

def update_user_profile(user_id, data):
    db = get_db_connection()
    if not db: return False
    cursor = db.cursor()
    try:
        query = "UPDATE users SET full_name = %s, mobile = %s, aadhar_no = %s, pan_no = %s, address = %s"
        params = [data.get('full_name'), data.get('mobile'), data.get('aadhar_no'), data.get('pan_no'), data.get('address')]
        if data.get('profile_img'):
            query += ", profile_img = %s"
            params.append(data.get('profile_img'))
        query += " WHERE id = %s"
        params.append(user_id)
        cursor.execute(query, tuple(params))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
    finally:
        cursor.close()
        db.close()

def get_bank_details(user_id):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT bank_acc_name, bank_acc_no, bank_ifsc, upi_id, upi_mobile FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()

def update_bank_details(user_id, data):
    db = get_db_connection()
    if not db: return False
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE users SET bank_acc_name = %s, bank_acc_no = %s, bank_ifsc = %s, upi_id = %s, upi_mobile = %s WHERE id = %s", 
            (data.get('bank_acc_name'), data.get('bank_acc_no'), data.get('bank_ifsc'), data.get('upi_id'), data.get('upi_mobile'), user_id))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
    finally:
        cursor.close()
        db.close()

def get_withdrawal_history(user_id):
    db = get_db_connection()
    if not db: return []
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT request_amount, status, created_at, processed_at FROM withdrawals WHERE user_id = %s ORDER BY created_at DESC LIMIT 10", (user_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()

def get_daily_earners():
    db = get_db_connection()
    if not db: return []
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT u.id, u.mobile, u.email, u.full_name, SUM(t.amount) as daily_total
            FROM users u 
            JOIN wallet_transactions t ON u.id = t.user_id 
            WHERE t.transaction_type = 'CREDIT' 
            AND DATE(t.created_at) = CURDATE()
            GROUP BY u.id
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()

def get_all_users_for_admin():
    db = get_db_connection()
    if not db: return []
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user_code, full_name, mobile, email, created_at, is_active, aadhar_no, pan_no, sponsor_id FROM users ORDER BY created_at DESC")
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()
