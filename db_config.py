import mysql.connector
from mysql.connector import Error
from mysql.connector import pooling
import random
import os
from urllib.parse import urlparse

# 🌟 PRODUCTION DATABASE TUNNEL PARSER 🌟
mysql_url = os.environ.get("MYSQL_URL")

try:
    if mysql_url:
        # Parse the cloud connection string into readable parameters safely
        url = urlparse(mysql_url)
        db_config = {
            'host': url.hostname,
            'port': url.port or 3306,
            'user': url.username,
            'password': url.password,
            'database': url.path[1:]
        }
        
        # Instantiate the pool passing the parsed cloud configurations explicitly
        db_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mlm_pool",
            pool_size=32,
            pool_reset_session=True,
            **db_config
        )
    else:
        # Fallback parameters for local machine XAMPP environment testing
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
        cursor.execute("SELECT COUNT(*) as directs FROM users WHERE sponsor_id = %s", (user_id,))
        directs = cursor.fetchone()['directs']

        # Fixed: Updated recursive structural tracking to use sponsor_id and leg layout
        left_query = """
            WITH RECURSIVE downline AS (
                SELECT id FROM users WHERE sponsor_id = %s AND leg = 'left'
                UNION ALL
                SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
            ) SELECT COUNT(*) as left_count FROM downline;
        """
        cursor.execute(left_query, (user_id,))
        left_team = cursor.fetchone()['left_count']

        right_query = """
            WITH RECURSIVE downline AS (
                SELECT id FROM users WHERE sponsor_id = %s AND leg = 'right'
                UNION ALL
                SELECT u.id FROM users u INNER JOIN downline d ON u.sponsor_id = d.id
            ) SELECT COUNT(*) as right_count FROM downline;
        """
        cursor.execute(right_query, (user_id,))
        right_team = cursor.fetchone()['right_count']

        return {
            "direct_referrals": directs,
            "left_team": left_team,
            "right_team": right_team,
            "active_team": left_team + right_team,  # Demo sync metric
            "non_active": 0,
            "total_team": left_team + right_team
        }
    finally:
        cursor.close()
        db.close()

