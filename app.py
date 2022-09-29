from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import sqlite3
import requests
import json


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure sqlite3 Library to use SQLite database
con = sqlite3.connect("anime.db", check_same_thread=False)
db = con.cursor()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Decorater for login required
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# Get username
def username():
    user_id = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = ?", [user_id]).fetchone()[0]
    return username

@app.route("/")
@login_required
def index():

    response = requests.get("https://api.jikan.moe/v4/top/anime", params={"limit": 20})

    animes = response.json()["data"]

    return render_template("index.html", username=username(), animes=animes)


# DONE
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validation
        if not username:
            flash("must provide username", category="error")
        elif db.execute("SELECT * FROM users WHERE username = ?", [username]).fetchone():
            flash("username already exists", category="error")
        elif not password:
            flash("must provide password", category="error")
        elif not confirmation:
            flash("must confirm password", category="error")
        elif password != confirmation:
            flash("passwords does not match", category="error")
        elif not len(password) >= 8:
            flash("password should contain 8 characters", category="error")
        elif not any(char.isdigit() for char in password):
            flash("password should contain numbers", category="error")
        elif not any(not char.isalnum() for char in password):
            flash("password should contain special characters", category="error")

        else:
            pass_hash = generate_password_hash(password)
            # inserting user details to users database
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", [username, pass_hash])
            id = db.execute("SELECT id FROM users WHERE username = ?", [username]).fetchone()[0]
            con.commit()

            # Logging IN the user
            session["user_id"] = id
            return redirect("/")

        return render_template("register.html")

    else:
        return render_template("register.html")

# DONE
@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("must provide username", category="error")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("must provide password", category="error")

        else:
            # Query database for username
            rows = db.execute("SELECT * FROM users WHERE username = ?", [request.form.get("username")]).fetchone()

            # Ensure username exists and password is correct
            if not rows or not check_password_hash(rows[2], request.form.get("password")):
                flash("invalid username and/or password", category="error")
                return render_template("login.html")

            # Remember which user has logged in
            session["user_id"] = rows[0]

            # Redirect user to home page
            return redirect("/")

        return render_template("login.html")

    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/search")
@login_required
def search():

    def jprint(obj):
        #create a formatted string of the Python JSON object
        text = json.dumps(obj, sort_keys=True, indent=4)
        print(text)

    keyword = request.args.get("keyword")
    print(keyword)

    response = requests.get("https://api.jikan.moe/v4/anime", params={"q": keyword, "limit": 12})

    animes = response.json()["data"]

    if response.json()["pagination"]["items"]["count"] == 0:
        return render_template("apology.html")

    return render_template("result.html", username=username(), animes=animes, limit=9)

@app.route("/info")
@login_required
def info():

    user_id = session["user_id"]

    anime_id = request.args.get("anime")
    print(anime_id)

    if not anime_id:
        return render_template("apology.html")

    response = requests.get(f"https://api.jikan.moe/v4/anime/{anime_id}")
    
    anime = response.json()["data"]


    if (anime["trailer"]["url"] != None):
        trailer = True
    else:
        trailer = False
    
    def exists(key):
        if (anime[key]):
            return True
        return False
    
    anime_title = requests.utils.quote(anime["title"])

    link = "https://zoro.to/search?keyword={anime}".format(anime=anime_title)

    # Check if anime already in watch-list
    id = db.execute("SELECT anime_id FROM watch_list WHERE user_id = ? AND anime_id = ?", [user_id, anime_id]).fetchone()
    print(id)

    if id:
        inList = True
    else:
        inList = False
    print(inList)

    return render_template("info.html", username=username(), anime=anime, trailer=trailer, link=link, inList=inList)


@app.route("/watch-list", methods=["GET", "POST"])
@login_required
def watch_list():
    user_id = session["user_id"]

    if request.method == "POST":
        
        if request.form.get("add-anime"):
            anime_id = request.form.get("add-anime")
            db.execute("INSERT INTO watch_list (user_id, anime_id) VALUES(?, ?)", [user_id, anime_id])
            con.commit()

        else:
            anime_id = request.form.get("remove-anime")
            db.execute("DELETE FROM watch_list WHERE anime_id = ?", [anime_id])


        if not anime_id or int(anime_id) < 1:
            return render_template("apology.html", username=username())

        return redirect("watch-list")

    else:
        anime_ids = db.execute("SELECT anime_id FROM watch_list WHERE user_id = ?", [user_id])
        anime_ids = [item[0] for item in anime_ids.fetchall()]

        animes = []
        for anime_id in anime_ids:
            animes.append(requests.get(f"https://api.jikan.moe/v4/anime/{anime_id}").json()["data"])

        return render_template("watch-list.html", username=username(), animes=animes)