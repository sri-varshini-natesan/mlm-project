from db_config import get_daily_earners, get_financial_stats

def run_midnight_job():
    earners = get_daily_earners()
    for user in earners:
        stats = get_financial_stats(user['id'])
        msg = f"Hi {user['full_name']}, you received ₹{user['daily_total']} today! Total balance: ₹{stats['total_balance']}."
        
        # Call your SMS/Email functions here
        print(f"Sending to {user['mobile']}: {msg}")