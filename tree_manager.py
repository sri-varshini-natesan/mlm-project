from db_config import get_db_connection

class TreeManager:
    def __init__(self):
        self.db = get_db_connection()
        self.cursor = self.db.cursor(dictionary=True)

    def create_user(self, user_data):
        """Creates the user in the database and returns their new ID."""
        query = """
            INSERT INTO users (full_name, email, mobile, aadhar_number, pan_number, gender, dob)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            user_data.get('fullName'), user_data.get('email'), user_data.get('mobile'),
            user_data.get('aadhar'), user_data.get('pan'), user_data.get('sex'), user_data.get('dob')
        )
        self.cursor.execute(query, values)
        self.db.commit()
        return self.cursor.lastrowid # Returns the newly generated user ID

    def get_child(self, upline_id, position):
        """Checks if a specific slot is taken."""
        query = "SELECT id FROM users WHERE upline_id = %s AND tree_position = %s"
        self.cursor.execute(query, (upline_id, position))
        return self.cursor.fetchone()

    def assign_placement(self, sponsor_id, upline_id, position, new_user_id):
        """Executes the final placement update in the database."""
        query = """
            UPDATE users 
            SET sponsor_id = %s, upline_id = %s, tree_position = %s 
            WHERE id = %s
        """
        self.cursor.execute(query, (sponsor_id, upline_id, position, new_user_id))
        self.db.commit()
        return upline_id

    def place_on_left_leg(self, sponsor_id, new_user_id):
        """Strict 1-slot deep left placement."""
        current_node = sponsor_id
        
        while True:
            left_child = self.get_child(current_node, 'LEFT_1')
            
            if not left_child:
                # Slot is empty, place user here
                return self.assign_placement(sponsor_id, current_node, 'LEFT_1', new_user_id)
            else:
                # Slot taken, move down to this child and loop again
                current_node = left_child['id']

    def place_on_right_leg(self, sponsor_id, new_user_id):
        """Strict 2-slot right placement with outer-edge spillover."""
        
        # 1. Check direct RIGHT_1
        if not self.get_child(sponsor_id, 'RIGHT_1'):
            return self.assign_placement(sponsor_id, sponsor_id, 'RIGHT_1', new_user_id)

        # 2. Check direct RIGHT_2
        if not self.get_child(sponsor_id, 'RIGHT_2'):
            return self.assign_placement(sponsor_id, sponsor_id, 'RIGHT_2', new_user_id)

        # 3. SPILLOVER: Both direct slots are full. Traverse down the RIGHT_2 outer edge.
        current_node = self.get_child(sponsor_id, 'RIGHT_2')['id']
        
        while True:
            inner_right = self.get_child(current_node, 'RIGHT_1')
            if not inner_right:
                return self.assign_placement(sponsor_id, current_node, 'RIGHT_1', new_user_id)
                
            outer_right = self.get_child(current_node, 'RIGHT_2')
            if not outer_right:
                return self.assign_placement(sponsor_id, current_node, 'RIGHT_2', new_user_id)
                
            # Both taken, keep moving down the outer edge
            current_node = outer_right['id']

    def place_company_spillover(self, new_user_id):
        """
        Auto-Fill Logic for users with NO Referral ID.
        Scans the entire tree Top-to-Bottom, Left-to-Right.
        """
        admin_root_id = 1 # Assuming user ID 1 is the company/admin root
        queue = [admin_root_id]
        
        while queue:
            current_node = queue.pop(0)
            
            # Check Left 1
            left_1 = self.get_child(current_node, 'LEFT_1')
            if not left_1:
                return self.assign_placement(admin_root_id, current_node, 'LEFT_1', new_user_id)
            queue.append(left_1['id'])

            # Check Right 1
            right_1 = self.get_child(current_node, 'RIGHT_1')
            if not right_1:
                return self.assign_placement(admin_root_id, current_node, 'RIGHT_1', new_user_id)
            queue.append(right_1['id'])

            # Check Right 2
            right_2 = self.get_child(current_node, 'RIGHT_2')
            if not right_2:
                return self.assign_placement(admin_root_id, current_node, 'RIGHT_2', new_user_id)
            queue.append(right_2['id'])

    def close(self):
        self.cursor.close()
        self.db.close()