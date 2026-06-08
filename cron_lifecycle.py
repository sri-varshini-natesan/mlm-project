import time
from datetime import datetime
from db_config import get_db_connection

def run_lifecycle_manager():
    print(f"--- Starting Lifecycle Manager: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    db = get_db_connection()
    if not db: 
        print("Database connection failed!")
        return
        
    cursor = db.cursor()

    try:
        # 1. ADD 1 DAY TO ALL INACTIVE USERS
        # Every night, if a user profile is inside a grace period window, its penalty timer ticks up by 1.
        cursor.execute("UPDATE users SET inactive_days = inactive_days + 1 WHERE is_active = FALSE")
        
        # 2. ENFORCE THE 250-DAY WASHOUT RULE
        # Find anyone who hit exactly 250 days today, and flush their left and right leg volumes completely to 0.00
        cursor.execute("""
            UPDATE users 
            SET left_volume = 0.00, right_volume = 0.00 
            WHERE is_active = FALSE AND inactive_days >= 250
        """)
        
        # Log how many users were washed out today
        washed_out_count = cursor.rowcount
        if washed_out_count > 0:
            print(f"WASHOUT EXECUTED: {washed_out_count} users crossed the 250 days threshold and lost their carry forward volume.")
        else:
            print("INFO: No users violated the 250-day window limits tonight.")

        db.commit()
        print("SUCCESS: User lifecycles updated successfully.")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {str(e)}")
    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    run_lifecycle_manager()