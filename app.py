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
import random
import threading
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
app.config['SESSION_COOKIE_SECURE'] = False 
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 

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
# PAGE ROUTES & APIS
# ==========================================

@app.route('/')
def home():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    user_code = session.get('user_code')
    left_link = f"{request.host_url}signup/{user_code}?side=left"
    right_link = f"{request.host_url}signup/{user_code}?side=right"
    return render_template('user/index.html', left_link=left_link, right_link=right_link)

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    result = register_new_user(
        data.get('fullName'), data.get('email'), data.get('dob'), 
        data.get('sex'), data.get('aadhar'), data.get('pan'), 
        data.get('mobile'), data.get('password'), data.get('sponsor_id'), data.get('leg')
    )
    return jsonify(result)

@app.route('/api/courses/purchase', methods=['POST'])
def api_purchase_course():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json()
    course_id = data.get('course_id')
    if not course_id: return jsonify({"status": "error", "message": "Course ID missing."})
    
    result = process_course_purchase(session['user_id'], course_id)
    return jsonify(result)

@app.route('/api/dashboard/me', methods=['GET'])
def api_dashboard_me():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    user_id = session['user_id']
    financials = get_financial_stats(user_id)
    team = get_team_stats(user_id)
    return jsonify({"status": "success", "data": {"financials": financials, "team": team}})

@app.route('/api/admin/team-list/<category>')
def get_team_list(category):
    user_id = session.get('user_id') 
    if not user_id: return jsonify({"members": []}), 401

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Recursive Query to support Deep Tree/Spillover Counting
    query = """
        WITH RECURSIVE downline AS (
            SELECT id, user_code, full_name, is_active, leg FROM users WHERE sponsor_id = %s
            UNION ALL
            SELECT u.id, u.user_code, u.full_name, u.is_active, d.leg 
            FROM users u INNER JOIN downline d ON u.placement_id = d.id
        )
        SELECT d.user_code as id, d.full_name as name, d.is_active, d.leg, c.name as course 
        FROM downline d
        LEFT JOIN user_courses uc ON d.id = uc.user_id AND uc.status = 'ACTIVE'
        LEFT JOIN courses c ON uc.course_id = c.id
        WHERE 1=1
    """
    if category == 'active': query += " AND d.is_active = 1"
    elif category == 'inactive': query += " AND d.is_active = 0"
    elif category == 'left': query += " AND d.leg = 'left'"
    elif category == 'right': query += " AND d.leg = 'right'"

    cursor.execute(query, (user_id,))
    members = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify({"members": members})

# [ ... Keep all your existing Admin routes from your provided file here ... ]

if __name__ == '__main__':
    print("🚀 Secure Server starting! Open http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
