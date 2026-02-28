from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

class User(UserMixin):
    """User model for authentication and data storage"""
    
    def __init__(self, user_id, username, email, password_hash=None, medical_condition=None, 
                 created_at=None, last_login=None, age=None, weight=None, height=None, 
                 calorie_target=None, goal=None, profile_completed=False, role='patient', 

                 education_details=None, assigned_patients=None, gender=None, diet_type=None, allergies=None):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.password_hash = password_hash or ""
        self.medical_condition = medical_condition
        self.created_at = created_at or datetime.now()
        self.last_login = last_login
        self.age = age
        self.gender = gender
        self.weight = weight  # in kg
        self.height = height  # in cm
        self.diet_type = diet_type
        self.allergies = allergies
        self.calorie_target = calorie_target
        self.goal = goal
        self.profile_completed = profile_completed
        self.role = role  # 'patient' or 'dietitian'
        self.education_details = education_details or {}
        self.assigned_patients = assigned_patients or []

    
    def get_id(self):
        """Required by Flask-Login"""
        return str(self.user_id)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password is correct"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Convert user to dictionary for database storage"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'medical_condition': self.medical_condition,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'age': self.age,
            'gender': self.gender,
            'weight': self.weight,
            'height': self.height,
            'diet_type': self.diet_type,
            'allergies': self.allergies,
            'calorie_target': self.calorie_target,
            'goal': self.goal,
            'profile_completed': self.profile_completed,
            'role': self.role,
            'education_details': self.education_details,
            'assigned_patients': self.assigned_patients
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create user from dictionary"""
        return cls(
            user_id=data.get('user_id'),
            username=data.get('username'),
            email=data.get('email'),
            password_hash=data.get('password_hash'),
            medical_condition=data.get('medical_condition'),
            created_at=data.get('created_at'),
            last_login=data.get('last_login'),
            age=data.get('age'),
            gender=data.get('gender'),
            weight=data.get('weight'),
            height=data.get('height'),
            diet_type=data.get('diet_type'),
            allergies=data.get('allergies'),
            calorie_target=data.get('calorie_target'),
            goal=data.get('goal'),
            profile_completed=data.get('profile_completed', False),
            role=data.get('role', 'patient'),
            education_details=data.get('education_details', {}),
            assigned_patients=data.get('assigned_patients', [])
        )

class UserManager:
    """Manages user operations with MongoDB"""
    
    def __init__(self, db):
        self.db = db
        if db is not None:
            self.users = db['users']
        else:
            # Create dummy collection for when db is None
            class DummyCollection:
                def find_one(self, *args, **kwargs): return None
                def find(self, *args, **kwargs): return []
                def insert_one(self, *args, **kwargs): return type('obj', (object,), {'inserted_id': None})()
                def update_one(self, *args, **kwargs): return type('obj', (object,), {'modified_count': 0})()
                def delete_one(self, *args, **kwargs): return type('obj', (object,), {'deleted_count': 0})()
            self.users = DummyCollection()
    
    def create_user(self, username, email, password, medical_condition=None):
        """Create a new user"""
        # Check if username or email already exists
        if self.users.find_one({'$or': [{'username': username}, {'email': email}]}):
            return None, "Username or email already exists"
        
        # Create new user
        user_id = str(uuid.uuid4())
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            medical_condition=medical_condition
        )
        user.set_password(password)
        
        # Save to database
        self.users.insert_one(user.to_dict())
        return user, None
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        user_data = self.users.find_one({'user_id': user_id})
        if user_data:
            return User.from_dict(user_data)
        return None
    
    def get_user_by_username(self, username):
        """Get user by username"""
        user_data = self.users.find_one({'username': username})
        if user_data:
            return User.from_dict(user_data)
        return None
    
    def get_user_by_email(self, email):
        """Get user by email"""
        user_data = self.users.find_one({'email': email})
        if user_data:
            return User.from_dict(user_data)
        return None
    
    def update_last_login(self, user_id):
        """Update user's last login time"""
        self.users.update_one(
            {'user_id': user_id},
            {'$set': {'last_login': datetime.now()}}
        )
    
    def update_medical_condition(self, user_id, condition):
        """Update user's medical condition"""
        self.users.update_one(
            {'user_id': user_id},
            {'$set': {'medical_condition': condition}}
        )
    

    def update_user_profile(self, user_id, age=None, weight=None, height=None, calorie_target=None, goal=None, gender=None, diet_type=None, allergies=None):
        """Update user's profile with health metrics and goals"""
        update_data = {'profile_completed': True}
        if age is not None:
            update_data['age'] = age
        if gender is not None:
            update_data['gender'] = gender
        if weight is not None:
            update_data['weight'] = weight
        if height is not None:
            update_data['height'] = height
        if diet_type is not None:
            update_data['diet_type'] = diet_type
        if allergies is not None:
            update_data['allergies'] = allergies
        if calorie_target is not None:
            update_data['calorie_target'] = calorie_target
        if goal is not None:
            update_data['goal'] = goal
        
        self.users.update_one(
            {'user_id': user_id},
            {'$set': update_data}
        )
    
    def get_all_users(self):
        """Get all users (for admin purposes)"""
        users_data = self.users.find({})
        return [User.from_dict(user_data) for user_data in users_data]
    
    def delete_user(self, user_id):
        """Delete user (for admin purposes)"""
        result = self.users.delete_one({'user_id': user_id})
        return result.deleted_count > 0
