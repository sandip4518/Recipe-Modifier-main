from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Optional
import re

class RegistrationForm(FlaskForm):
    """User registration form"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=20, message='Username must be between 3 and 20 characters')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    
    medical_condition = SelectField('Medical Condition (Optional)', 
                                  choices=[
                                      ('', 'Select a condition (optional)'),
                                      ('diabetes', 'Diabetes'),
                                      ('hypertension', 'Hypertension'),
                                      ('heart_disease', 'Heart Disease'),
                                      ('celiac', 'Celiac Disease'),
                                      ('gluten_intolerance', 'Gluten Intolerance'),
                                      ('lactose_intolerance', 'Lactose Intolerance'),
                                      ('egg_allergy', 'Egg Allergy'),
                                      ('peanut_allergy', 'Peanut Allergy'),
                                      ('soy_allergy', 'Soy Allergy'),
                                      ('corn_allergy', 'Corn Allergy'),
                                      ('obesity', 'Obesity'),
                                      ('cholesterol', 'High Cholesterol')
                                  ])
    
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        """Custom validation for username"""
        # Must only contain letters, numbers, and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', username.data):
            raise ValidationError('Username can only contain letters, numbers, and underscores')
        
        # Must start with a letter
        if not re.match(r'^[a-zA-Z]', username.data):
            raise ValidationError('Username must start with a letter')
        
        # Must contain at least one letter (not purely numeric or underscores)
        if not re.search(r'[a-zA-Z]', username.data):
            raise ValidationError('Username must contain at least one letter')
    
    def validate_password(self, password):
        """Custom validation for password strength"""
        if len(password.data) < 6:
            raise ValidationError('Password must be at least 6 characters long')
        
        # Check for at least one letter and one number
        if not re.search(r'[A-Za-z]', password.data):
            raise ValidationError('Password must contain at least one letter')
        
        if not re.search(r'\d', password.data):
            raise ValidationError('Password must contain at least one number')

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username or Email', validators=[
        DataRequired(message='Please enter your username or email')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Please enter your password')
    ])
    
    remember_me = BooleanField('Remember Me')
    
    submit = SubmitField('Login')

class ProfileUpdateForm(FlaskForm):
    """Profile update form"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address')
    ])
    
    medical_condition = SelectField('Medical Condition', 
                                  choices=[
                                      ('', 'Select a condition'),
                                      ('diabetes', 'Diabetes'),
                                      ('hypertension', 'Hypertension'),
                                      ('heart_disease', 'Heart Disease'),
                                      ('celiac', 'Celiac Disease'),
                                      ('gluten_intolerance', 'Gluten Intolerance'),
                                      ('lactose_intolerance', 'Lactose Intolerance'),
                                      ('egg_allergy', 'Egg Allergy'),
                                      ('peanut_allergy', 'Peanut Allergy'),
                                      ('soy_allergy', 'Soy Allergy'),
                                      ('corn_allergy', 'Corn Allergy'),
                                      ('obesity', 'Obesity'),
                                      ('cholesterol', 'High Cholesterol')
                                  ])
    
    submit = SubmitField('Update Profile')

class ChangePasswordForm(FlaskForm):
    """Change password form"""
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Please enter your current password')
    ])
    
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    
    submit = SubmitField('Change Password')
    
    def validate_new_password(self, new_password):
        """Custom validation for new password strength"""
        if len(new_password.data) < 6:
            raise ValidationError('Password must be at least 6 characters long')
        
        # Check for at least one letter and one number
        if not re.search(r'[A-Za-z]', new_password.data):
            raise ValidationError('Password must contain at least one letter')
        
        if not re.search(r'\d', new_password.data):
            raise ValidationError('Password must contain at least one number')

class ProfileCompletionForm(FlaskForm):
    """Profile completion form for new users"""
    age = IntegerField('Age', validators=[
        DataRequired(message='Please enter your age'),
        NumberRange(min=13, max=120, message='Age must be between 13 and 120')
    ])
    
    weight = IntegerField('Weight (kg)', validators=[
        DataRequired(message='Please enter your weight'),
        NumberRange(min=20, max=300, message='Weight must be between 20 and 300 kg')
    ])
    

    height = IntegerField('Height (cm)', validators=[
        DataRequired(message='Please enter your height'),
        NumberRange(min=50, max=250, message='Height must be between 50 and 250 cm')
    ])
    
    gender = SelectField('Gender', 
                        choices=[
                            ('', 'Select your gender'),
                            ('male', 'Male'),
                            ('female', 'Female'),
                            ('other', 'Other')
                        ],
                        validators=[DataRequired(message='Please select your gender')])
    
    diet_type = StringField('Diet Type (Optional)', validators=[Optional(), Length(max=50)])
    
    allergies = StringField('Allergies (Optional)', validators=[Optional(), Length(max=200)])
    
    calorie_target = IntegerField('Daily Calorie Target', validators=[
        DataRequired(message='Please enter your calorie target'),
        NumberRange(min=800, max=5000, message='Calorie target must be between 800 and 5000')
    ])
    
    goal = SelectField('Fitness Goal', 
                      choices=[
                          ('', 'Select your goal'),
                          ('lose_weight', '🔥 Lose Weight'),
                          ('gain_muscle', '💪 Gain Muscle'),
                          ('maintain_fitness', '⚖️ Maintain Fitness'),
                          ('improve_health', '❤️ Improve Overall Health')
                      ],
                      validators=[DataRequired(message='Please select a fitness goal')])
    
    submit = SubmitField('Complete Profile')


