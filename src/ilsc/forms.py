# -*- coding: UTF-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

__all__ = [
    # classes
    'RegisterForm',
    'UserForm',
    'UserAddForm',
    'ChangePasswd',
    'DateLocForm',
    'LocationForm',
    'OrganisationForm',
    'OrganisationRegForm',
    'OrganisationSwitchForm'
]

from datetime import date
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, PasswordField, SelectField, SelectMultipleField, widgets
from wtforms.compat import itervalues
from wtforms.fields.html5 import DateField
from wtforms.validators import InputRequired, length, DataRequired, EqualTo, ValidationError, Regexp
from collections import OrderedDict
#********Forms**********
class RegisterForm(FlaskForm):
    '''
    Guest registration form
    '''
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

class MultiCheckboxField(SelectMultipleField):
    '''
    class to provide multiple options checkbox field
    '''
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

def validate_unique(form, field):
    '''
    validator to check if username already exists
    '''
    if form.dup_check(field.data) and field.object_data != field.data:
        raise ValidationError(f'"{field.data}" existiert bereits.')

def validate_unique_usr(form, field):
    '''
    validator to check if username already exists
    '''
    if form.usr_dup_check(field.data) and field.object_data != field.data:
        raise ValidationError(f'"{field.data}" existiert bereits.')

class UserForm(FlaskForm):
    '''
    Basic user edit form
    '''
    username = StringField(label = 'Nutzername',
                            validators=[InputRequired(message='Bitte Vornamen eingeben'), length(max=40, message='Maximal 40 Zeichen erlaubt.'), validate_unique_usr],
                            filters=(),
                            description='',
                            id='username',
                            render_kw={'placeholder': 'Nutzername', 'maxlength':'40'}
                            )
    devision = SelectField(label = 'Location')
    roles = SelectMultipleField('Nutzerrollen', 
        coerce=int,
        option_widget=widgets.CheckboxInput(), 
        widget=widgets.ListWidget(prefix_label=False) )

    def __init__(self, usr_dup_check=None, choices=[], obj=None, *args, **kwargs):
        '''
        usr_dup_check > callback to database object to check duplicate names
        '''
        super().__init__(obj = obj)
        if self.devision:
            self.devision.choices = choices
        if usr_dup_check:
            self.usr_dup_check = usr_dup_check

class UserAddForm(UserForm):
    '''
    User add form
    '''
    password = PasswordField('Passwort',
                            validators=[
                                DataRequired(),
                                EqualTo('confirm', message='Passwörter müssen übereinstimmen'),
                                Regexp('^(?=.*[A-Za-z])(?=.*\d)(?=.*[_\-=@$!%*#?&])[A-Za-z\d@_\-=$!%*#?&]{8,}$',
                                message="""Passwort muss mindestens 8 Zeichen lang sein und einen<br/>"""\
                                        """Buchstaben, eine Zahl und ein Sonderzeichen _-=@$!%*#?& enthalten""")
                            ],
                            description="""Passwort muss mindestens 8 Zeichen lang sein und einen """\
                                        """Buchstaben, eine Zahl und ein Sonderzeichen _-=@$!%*#?& enthalten"""
                            )
    confirm = PasswordField('Passwort wiederholen')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class ChangePasswd(FlaskForm):
    '''
    User password change form
    '''
    password = PasswordField('Passwort',
                            validators=[
                                DataRequired(),
                                EqualTo('confirm', message='Passwörter müssen übereinstimmen'),
                                Regexp('^(?=.*[A-Za-z])(?=.*\d)(?=.*[_\-=@$!%*#?&])[A-Za-z\d@_\-=$!%*#?&]{8,}$',
                                       message="""Passwort muss mindestens 8 Zeichen lang sein und einen<br/>"""\
                                               """Buchstaben, eine Zahl und ein Sonderzeichen _-=@$!%*#?& enthalten""")
                            ],
                            description="""Passwort muss mindestens 8 Zeichen lang sein und einen """\
                                        """Buchstaben, eine Zahl und ein Sonderzeichen _-=@$!%*#?& enthalten"""
                            )
    confirm = PasswordField('Passwort wiederholen')

