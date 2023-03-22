"""
Info for correction

For admin login, one existing admin is 'admin1' with password 'abc123',
other admins can be created

I have commented features in routes which I would like to note and linked to resources

Do not bother to check the following html files, as they do not contain any interesting jinja2:
- add_game_form.html
- admin_login.html
- admin.html
- new_admin_form.html
- login.html
- register.html


I frequently used the following pages (more specific pages are commented where they are used):
- https://wtforms.readthedocs.io/en/2.3.x/fields/
-
"""


from flask import Flask, render_template, session, redirect, url_for, g, request
from flask_session import Session
from database import get_db, close_db
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename  # File upload
from forms import SearchForm, GenreForm, WriteReviewForm, RegistrationForm, LoginForm, AdminLoginForm, AddGameForm, DeleteGameForm, DeleteReviewForm, DeleteUserForm, UploadImageForm, AddNewAdminForm
from functools import wraps
from datetime import datetime
import os  # File upload


app = Flask(__name__)
app.teardown_appcontext(close_db)
app.config["SECRET_KEY"] = "this-is-the-secret-key"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.before_request
def logged_in_user():
    g.user = session.get("user_id", None)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        # Checks if user is an admin also
        if g.user is None or g.user == "admin":
            return redirect(url_for("login", next=request.url))
        return view(*args, **kwargs)
    return wrapped_view

# Same as login_required, but requires user to be admin


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user != "admin":
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped_view


# Used in writing reviews and registering an account
censored_words = ["fuck", "cunt", "shit", "cum", "bitch", "cock", "nigg", "fag"]

@app.route("/")
def index():
    db = get_db()
    # Displays games that have more than 2 reviews
    games = db.execute("""SELECT * FROM games
                        WHERE game_id IN (
                            SELECT game_id
                            FROM reviews
                            GROUP BY game_id
                            HAVING COUNT(*) > 2
                        )
                        ORDER BY release_date DESC""").fetchall()
    return render_template("index.html", title="Home", games=games)


@app.route("/discover/<int:order>", methods=["GET", "POST"])
def discover(order):
    # Passed in from jinja to determine how to order games displayed
    ordering = ["release_date DESC", "name ASC", "avg_score DESC"]
    order_by = ordering[order]
    search_form = SearchForm()
    genre_form = GenreForm()
    db = get_db()
    # Take all genres from the database to display & select
    genres = db.execute(
        """SELECT DISTINCT genre FROM games ORDER BY genre;""").fetchall()
    for dict in genres:
        genre_form.genreFilter.choices.append(dict["genre"])
    games = db.execute("""SELECT * FROM games ORDER BY """ + order_by + """;""").fetchall()
    # https://stackoverflow.com/questions/18290142/multiple-forms-in-a-single-page-using-flask-and-wtforms
    if search_form.validate_on_submit() and search_form.submitSearch.data:
        search = search_form.search.data
        # If user searches nothing, ignores their search
        if search == "":
            games = db.execute("""SELECT * FROM games ORDER BY """ + order_by + """;""").fetchall()
        # Displays their search
        else:
            # https://code-boxx.com/search-results-python-flask/
            games = db.execute(
                """SELECT * FROM games WHERE name LIKE ?;""", (search+"%",)).fetchall()
    #Form for user filtering by game genre
    elif genre_form.validate_on_submit() and genre_form.submitGenre.data:
        genreFilter = genre_form.genreFilter.data
        # If user selects None, ignores filter
        if genreFilter == "None":
            games = db.execute("""SELECT * FROM games ORDER BY """ + order_by + """;""").fetchall()
        else:
            games = db.execute(
                """SELECT * FROM games WHERE genre=? ORDER BY """ + order_by + """;""", (genreFilter,)).fetchall()
    return render_template("discover.html", title="Discover", 
                            search_form=search_form, genre_form=genre_form, games=games, order=order)


# Takes in game_id from jinja in index.html
@app.route("/game/<int:game_id>", methods=["GET", "POST"])
def game(game_id):
    db = get_db()
    # Fetches data on the game which the user searched to display on the
    game = db.execute(
        """SELECT * FROM games WHERE game_id=?;""", (game_id,)).fetchone()
    # Fetches review data for the 8 most recent games for this game
    # Does not display reviews with a low helpfulness score
    reviews = db.execute("""
        SELECT *
        FROM reviews
        WHERE game_id = ?
        AND helpfulness > -5
        ORDER BY date DESC
        LIMIT 8;""", (game_id,)).fetchall()
    return render_template("game.html", title=game["name"], game=game, reviews=reviews)

