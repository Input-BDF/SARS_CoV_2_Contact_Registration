# -*- coding: UTF-8 -*-
'''
Created on 06.06.2020

@author: Input
'''
from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, PasswordField, SelectField

from wtforms.fields.html5 import DateField
from wtforms.validators import InputRequired, length, DataRequired, EqualTo

#********Forms**********
class RegisterForm(FlaskForm):
    firstname = StringField(label = 'Vorname',
                            validators=[InputRequired(message='Bitte Vornamen eingeben'), length(max=40, message='Maximal 40 Zeichen erlaubt.')],
                            filters=(),
                            description='Vorname',
                            id='fname',
                            render_kw={'placeholder': 'Vorname', 'maxlength':'40'}
                            )
    lastname = StringField(label = 'Nachname',
                           validators=[InputRequired(message='Bitte Nachnamen eingeben'), length(max=40, message='Maximal 40 Zeichen erlaubt.')],
                           filters=(),
                           description='Nachname',
                           id='sname',
                           render_kw={'placeholder': 'Nachname', 'maxlength':'40'}
                           )
    contact = TextAreaField(label = 'Kontakt',
                            validators=[InputRequired(message='Bitte Adresse eingeben'), length(max=400, message='Maximal 400 Zeichen erlaubt.')],
                            filters=(),
                            description='Adresse oder Telefonnummer',
                            id='contact',
                            render_kw={'placeholder': 'Adresse oder Telefonnummer', 'maxlength':'400'},
                            )
    agree = BooleanField(label = 'Ich stimme der Speicherung meiner angegebenen Daten zur Umsetzung der Bestimmungen der '\
                         '<a href="https://corona.thueringen.de/behoerden/ausgewaehlte-verordnungen" target="_blank">Thüringer'\
                         ' Verordnung zur Neuordnung der erforderlichen Maßnahmen zur Eindämmung der Ausbreitung des Coronavirus SARS-CoV-2</a> zu.',
                         validators=[InputRequired(message='Bitte Zustimmung geben')])

class UserForm(FlaskForm):
    username = StringField(label = 'Nutzername',
                            validators=[InputRequired(message='Bitte Vornamen eingeben'), length(max=40, message='Maximal 40 Zeichen erlaubt.')],
                            filters=(),
                            description='Nutzername',
                            id='username',
                            render_kw={'placeholder': 'Nutzername', 'maxlength':'40'}
                            )
    isadmin = BooleanField(label = 'Admin')
    devision = SelectField(label = 'Sektion')
    
    def __init__(self, choices = [], obj = None):
        super().__init__(obj = obj)
        self.devision.choices = choices

class ChangePasswd(FlaskForm):
    password = PasswordField('Passwort', validators=[
        DataRequired(),
        EqualTo('confirm', message='Passwörter müssen übereinstimmen')
    ])
    confirm = PasswordField('Passwort wiederholen')
    
class UserAddForm(FlaskForm):
    username = StringField(label = 'Nutzername',
                            validators=[InputRequired(message='Bitte Vornamen eingeben'), length(max=40, message='Maximal 40 Zeichen erlaubt.')],
                            filters=(),
                            description='Nutzername',
                            id='username',
                            render_kw={'placeholder': 'Nutzername', 'maxlength':'40'}
                            )
    isadmin = BooleanField(label = 'Admin')
    devision = SelectField(label = 'Sektion')
    password = PasswordField('Passwort', validators=[
        DataRequired(),
        EqualTo('confirm', message='Passwörter müssen übereinstimmen')
    ])
    confirm = PasswordField('Passwort wiederholen')
    
    def __init__(self, choices = [], obj = None):
        super().__init__(obj = obj)
        self.devision.choices = choices

class DateForm(FlaskForm):
    visitdate = DateField('Datum', format='%Y-%m-%d', default=date.today())
    
    '''
    def validate_on_submit(self):
        result = super(TestForm, self).validate()
        if (self.startdate.data>self.enddate.data):
            return False
        else:
            return result
    '''

class OrganisationForm(FlaskForm):
    name = StringField(label = 'Organisation',
                            validators=[InputRequired(message='Bitte Namen eingeben'), length(max=256, message='Maximal 256 Zeichen erlaubt.')],
                            filters=(),
                            description='Organisationsname',
                            id='orgname',
                            render_kw={'placeholder': 'Bitte Namen eingeben', 'maxlength':'256'}
                            )
    
    def __init__(self, obj = None):
        super().__init__(obj = obj)

class LocationForm(FlaskForm):
    name = StringField(label = 'Location',
                            validators=[InputRequired(message='Bitte Namen eingeben'), length(max=256, message='Maximal 256 Zeichen erlaubt.')],
                            filters=(),
                            description='Locationname',
                            id='locname',
                            render_kw={'placeholder': 'Bitte Namen eingeben', 'maxlength':'256'}
                            )

    def __init__(self, obj = None):
        super().__init__(obj = obj)
