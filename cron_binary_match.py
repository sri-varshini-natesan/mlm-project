import time
from datetime import datetime
from db_config import get_db_connection

def run_binary_match():
    # FLUSH INACTIVE USERS: Wipe their carry forward volume to 0
    cursor.execute("""
        UPDATE users 
        SET left_volume = 0, right_volume = 0 
        WHERE is_active = FALSE AND (left_volume > 0 OR right_volume > 0)
    """)
    db.commit()

    print(f"--- Starting Binary Match Process: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    db = get_db_connection()
    if not db: return

    cursor = db.cursor(dictionary=True)

    try:
        # 1. Find ONLY users who have volume on BOTH sides (otherwise a match is impossible)
        cursor.execute("""
            SELECT id, user_code, left_volume, right_volume 
            FROM users 
            WHERE left_volume > 0 AND right_volume > 0 AND is_active = TRUE
        """)
        eligible_users = cursor.fetchall()
        
        total_payout = 0

        for user in eligible_users:
            user_id = user['id']
            left_vol = float(user['left_volume'])
            right_vol = float(user['right_volume'])
            
            # 2. CALCULATE THE 1:2 OR 2:1 RATIO MATCH
            # It finds which combination uses the most volume for the biggest payout
            
            # Option A: 1 Part Left, 2 Parts Right
            possible_base_1_2 = min(left_vol, right_vol / 2)
            
            # Option B: 2 Parts Left, 1 Part Right
            possible_base_2_1 = min(left_vol / 2, right_vol)
            
            base_match = 0
            deduct_left = 0
            deduct_right = 0
            
            # Pick the mathematical option that yields the higher match
            if possible_base_1_2 >= possible_base_2_1 and possible_base_1_2 > 0:
                base_match = possible_base_1_2
                deduct_left = base_match
                deduct_right = base_match * 2
            elif possible_base_2_1 > 0:
                base_match = possible_base_2_1
                deduct_left = base_match * 2
                deduct_right = base_match
                
            # If a match was found (meaning they had enough volume for a 1:2 ratio)
            if base_match > 0:
                # 3. Calculate 3% Bonus (Based on the total matched volume)
                total_matched_volume = deduct_left + deduct_right
                bonus_amount = total_matched_volume * 0.03
                
                if bonus_amount > 0:
                    # Pay the User
                    cursor.execute("""
                        INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description)
                        VALUES (%s, %s, 'CREDIT', 'BINARY_MATCH', %s)
                    """, (user_id, bonus_amount, f"Binary Match 3% (L: {deduct_left}, R: {deduct_right})"))
                    
                    # 4. THE CARRY FORWARD MATH
                    # Deduct the used volume. The remainder automatically stays in the database for tomorrow!
                    cursor.execute("""
                        UPDATE users 
                        SET left_volume = left_volume - %s, 
                            right_volume = right_volume - %s 
                        WHERE id = %s
                    """, (deduct_left, deduct_right, user_id))
                    
                    total_payout += bonus_amount
                    print(f"Paid User {user['user_code']}: ₹{bonus_amount} (Matched {deduct_left}L : {deduct_right}R)")

        db.commit()
        print(f"SUCCESS: Binary matching complete. Total Paid: ₹{total_payout}")

    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR: {str(e)}. Transaction rolled back.")
    finally:
        cursor.close()
        db.close()
        print("--- Binary Match Process Complete ---")

if __name__ == "__main__":
    run_binary_match()