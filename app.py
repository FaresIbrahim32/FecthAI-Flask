from flask import Flask, render_template, request, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
from pydantic import BaseModel, ValidationError
import json
# Add this near the top of your app.py
# Football Data API Key - ideally this would be in environment variables
FOOTBALL_API_KEY = "b134a5b6d3e240b4b594c8e5ff9311d0"  # Replace with your actual API key
FOOTBALL_API_URL = "https://api.football-data.org/v4"

# Add this near the top with your other constants
ASI1_API_KEY = "sk_21b370999a4e40b79302b09273dd39513b9363905b3844698f8052cfa32672e1"
ASI1_API_URL = "https://api.asi1.ai/v1/chat/completions"
ASI1_MODEL = "asi1-mini"


# Initialize Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "supersecretkey"

# Initialize database and login manager
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User model
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    
# Team model

class Teams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(250), nullable=False)
    country = db.Column(db.String(250), nullable=False)
    api_team_id = db.Column(db.Integer,nullable=True)  # ID from the football API
    competition_id = db.Column(db.String(20),nullable=True)  # Competition/league ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# Create database
with app.app_context():
    db.create_all()

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

# Home route
@app.route("/")
def home():
    return render_template("home.html")

# Register route
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if Users.query.filter_by(username=username).first():
            return render_template("sign_up.html", error="Username already taken!")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        new_user = Users(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))
    
    return render_template("sign_up.html")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

# Protected dashboard route

@app.route("/dashboard")
@login_required
def dashboard():
    # Get user's teams
    user_teams = Teams.query.filter_by(user_id=current_user.id).all()
    
    # Get data for first team if exists
    dashboard_data = {}
    if user_teams:
        first_team = user_teams[0]
        if first_team.api_team_id:
            matches_data = get_team_matches(first_team.api_team_id, limit=10)
            
            if matches_data and 'matches' in matches_data:
                # Sort matches by date (recent first)
                sorted_matches = sorted(
                    matches_data['matches'],
                    key=lambda x: x.get('utcDate', ''),
                    reverse=True  # Most recent first
                )
                
                # Take up to 3 finished matches for "Recent Matches"
                recent_matches = [m for m in sorted_matches if m.get('status') == 'FINISHED'][:3]
                dashboard_data['recent_matches'] = recent_matches
                
                # Take up to 3 upcoming matches for "Upcoming Fixtures"
                upcoming_matches = [m for m in sorted_matches if m.get('status') != 'FINISHED'][:3]
                dashboard_data['upcoming_matches'] = upcoming_matches
            
            if first_team.competition_id:
                dashboard_data['standings'] = get_league_standings(first_team.competition_id)
    
    return render_template(
        "dashboard.html", 
        username=current_user.username,
        user_teams=user_teams,
        dashboard_data=dashboard_data
    )
# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route('/team', methods=["GET", "POST"])
@login_required
def get_team():
    if request.method == "POST":
        team_name = request.form.get("teamname")
        country = request.form.get("country")
        api_team_id = request.form.get("api_team_id")
        competition_id = request.form.get("competition_id")
        
        # Validate inputs
        if not team_name or not country:
            return render_template("team.html", error="Team name and country are required")
        
        # Create a new team with the current user's ID
        new_team = Teams(
            team_name=team_name,
            country=country,
            api_team_id=api_team_id,
            competition_id=competition_id,
            user_id=current_user.id
        )
        
        db.session.add(new_team)
        db.session.commit()
        
        # Redirect to dashboard after successfully adding the team
        return redirect(url_for("dashboard"))
    
    # If GET request, just show the form
    return render_template("team.html")

@login_required
@app.route('/all_teams',methods=["GET","POST"])
def get_teams():
    user_teams = Teams.query.filter_by(user_id=current_user.id).all()
    
    return render_template('dashboard.html', user_teams=user_teams)

