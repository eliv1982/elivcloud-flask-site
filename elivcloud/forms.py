"""WTForms form definitions.

LoginForm and EmptyForm are unchanged from the original single-file app.py
(admin-only, Russian labels, not localized in this slice per the approved
plan).

ContactForm gained a `lang` constructor keyword. WTForms builds a fresh
Field instance per Form *instance* already (that's how the same class can
back independent requests at all), but the validators list attached to each
field is, by default, the very list object given in the class body below —
shared by reference across every instance unless something reassigns it.
Mutating that shared list in place (e.g. appending/replacing an element)
would leak between concurrent requests under threaded/gunicorn workers.
Instead, __init__ *replaces* each field's `.validators` with a brand new
list of freshly constructed validator objects carrying localized messages —
that only rebinds the instance attribute, leaving the class-level list (and
every other in-flight ContactForm instance) untouched. This is the
"localized custom validators" approach, not a form factory, since a factory
that generates a new class per request would be unnecessary — WTForms
already gives every instance its own bound fields.
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length

from .content import get_contact_validation_messages


class ContactForm(FlaskForm):
    name = StringField("Имя", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Телефон", validators=[Length(max=32)])
    subject = StringField("Тема", validators=[DataRequired(), Length(max=180)])
    message = TextAreaField("Сообщение", validators=[DataRequired(), Length(max=5000)])
    submit = SubmitField("Отправить заявку")

    def __init__(self, *args, lang: str = "ru", **kwargs):
        super().__init__(*args, **kwargs)
        messages = get_contact_validation_messages(lang)

        # Each assignment below replaces the instance's field.validators
        # list wholesale; it never mutates the original list defined on the
        # class above, so other ContactForm instances (other requests,
        # other languages, concurrently in flight) are unaffected.
        self.name.validators = [
            DataRequired(message=messages["required"]),
            Length(max=120, message=messages["name_length"]),
        ]
        self.email.validators = [
            DataRequired(message=messages["required"]),
            Email(message=messages["invalid_email"]),
            Length(max=255, message=messages["email_length"]),
        ]
        self.phone.validators = [
            Length(max=32, message=messages["phone_length"]),
        ]
        self.subject.validators = [
            DataRequired(message=messages["required"]),
            Length(max=180, message=messages["subject_length"]),
        ]
        self.message.validators = [
            DataRequired(message=messages["required"]),
            Length(max=5000, message=messages["message_length"]),
        ]


class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Войти")


class EmptyForm(FlaskForm):
    submit = SubmitField("Подтвердить")
