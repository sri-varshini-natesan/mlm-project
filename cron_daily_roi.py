import time
from datetime import datetime
from db_config import get_db_connection

def run_daily_roi():
    print(f"--- Starting Daily ROI Process: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    db = get_db_connection()
    if not db:
        print("Database connection failed!")
        return

    cursor = db.cursor(dictionary=True)

    try:
        # ==========================================
        # RULE 1: NO ROI ON WEEKENDS
        # ==========================================
        current_day = datetime.now().weekday() # Monday is 0, Sunday is 6
        if current_day >= 5:
            print("Today is the weekend (Saturday/Sunday). No ROI payouts today.")
            return

        # ==========================================
        # RULE 2: NO ROI ON ADMIN SELECTED HOLIDAYS
        # ==========================================
        today_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT holiday_name FROM admin_holidays WHERE holiday_date = %s", (today_str,))
        holiday = cursor.fetchone()
        
        if holiday:
            print(f"Today is an Admin Holiday: {holiday['holiday_name']}. ROI paused.")
            return

        # ==========================================
        # RULES 3 & 4: MULTIPLE INDEPENDENT COURSES
        # ==========================================
        # Only fetch active courses for users who are currently active (Green status)
        cursor.execute("""
            SELECT uc.id, uc.user_id, uc.course_name, uc.course_price, uc.remaining_days 
            FROM user_courses uc
            INNER JOIN users u ON uc.user_id = u.id
            WHERE uc.status = 'ACTIVE' AND uc.remaining_days > 0 AND u.is_active = TRUE
        """)
        active_courses = cursor.fetchall()
        
        if not active_courses:
            print("No active courses eligible for ROI payouts today. Exiting.")
            return

        for course in active_courses:
            user_id = course['user_id']
            course_id = course['id'] # The unique ID of this specific purchase
            course_price = float(course['course_price'])
            
            # Calculate 1% Daily ROI for this specific course
            roi_amount = course_price * 0.01 
            
            # Deposit the 1%
            cursor.execute("""
                INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description)
                VALUES (%s, %s, 'CREDIT', 'DAILY_ROI', %s)
            """, (user_id, roi_amount, f"Daily 1% ROI for {course['course_name']}"))
            
            # Deduct 1 day from THIS course's specific timer
            new_remaining_days = course['remaining_days'] - 1
            
            if new_remaining_days > 0:
                cursor.execute("UPDATE user_courses SET remaining_days = %s WHERE id = %s", (new_remaining_days, course_id))
            else:
                # 212 Days completed: Expire the course tracking entry
                cursor.execute("UPDATE user_courses SET remaining_days = 0, status = 'EXPIRED' WHERE id = %s", (course_id,))
                
                # ENFORCE CRITICAL LIFECYCLE RULE 2: Turn user flag to FALSE (Puts account in Grace Period)
                # This freezes all other incomes immediately, but keeps leg volumes intact
                cursor.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
                print(f"Course ID {course_id} for User {user_id} has expired. User shifted to Grace Period (Inactive).")

        db.commit()
        print("SUCCESS: All valid ROIs paid and statuses updated.")

    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR: {str(e)}. Transaction rolled back.")
    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    run_daily_roi()