# Takes in game_id, review_id and helpfulness when user clicks the helpful/not helpful link in game.html


@app.route("/game/<int:game_id>/<int:review_id>/helpfulness/<int:helpfulness>")
@login_required  # Admins not allowed access
def helpfulness(game_id, review_id, helpfulness):
    # Keeps track of helpfulness ratings in the session
    if "ratings" not in session:
        session["ratings"] = {}
    # Updates if the user has not given a rating, or changed their rating
    if review_id not in session["ratings"] or helpfulness != session["ratings"][review_id]:
        # Stores their score in session
        session["ratings"][review_id] = helpfulness
        # Converts helpfulness to a working score if 0 (not helpful)
        if helpfulness == 0:
            helpfulness = -1
        db = get_db()
        # Updates helpfulness score if user is not voting for their own review
        reviewer = db.execute(
            """SELECT user_id FROM reviews WHERE review_id=?;""", (review_id,)).fetchone()
        # Checks if user is voting for themself
        if reviewer["user_id"] != g.user:
            # Updates review's helpfulness
            db.execute("""UPDATE reviews
                        SET helpfulness = helpfulness+?
                        WHERE review_id=?;""", (helpfulness, review_id))
            db.commit()
    # Redirects back, does not have its own page
    return redirect(url_for("game", game_id=game_id))


# Takes in game_id from game.html
@app.route("/review/<int:game_id>", methods=["GET", "POST"])
@login_required  # Admins not allowed to leave reviews
def write_review(game_id):
    form = WriteReviewForm()
    if form.validate_on_submit():
        review_text = form.review_text.data
        user_score = form.user_score.data
        db = get_db()
        user_reviewed = db.execute("""SELECT * FROM reviews
                                WHERE game_id = ? AND user_id = ?;""", (game_id, g.user)).fetchone()
        # Checks if review contains censored words
        censor = False
        alter_review = review_text.lower()
        for word in censored_words:
            if word in alter_review:
                censor = True
        # Checks if user has already reviewed this game
        if user_reviewed is not None:
            form.review_text.errors.append(
                "You have already reviewed this game")
        # Returns error if review is vulgar
        elif censor:
            form.review_text.errors.append("Please do not use vulgar language")
        else:
            # Makes a date format suitable for SQLites
            current_date = "20" + (datetime.now().strftime("%y-%m-%d"))
            # Inserts reviews into database
            db.execute("""INSERT INTO reviews (user_id, game_id, date, description, score, helpfulness)
            VALUES (?, ?, ?, ?, ?, 0);""", (g.user, game_id, current_date, review_text, user_score))
            db.commit()
            # Updates the average user score for the game
            db.execute("""UPDATE games SET avg_score =
                ROUND(((SELECT AVG(score)
                FROM reviews
                WHERE game_id = ?) * 10), 0)
            WHERE game_id = ?;""", (game_id, game_id))
            db.commit()
            return redirect(url_for("game", game_id=game_id))
    return render_template("review_form.html", title="Leave a Review!", form=form)


@app.route("/profile", methods=["GET", "POST"])
@login_required  # Admins cannot have profiles
def profile():
    db = get_db()
    user_reviews = db.execute("""SELECT * FROM reviews AS r
                                JOIN games AS g
                                ON r.game_id = g.game_id
                                WHERE user_id=?;""", (g.user,)).fetchall()
    # Calculates the average score the user has given in their reviews
    avg_score = db.execute(
        """SELECT AVG(score) FROM reviews WHERE user_id=?;""", (g.user,)).fetchone()
    return render_template("profile.html", title=g.user, user_reviews=user_reviews, avg_score=avg_score)

# ---------------- ADMIN ROUTES ----------------

# All have the admin_required function


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_profile():
    # Hub for links to other admin controls
    return render_template("admin.html", title="Admin Commands")

# ---------- EDITING ----------