@app.route('/get_team/<int:team_id>', methods=["GET", "POST"])
@login_required
def get_my_team(team_id):
    # Get the team using SQLAlchemy
    team = Teams.query.filter_by(id=team_id, user_id=current_user.id).first_or_404()
    
    # If you want to display additional team data from the API
    team_info = None
    if team.api_team_id:
        team_info = get_team_info(team.api_team_id)
    
    return render_template("team_detail.html", team=team, team_info=team_info)

@app.route('/delete_team/<int:team_id>', methods=["GET", "POST"])
@login_required
def delete_team(team_id):
    deleted_team = Teams.query.filter_by(team_id=team_id).first()
    db.session.delete(deleted_team)
    db.session.commit()
    
    return render_template('all_teams.html')

@app.route('/competition_scorers/<competition_id>')
@login_required
def competition_scorers(competition_id):
    """Display top scorers for a competition"""
    headers = {'X-Auth-Token': FOOTBALL_API_KEY}
    url = f"{FOOTBALL_API_URL}/competitions/{competition_id}/scorers"
    
    # Optional: add limit parameter
    params = {'limit': 10}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        scorers_data = response.json()
        
        # Debug the response structure
        print(f"API Response structure: {scorers_data.keys()}")
        
        return render_template(
            'scorers.html',
            competition_id=competition_id,
            scorers_data=scorers_data
        )
    except requests.exceptions.RequestException as e:
        print(f"Error fetching scorers data: {e}")
        return render_template(
            'scorers.html',
            competition_id=competition_id,
            error=str(e)
        )

def get_team_matches(team_id, limit=10):
    """Get recent and upcoming matches for a team"""
    headers = {'X-Auth-Token': FOOTBALL_API_KEY}
    url = f"{FOOTBALL_API_URL}/teams/{team_id}/matches"
    
    # Get both finished and scheduled matches, with a larger limit
    # so we can get a mix of both types
    params = {
        'limit': limit,
        'status': 'FINISHED,SCHEDULED'  # Get both finished and upcoming matches
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching team matches: {e}")
        return None

def get_team_info(team_id):
    """Get detailed information about a team"""
    headers = {'X-Auth-Token': FOOTBALL_API_KEY}
    url = f"{FOOTBALL_API_URL}/teams/{team_id}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching team info: {e}")
        return None
        
def get_league_standings(competition_id):
    """Get standings for a specific league/competition"""
    headers = {'X-Auth-Token': FOOTBALL_API_KEY}
    url = f"{FOOTBALL_API_URL}/competitions/{competition_id}/standings"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching standings: {e}")
        return None
    
def get_llm_response(question):
    """Get a response from ASI1 Mini LLM"""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {ASI1_API_KEY}'
    }
    
    payload = json.dumps({
        "model": ASI1_MODEL,
        "messages": [
            {
                "role": "user",
                "content": question
            }
        ],
        "temperature": 0,
        "stream": False,
        "max_tokens": 0
    })
    
    try:
        response = requests.request("POST", ASI1_API_URL, headers=headers, data=payload)
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return content
        else:
            print(f"ASI1 API error: {response.status_code}")
            print(response.text)
            return f"Error: Could not get response from ASI1 API (Status: {response.status_code})"
    except Exception as e:
        print(f"Exception in get_llm_response: {str(e)}")
        return f"Error: {str(e)}"
    
@app.route('/ask_chatbot', methods=["GET", "POST"])
@login_required
def ask_chatbot():
    response_text = ""
    question = ""
    
    if request.method == "POST":
        question = request.form.get("question", "")
        if question:
            # Add soccer context to the question
            user_teams = Teams.query.filter_by(user_id=current_user.id).all()
            team_names = [team.team_name for team in user_teams]
            
            context = f"The user is asking about soccer. They follow these teams: {', '.join(team_names) if team_names else 'No specific teams'}. "
            
            # Get response from LLM
            response_text = get_llm_response(context + question)
    
    return render_template(
        "chatbot.html",
        username=current_user.username,
        question=question,
        response=response_text
    )     

if __name__ == "__main__":
    app.run(debug=True)