def get_financial_stats(user_id):
    db = get_db_connection()
    if not db: 
        return {"total_income": 0, "total_withdrawal": 0, "current_balance": 0, "cashback_bonus": 0}
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT SUM(amount) as total_income FROM wallet_transactions 
            WHERE user_id = %s AND transaction_type = 'CREDIT'
        """, (user_id,))
        income_res = cursor.fetchone()
        total_income = float(income_res['total_income']) if income_res and income_res['total_income'] else 0.00

        cursor.execute("""
            SELECT SUM(request_amount) as total_withdraw FROM withdrawals 
            WHERE user_id = %s AND status IN ('APPROVED', 'PENDING')
        """, (user_id,))
        withdraw_res = cursor.fetchone()
        total_withdraw = float(withdraw_res['total_withdraw']) if withdraw_res and withdraw_res['total_withdraw'] else 0.00

        cursor.execute("""
            SELECT SUM(amount) as total_cashback FROM wallet_transactions 
            WHERE user_id = %s AND transaction_type = 'CREDIT' AND bonus_type = 'CASHBACK'
        """, (user_id,))
        cashback_res = cursor.fetchone()
        cashback_bonus = float(cashback_res['total_cashback']) if cashback_res and cashback_res['total_cashback'] else 0.00

        # Fixed: Updated dictionary keys to line up perfectly with index.html JS selectors
        return {
            "total_income": round(total_income, 2),
            "total_withdrawal": round(total_withdraw, 2),
            "current_balance": round(total_income - total_withdraw, 2),
            "cashback_bonus": round(cashback_bonus, 2),
            "staking_bonus": 0.00,
            "sponsor_bonus": 0.00,
            "binary_bonus": 0.00,
            "repurchase_bonus": 0.00,
            "royalty_bonus": 0.00
        }
    finally:
        cursor.close()
        db.close()

def get_tree_view_data(user_code):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user_code, full_name, is_active FROM users WHERE user_code = %s", (user_code,))
        root_user = cursor.fetchone()
        if not root_user: return None

        cursor.execute("""
            SELECT user_code, full_name, is_active, leg 
            FROM users WHERE sponsor_id = %s
        """, (root_user['id'],))
        children = cursor.fetchall()

        tree_structure = {
            "status": "success",
            "id": root_user['user_code'],
            "name": root_user['full_name'],
            "active": root_user['is_active'],
            "children": {
                "left": None,
                "right": None
            }
        }

        for child in children:
            position = child['leg'].lower() if child['leg'] else ''
            if position in ['left', 'right']:
                tree_structure["children"][position] = {
                    "id": child['user_code'],
                    "name": child['full_name'],
                    "active": child['is_active']
                }
                
        return tree_structure
    finally:
        cursor.close()
        db.close()

def process_withdrawal_request(user_id, request_amount):
    db = get_db_connection()
    if not db: return {"status": "error", "message": "Database error"}
    cursor = db.cursor(dictionary=True)
    try:
        request_amount = float(request_amount)
        if request_amount < 100:
            return {"status": "error", "message": "Minimum withdrawal amount is ₹100."}
            
        stats = get_financial_stats(user_id)
        if request_amount > float(stats['current_balance']):
            return {"status": "error", "message": f"Insufficient funds. Balance: ₹{stats['current_balance']}."}
            
        # 5% TDS + 5% Admin fee split configuration
        tds_amount = request_amount * 0.05
        admin_amount = request_amount * 0.05
        total_deductions = tds_amount + admin_amount
        net_payable = request_amount - total_deductions
        
        cursor.execute("""
            INSERT INTO withdrawals (user_id, request_amount, tds_deduction, net_payable, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
        """, (user_id, request_amount, total_deductions, net_payable))
        
        db.commit()
        return {"status": "success", "message": f"Withdrawal requested. Net payout after 5% TDS & 5% Admin Charges: ₹{net_payable}."}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        db.close()

# Fixed: Rearranged arguments configuration to eliminate positional validation errors on purchase executions
def process_course_purchase(user_id, course_name, course_price, course_category="General Education"):
    db = get_db_connection()
    if not db: return {"status": "error", "message": "Database error"}
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT MAX(course_price) as highest_price FROM user_courses WHERE user_id = %s FOR UPDATE", (user_id,))
        result = cursor.fetchone()
        highest_price = result['highest_price'] if result and result['highest_price'] else 0
        
        if course_price < highest_price:
            return {"status": "error", "message": f"Downgrades not allowed. Minimum purchase requirement: ₹{highest_price}."}

        cursor.execute("""
            INSERT INTO user_courses (user_id, course_name, course_category, course_price, remaining_days, status)
            VALUES (%s, %s, %s, %s, 212, 'ACTIVE')
        """, (user_id, course_name, course_category, course_price))
        
        cursor.execute("UPDATE users SET is_active = TRUE WHERE id = %s", (user_id,))
        db.commit()
        return {"status": "success", "message": "Course activated successfully!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        db.close()

def register_new_user(full_name, email, dob, gender, aadhar_no, pan_no, mobile, password, sponsor_id, leg):
    db = get_db_connection()
    if not db:
        return {"status": "error", "message": "Database connection failed"}
    
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return {"status": "error", "message": "Email is already registered!"}
        
        real_sponsor_id = None
        if sponsor_id:
            cursor.execute("SELECT id FROM users WHERE user_code = %s", (sponsor_id,))
            sponsor_record = cursor.fetchone()
            if sponsor_record:
                real_sponsor_id = sponsor_record['id']
            else:
                return {"status": "error", "message": "Invalid Sponsor ID! That referral code does not exist."}
        
        user_code = f"MLM{random.randint(10000, 99999)}"

        cursor.execute("""
            INSERT INTO users (full_name, email, user_code, dob, gender, aadhar_no, pan_no, mobile, password, sponsor_id, leg) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (full_name, email, user_code, dob, gender, aadhar_no, pan_no, mobile, password, real_sponsor_id, leg))
        
        db.commit()
        return {"status": "success", "message": f"Registration successful!\nYour Login ID is: {user_code}"}
    except Exception as e:
        db.rollback()
        print("Registration Error:", e)
        return {"status": "error", "message": "An error occurred during registration."}
    finally:
        cursor.close()
        db.close()

def verify_login(user_code, password):
    db = get_db_connection()
    if not db: return None
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, full_name as name, user_code, is_active FROM users WHERE user_code = %s AND password = %s", (user_code, password))
        return cursor.fetchone()
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
        cursor.execute("""
            SELECT full_name, email, mobile, dob, gender, aadhar_no, pan_no, address, profile_img, created_at, is_active 
            FROM users WHERE id = %s
        """, (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()

# Fixed: Consolidated duplicates into a single, clean image-handling profile update handler
def update_user_profile(user_id, data):
    db = get_db_connection()
    if not db: return False
    cursor = db.cursor()
    try:
        query = """
            UPDATE users
            SET full_name = %s, mobile = %s, aadhar_no = %s, pan_no = %s, address = %s
        """
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
        print("Profile Update Error:", e)
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
        cursor.execute("""
            SELECT bank_acc_name, bank_acc_no, bank_ifsc, upi_id, upi_mobile 
            FROM users WHERE id = %s
        """, (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        db.close()

def update_bank_details(user_id, data):
    db = get_db_connection()
    if not db: return False
    cursor = db.cursor()
    try:
        cursor.execute("""
            UPDATE users
            SET bank_acc_name = %s, bank_acc_no = %s, bank_ifsc = %s, upi_id = %s, upi_mobile = %s
            WHERE id = %s
        """, (
            data.get('bank_acc_name'), data.get('bank_acc_no'), 
            data.get('bank_ifsc'), data.get('upi_id'), 
            data.get('upi_mobile'), user_id
        ))
        db.commit()
        return True
    except Exception as e:
        print("Bank Update Error:", e)
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
        cursor.execute("""
            SELECT request_amount, status, created_at, processed_at 
            FROM withdrawals 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT 10
        """, (user_id,))
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
            AND t.created_at >= CURDATE()
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
        cursor.execute("""
            SELECT id, user_code, full_name, mobile, email, created_at, is_active, 
                   aadhar_no, pan_no, sponsor_id
            FROM users 
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()
