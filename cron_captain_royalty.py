import time
from datetime import datetime
from db_config import get_db_connection

# The Exact Data from the Final Core Business Logic Image
ROYALTY_LEVELS = {
    1:  {"direct": 3,     "team_l": 10,     "team_r": 10,     "bonus": 250},
    2:  {"direct": 6,     "team_l": 20,     "team_r": 20,     "bonus": 500},
    3:  {"direct": 10,    "team_l": 30,     "team_r": 30,     "bonus": 750},
    4:  {"direct": 15,    "team_l": 50,     "team_r": 50,     "bonus": 1000},
    5:  {"direct": 25,    "team_l": 75,     "team_r": 75,     "bonus": 2500},
    6:  {"direct": 50,    "team_l": 150,    "team_r": 150,    "bonus": 5000},
    7:  {"direct": 80,    "team_l": 300,    "team_r": 300,    "bonus": 10000},
    8:  {"direct": 125,   "team_l": 500,    "team_r": 500,    "bonus": 15000},
    9:  {"direct": 175,   "team_l": 700,    "team_r": 700,    "bonus": 20000},
    10: {"direct": 250,   "team_l": 1000,   "team_r": 1000,   "bonus": 30000},
    11: {"direct": 350,   "team_l": 2500,   "team_r": 2500,   "bonus": 45000},
    12: {"direct": 500,   "team_l": 5000,   "team_r": 5000,   "bonus": 50000},
    13: {"direct": 650,   "team_l": 7500,   "team_r": 7500,   "bonus": 75000},
    14: {"direct": 800,   "team_l": 10000,  "team_r": 10000,  "bonus": 100000},  # 1 Lakh
    15: {"direct": 1000,  "team_l": 15000,  "team_r": 15000,  "bonus": 200000},  # 2 Lakh
    16: {"direct": 2000,  "team_l": 25000,  "team_r": 25000,  "bonus": 300000},  # 3 Lakh
    17: {"direct": 3000,  "team_l": 40000,  "team_r": 40000,  "bonus": 500000},  # 5 Lakh
    18: {"direct": 4000,  "team_l": 60000,  "team_r": 60000,  "bonus": 750000},  # 7.5 Lakh
    19: {"direct": 5000,  "team_l": 80000,  "team_r": 80000,  "bonus": 1000000}, # 10 Lakh
    20: {"direct": 10000, "team_l": 100000, "team_r": 100000, "bonus": 2500000}  # 25 Lakh
}

def calculate_active_team_counts(cursor, user_id):
    """Calculates exactly how many ACTIVE users are in the Left and Right legs."""
    
    # Condition 1: Active Users Only - Left Leg Count
    left_query = """
        WITH RECURSIVE downline AS (
            SELECT id, is_active FROM users WHERE upline_id = %s AND tree_position = 'LEFT_1'
            UNION ALL
            SELECT u.id, u.is_active FROM users u
            INNER JOIN downline d ON u.upline_id = d.id
        )
        SELECT COUNT(*) as count FROM downline WHERE is_active = TRUE;
    """
    cursor.execute(left_query, (user_id,))
    active_left = cursor.fetchone()['count']

    # Condition 1: Active Users Only - Right Leg Count
    right_query = """
        WITH RECURSIVE downline AS (
            SELECT id, is_active FROM users WHERE upline_id = %s AND tree_position IN ('RIGHT_1', 'RIGHT_2')
            UNION ALL
            SELECT u.id, u.is_active FROM users u
            INNER JOIN downline d ON u.upline_id = d.id
        )
        SELECT COUNT(*) as count FROM downline WHERE is_active = TRUE;
    """
    cursor.execute(right_query, (user_id,))
    active_right = cursor.fetchone()['count']

    return active_left, active_right

def run_captain_royalty_evaluator():
    print(f"--- Starting Captain Royalty Evaluator: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    db = get_db_connection()
    if not db: return
    cursor = db.cursor(dictionary=True)

    try:
        # Only evaluate users who are currently active and haven't hit level 20 yet
        cursor.execute("SELECT id, user_code, captain_level FROM users WHERE is_active = TRUE AND captain_level < 20")
        eligible_users = cursor.fetchall()
        
        for user in eligible_users:
            user_id = user['id']
            current_level = user['captain_level']
            next_level_to_check = current_level + 1
            
            # 1. Check Condition 2 & 3: Active Direct Referrals Count
            cursor.execute("SELECT COUNT(*) as direct_count FROM users WHERE sponsor_id = %s AND is_active = TRUE", (user_id,))
            active_directs = cursor.fetchone()['direct_count']
            
            # Get the requirements for the next level
            reqs = ROYALTY_LEVELS[next_level_to_check]
            
            # Quick check: If they don't even have the required direct referrals, skip the heavy team query
            if active_directs < reqs['direct']:
                continue
                
            # 2. Check Condition 3: Active Team Left and Right counts
            active_left, active_right = calculate_active_team_counts(cursor, user_id)
            
            # 3. Evaluate Success!
            if active_left >= reqs['team_l'] and active_right >= reqs['team_r']:
                bonus_amount = reqs['bonus']
                
                # Pay the user
                cursor.execute("""
                    INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description)
                    VALUES (%s, %s, 'CREDIT', 'CAPTAIN_ROYALTY', %s)
                """, (user_id, bonus_amount, f"Captain Royalty Bonus - Reached Level {next_level_to_check}"))
                
                # Update their rank in the database
                cursor.execute("UPDATE users SET captain_level = %s WHERE id = %s", (next_level_to_check, user_id))
                
                print(f"LEVEL UP! User {user['user_code']} achieved Level {next_level_to_check}. Paid ₹{bonus_amount}.")

        db.commit()
        print("SUCCESS: Captain Royalty evaluations complete.")

    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR: {str(e)}")
    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    run_captain_royalty_evaluator()