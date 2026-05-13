from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length
)


class RegisterForm(FlaskForm):
    username = StringField(
        'Username',
        validators=[DataRequired(), Length(min=3, max=30)]
    )

    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )

    password = PasswordField(
        'Password',
        validators=[DataRequired(), Length(min=6)]
    )

    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(),
            EqualTo('password')
        ]
    )

    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )

    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )

    submit = SubmitField('Login')


class MessageForm(FlaskForm):
    content = TextAreaField(
        'Message',
        validators=[DataRequired(), Length(max=1000)]
    )

    submit = SubmitField('Send')