class DateLocForm(FlaskForm):
    '''
    Select date and location form
    '''
    visitdate = DateField('Datum', format='%Y-%m-%d')
    location = SelectField(label = 'Location')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.visitdate.data:
            self.visitdate.data = date.today()
        self.visitdate.default = date.today()

class LocationForm(FlaskForm):
    '''
    location edit form
    '''
    name = StringField(label = 'Location',
                            validators=[InputRequired(message='Bitte Namen eingeben'), length(max=256, message='Maximal 256 Zeichen erlaubt.')],
                            filters=(),
                            description='anzuzeigender Locationname',
                            id='locname',
                            render_kw={'placeholder': 'Bitte Namen eingeben', 'maxlength':'256'}
                            )
    checkouts = StringField(label = 'Autocheckouts',
                            validators=[
                                InputRequired(message='Bitte Stunde(n) eingeben.'),
                                length(max=256, message='Maximal 256 Zeichen erlaubt.'),
                                Regexp('^(?:([0-9]|1[0-9]|2[0-3]))(,\s*([0-9]|1[0-9]|2[0-3]))*$',
                                message="""Es sind nur Stundenwerte zwischen 0 und 23 erlaubt.<br/>"""\
                                        """Mehrere Werte durch Komma trennen. z.B.: 0,12,23""")
                            ],
                            default = 0,
                            filters=(),
                            description="""Stunde zu der ein Autocheckout aller Besucher sattfindet.\n"""\
                                        """Mehrere Werte durch Komma trennen. z.B.: 0,12,23""",
                            id='locname',
                            render_kw={'placeholder': 'Bitte Stunde(n) eingeben.',
                                       'maxlength':'256',
                                       'title':"""Stunde zu der ein Autocheckout aller Besucher sattfindet.\n"""\
                                       """Mehrere Werte durch Komma trennen. z.B.: 0,12,23""" }
                            )

    autoscancheckout = BooleanField(label = 'Autocheckout beim Scannen')

    def __init__(self, obj = None, *arg, **kwargs):
        super().__init__(obj = obj, *arg, **kwargs)

class OrganisationForm(FlaskForm):
    '''
    organisation edit form
    '''
    name = StringField(label = 'Organisation',
                            validators=[InputRequired(message='Bitte Namen eingeben'), length(max=256, message='Maximal 256 Zeichen erlaubt.'), validate_unique],
                            filters=(),
                            description='Organisationsname',
                            id='orgname',
                            render_kw={'placeholder': 'Bitte Namen eingeben', 'maxlength':'256'}
                            )
    
    def __init__(self, dup_check = None, obj = None, *arg, **kwargs):
        '''
        dup_check > callback to database object to check duplicate names
        '''
        super().__init__(dup_check = dup_check, obj = obj)
        if dup_check:
            self.dup_check = dup_check

class OrganisationSwitchForm(FlaskForm):
    '''
    simple form for organisation switching
    '''
    organisation = SelectField(label = 'Organisation', coerce=int)

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

class OrganisationRegForm(OrganisationForm, UserAddForm):
    '''
    Combined form to create Organisation and User 
    '''
    locationname = StringField(label = 'Location',
                        validators=[InputRequired(message='Bitte Namen eingeben'), length(max=256, message='Maximal 256 Zeichen erlaubt.'), validate_unique],
                        filters=(),
                        description='Locationname',
                        id='locname',
                        render_kw={'placeholder': 'Bitte Namen eingeben', 'maxlength':'256'}
                        )
    checkouts = LocationForm.checkouts
    devision = None
    roles = None

    __order = ['csrf_token', 'name', 'locationname', 'checkouts', 'username', 'password', 'confirm']
    def __init__(self, dup_check = None, usr_dup_check = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usr_dup_check = usr_dup_check
        self.dup_check = dup_check
        self.location_id = 0
        self.role_list = 0 
        
    def __iter__(self):
        '''
        reorder form fields based on __order
        '''
        __ordered = OrderedDict([(k, self._fields[k]) for k in self.__order])
        return iter(itervalues(__ordered))