@app.route("/admin/add-game", methods=["GET", "POST"])
@admin_required
def add_game():
    form = AddGameForm()
    if form.validate_on_submit():
        name = form.name.data
        genre = form.genre.data
        release_date = form.release_date.data
        developer = form.developer.data
        publisher = form.publisher.data
        image = form.image.data
        description = form.description.data
        db = get_db()
        # Adds new game to database, with "None" for avg_score, as there will be no reviews
        db.execute("""INSERT INTO games
                (name, genre, release_date, developer,
                 publisher, avg_score, image, description)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?);""",
                (name, genre, release_date, developer, publisher, "None", image, description))
        db.commit()
        # Redirects to the upload_image route so the game can have an accompanying image
        return redirect(url_for("upload_image"))
    return render_template("add_game_form.html", title="Add a game", form=form)


@app.route("/admin/delete-game", methods=["GET", "POST"])
@admin_required
def delete_game():
    form = DeleteGameForm()
    db = get_db()
    games = db.execute("""SELECT * FROM games;""").fetchall()
    if form.validate_on_submit():
        game_id = form.game_id.data
        # Deletes the game and all accompanying reviews from the database
        db.execute("""DELETE FROM games WHERE game_id = ?;""", (game_id,))
        db.execute("""DELETE FROM reviews WHERE game_id = ?;""", (game_id,))
        db.commit()
    return render_template("delete_game_form.html", title="Delete a game", form=form, games=games)


@app.route("/admin/delete-user", methods=["GET", "POST"])
@admin_required
def delete_user():
    form = DeleteUserForm()
    db = get_db()
    active_users = db.execute("""SELECT DISTINCT user_id FROM reviews""")
    unhelpful_users = []
    # For each user who has reviewed
    for user in active_users:
        avg_helpfulness = db.execute("""SELECT AVG(helpfulness) FROM reviews
                                        WHERE user_id=?;""", (user["user_id"],)).fetchone()
        num_reviews = db.execute("""SELECT COUNT(*) FROM reviews
                                    WHERE user_id=?;""", (user["user_id"],)).fetchone()
        # If they have an average helpfulness of 5 or less, and have left 3+ reviews
        if avg_helpfulness[0] <= -5 and num_reviews[0] > 3:
            unhelpful_users.append(user["user_id"])
    if form.validate_on_submit():
        user_id = form.user_id.data
        games_reviewed = db.execute(
            """SELECT game_id FROM reviews WHERE user_id=?;""", (user_id,)).fetchall()
        # Deletes the user, and their reviews
        db.execute("""DELETE FROM users WHERE user_id=?;""", (user_id,))
        db.execute("""DELETE FROM reviews WHERE user_id=?;""", (user_id,))
        db.commit()
        # Updates the score for each game the user has reviewed
        for game in games_reviewed:
            db.execute("""UPDATE games SET avg_score =
                    ROUND(((SELECT AVG(score)
                    FROM reviews
                    WHERE game_id = ?) * 10), 0)
                WHERE game_id = ?;""", (game["game_id"], game["game_id"]))
        db.commit()
    return render_template("delete_user_form.html", title="Delete a User", form=form, unhelpful_users=unhelpful_users)

# Does not immediately display the review being deleted, but when checked again, it has


@app.route("/admin/delete-review", methods=["GET", "POST"])
@admin_required
def delete_review():
    form = DeleteReviewForm()
    db = get_db()
    reviews = db.execute("""SELECT * FROM reviews AS r
                        JOIN games AS g
                        ON g.game_id = r.game_id
                        ORDER BY g.game_id;""").fetchall()
    if form.validate_on_submit():
        review_id = form.review_id.data
        review = db.execute(
            """SELECT * FROM reviews WHERE review_id = ?;""", (review_id,)).fetchone()
        game_id = review["game_id"]
        # Deletes a review
        db.execute("""DELETE FROM reviews WHERE review_id = ?;""", (review_id,))
        db.commit()
        # Updates avg_score after the review is deleted
        db.execute("""UPDATE games SET avg_score =
                ROUND(((SELECT AVG(score)
                FROM reviews
                WHERE game_id = ?) * 10), 0)
            WHERE game_id = ?;""", (game_id, game_id))
        db.commit()
    return render_template("delete_review_form.html", title="Delete a Review", form=form, reviews=reviews)

# https://flask.palletsprojects.com/en/2.2.x/patterns/fileuploads/


# Allowed file types to be uploaded
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Splits file so that the filename can be checked


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# File upload


