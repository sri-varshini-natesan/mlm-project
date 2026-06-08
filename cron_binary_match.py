import time
from datetime import datetime
from db_config import get_db_connection
from decimal import Decimal, ROUND_HALF_UP

def get_direct_referral_count(cursor, user_id):
    """Helper to count direct referrals from the database."""
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE sponsor_id = %s", (user_id,))
    result = cursor.fetchone()
    return result['count'] if result else 0

def run_binary_match():
    db = get_db_connection()
    if not db: return
    cursor = db.cursor(dictionary=True)

    print(f"--- Starting Volume-Based Binary Match: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    try:
        # Fetch all active users
        cursor.execute("""
            SELECT id, user_code, left_volume, right_volume, left_carry, right_carry 
            FROM users 
            WHERE is_active = TRUE
        """)
        users = cursor.fetchall()
        
        total_payout = 0

        for user in users:
            # 1. QUALIFICATION GATE: Check for 3 Direct Referrals
            if get_direct_referral_count(cursor, user['id']) < 3:
                print(f"Skipping {user['user_code']}: Needs 3 direct referrals.")
                continue 
            
            # 2. Calculate Total Available Volume (Volume + Carry Forward)
            total_left = float(user['left_volume']) + float(user['left_carry'])
            total_right = float(user['right_volume']) + float(user['right_carry'])
            
            # 3. Find Matched Volume (Formula: MIN(Left, Right))
            matched_volume = min(total_left, total_right)
            
            # Only proceed if there is a match
            if matched_volume > 0:
                # 4. Calculate 3% Bonus
                bonus_amount = Decimal(str(matched_volume)) * Decimal('0.03')
                bonus_amount = bonus_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                # 5. Calculate New Carry Forward (Remaining Volume)
                new_left_carry = total_left - matched_volume
                new_right_carry = total_right - matched_volume
                
                # 6. Database Updates
                # A: Record the binary bonus transaction
                cursor.execute("""
                    INSERT INTO wallet_transactions (user_id, amount, transaction_type, bonus_type, description)
                    VALUES (%s, %s, 'CREDIT', 'BINARY_MATCH', %s)
                """, (user['id'], float(bonus_amount), f"Binary Match 3% on ₹{matched_volume}"))
                
                # B: Update Carry Forward (Clear volume, save remainder to carry)
                cursor.execute("""
                    UPDATE users 
                    SET left_volume = 0, right_volume = 0, 
                        left_carry = %s, right_carry = %s 
                    WHERE id = %s
                """, (new_left_carry, new_right_carry, user['id']))
                
                total_payout += float(bonus_amount)
                print(f"Paid User {user['user_code']}: ₹{bonus_amount} | Carry: {new_left_carry}L, {new_right_carry}R")

        db.commit()
        print(f"SUCCESS: Binary matching complete. Total Paid: ₹{total_payout}")

    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR: {str(e)}")
    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    run_binary_match()