This is a website for management and archival of robot combat events.
The System runs on python 3 and requires:
	Django: https://www.djangoproject.com/
	Crispy Forms: https://django-crispy-forms.readthedocs.io/en/latest/
	pycountry: https://pypi.org/project/pycountry/

Django comes with an inbuilt webserver so there is no need to set one up.
The database is currently configured to use mySQL, which would be required to be set up seperately

The simplest way to setup the project is to set it up using the default sqlite database.
	To do this, first open Django/EventManager/settings.py
		Change the 'ENGINE' argument on line 80 from 'django.db.backends.mysql' to 'django.db.backends.sqlite3'
		Change the 'NAME' argument on line 81 from 'robot_event_manager' to 'robot_event_manager.sqlite3'
		Delete lines 82 - 85
	Next some data needs to be changed in Django/EventManager/stuff.py
		For the google maps enabled parts of the site to work, set map to a valid google maps API key. (this is not nessicary for the site to function it can be set to just a blank string to allow the site to function without maps working)
		The Django variable should be set to a long string of random characters as this is the secret django key
		Since we're not using mySQL, the other two lines can be deleted.
	Then open a terminal in Django/ and run the following commands
		python3 manage.py makemigrations main
		python3 manage.py migrate
	The program can now be launched by running 
		python3 manage.py runserver
	and accessed from the localhost ip in a webbrowser

It also requires some data to be filled in in Django/EventManager/stuff.py
