from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, RadioField, SelectField, TextAreaField, IntegerField, PasswordField, DateField # DONT FORGET OTHER FIELDS
from wtforms.validators import InputRequired, Length, EqualTo

from flask_wtf.file import FileField, FileAllowed, FileRequired


class SearchForm(FlaskForm):
    search = StringField()
    submitSearch = SubmitField("Search")

class GenreForm(FlaskForm):
    genreFilter = RadioField("Genres:", choices=["None"], default="None")
    submitGenre = SubmitField("Filter by Genre")

class WriteReviewForm(FlaskForm):
    review_text = TextAreaField("Your Review:", validators=[InputRequired(), Length(1, 200, "No more than 200 words")])
    user_score = RadioField("Score:", choices=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10], default=5)
    submit = SubmitField("Post")

# Account Forms
class RegistrationForm(FlaskForm):
	user_id = StringField("User id:", validators=[InputRequired()])
	password = PasswordField("Password:", validators=[InputRequired()])
	password2 = PasswordField("Repeat Password:", validators=[InputRequired(), EqualTo("password")])
	submit = SubmitField("Register")

class LoginForm(FlaskForm):
    user_id = StringField("User id:", validators=[InputRequired()])
    password = PasswordField("Password:", validators=[InputRequired()])
    submit = SubmitField("Login")

class AdminLoginForm(FlaskForm):
    admin_id = StringField("Admin id:", validators=[InputRequired()])
    password = PasswordField("Password:", validators=[InputRequired()])
    submit = SubmitField("Login")

# Admin Forms
class AddGameForm(FlaskForm):
    name = StringField("Game Name:", validators=[InputRequired()])
    genre = StringField("Genre:", validators=[InputRequired()])
    release_date = DateField("Date (YYYY-MM-DD):", format='%Y-%m-%d', validators=[InputRequired()])
    developer = StringField("Developer:", validators=[InputRequired()])
    publisher = StringField("Publisher:", validators=[InputRequired()])
    image = StringField("Image URL (Add to static folder):", validators=[InputRequired()])
    description = TextAreaField("Game Description:", validators=[InputRequired()])
    submit = SubmitField("Add")

class DeleteGameForm(FlaskForm):
    game_id = IntegerField("Game ID:", validators=[InputRequired()])
    submit = SubmitField("Delete")

class DeleteReviewForm(FlaskForm):
    review_id = IntegerField("Review ID:", validators=[InputRequired()])
    submit = SubmitField("Delete")

class DeleteUserForm(FlaskForm):
    user_id = StringField("User ID:", validators=[InputRequired()])
    submit = SubmitField("Delete")

# https://wtforms.readthedocs.io/en/2.3.x/fields/
class UploadImageForm(FlaskForm):
    image = FileField("Image File:", validators=[FileRequired(), FileAllowed(["jpg", "jpeg", "png"], "Images only!")])
    submit = SubmitField("Upload")

class AddNewAdminForm(FlaskForm):
	admin_id = StringField("Admin id:", validators=[InputRequired()])
	password = PasswordField("Password:", validators=[InputRequired()])
	password2 = PasswordField("Repeat Password:", validators=[InputRequired(), EqualTo("password")])
	submit = SubmitField("Add Admin")