@app.route("/admin/upload-image", methods=["GET", "POST"])
@admin_required
def upload_image():
    form = UploadImageForm()
    if form.validate_on_submit():
        file = form.image.data
        # If the user does not select a file
        if file is None or file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Saves file to static folder using the os module
            file.save(os.path.join(r'static', filename))
            # Redirects back to admin profile
            return redirect(url_for('admin_profile'))
    return render_template("upload_image_form.html", title="Upload an Image", form=form)


@app.route("/new-admin", methods=["GET", "POST"])
@admin_required
def new_admin():
    # Effectively a register form
    form = AddNewAdminForm()
    if form.validate_on_submit():
        admin_id = form.admin_id.data
        password = form.password.data
        db = get_db()
        clashing_admin = db.execute("""
            SELECT * FROM admins
            WHERE admin_id = ?;
            """, (admin_id,)).fetchone()
        if clashing_admin is not None:
            form.admin_id.errors.append("Username already taken")
        else:
            db.execute("""
            INSERT INTO admins (admin_id, password)
            VALUES (?, ?);
            """, (admin_id, generate_password_hash(password)))
            db.commit()
    return render_template("new_admin_form.html", title="Add New Admin", form=form)

# ---------- MONITORING ----------


@app.route("/admin/see-reviews")
@admin_required
def see_reviews():
    db = get_db()
    # Displays all reviews and their game, ordered by game
    reviews = db.execute("""SELECT * FROM reviews AS r
                        JOIN games AS g
                        ON g.game_id = r.game_id
                        ORDER BY g.game_id;""").fetchall()
    return render_template("see_reviews.html", title="All Reviews", reviews=reviews)


@app.route("/admin/see-users")
@admin_required
def see_users():
    db = get_db()
    # Displays all users
    users = db.execute("""SELECT * FROM users;""").fetchall()
    inactive_users = db.execute("""SELECT * FROM users
                                WHERE user_id NOT IN
                                (SELECT user_id FROM reviews);""").fetchall()
    return render_template("see_users.html", title="All Users", users=users, inactive_users=inactive_users)


# ---------------- LOGIN AND REGISTRATION ----------------


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user_id = form.user_id.data
        password = form.password.data
        db = get_db()
        clashing_user = db.execute("""
			SELECT * FROM users
			WHERE user_id = ?;
			""", (user_id,)).fetchone()
        censor = False
        alter_id = user_id.lower()
        for word in censored_words:
            if word in alter_id:
                censor = True
        if clashing_user is not None:
            form.user_id.errors.append("Username already taken")
        # User cannot name themselves after an admin
        elif "admin" in user_id:
            form.user_id.errors.append("Username cannot contain 'admin'")
        elif censor:
            form.user_id.errors.append(
                "Please do not use vulgar language in your name")
        else:
            db.execute("""
            INSERT INTO users (user_id, password)
            VALUES (?, ?);
            """, (user_id, generate_password_hash(password)))
            db.commit()
            return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)


# Pretty much same as screenshots
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_id = form.user_id.data
        password = form.password.data
        db = get_db()
        existing_user = db.execute("""SELECT * FROM users
                                    WHERE user_id=?;""", (user_id,)).fetchone()
        if existing_user is None:
            form.user_id.errors.append("User ID or password details are incorrect!")
        elif not check_password_hash(existing_user["password"], password):
            form.password.errors.append("User ID or password details are incorrect!")
        else:
            session.clear()
            session["user_id"]=user_id
            next_page=request.args.get("next")
            if not next_page:
                next_page=url_for("index")
            return redirect(next_page)
    return render_template("login.html", title="Login", form=form)

# Same as login above but for admin table
@ app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        admin_id = form.admin_id.data
        password = form.password.data
        db = get_db()
        existing_admin = db.execute("""SELECT * FROM admins WHERE admin_id=?;""", (admin_id,)).fetchone()
        if existing_admin is None:
            form.admin_id.errors.append("Admin ID is incorrect!")
        elif not check_password_hash(existing_admin["password"], password):
            form.admin_id.errors.append("Password details are incorrect!")
        else:
            session.clear()
            session["user_id"]="admin"
            return redirect(url_for("admin_profile"))
    return render_template("admin_login.html", title="Admin Login", form=form)

@ app.route("/logout")
def logout():
	session.clear()
	return redirect(url_for("index"))
