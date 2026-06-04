# create_user.py
from db_config import register_new_user, get_db_connection

print("Creating First User: John Doe...")

# 1. Register John Doe
response = register_new_user("John Doe", "johndoe@mlm.com", "password123")
print(response['message'])

# 2. Fetch the newly generated Sponsor ID
db = get_db_connection()
cursor = db.cursor(dictionary=True)
cursor.execute("SELECT id, user_code FROM users WHERE email = 'johndoe@mlm.com'")
user = cursor.fetchone()

if user:
    print("\n" + "="*30)
    print("✅ JOHN DOE CREATED SUCCESSFULLY!")
    print(f"Database ID: {user['id']}")
    print(f"Login Sponsor ID: {user['user_code']}")  # <-- YOU NEED THIS TO LOG IN!
    print("Login Password: password123")
    print("="*30 + "\n")
else:
    print("Something went wrong finding the user.")

cursor.close()
db.close()