BACKUP! BACKUP! BACKUP!
stop racoontrace. Important!
(if you used migrate before: delete table "alembic_version" and every "migrations" folder)

"c:\Python\Python3.8.3\python.exe" migrate.py db init
"c:\Python\Python3.8.3\python.exe" migrate.py db migrate -m "move to v0.5"
"c:\Python\Python3.8.3\python.exe" migrate.py db upgrade

Start racoontrace

goto http(s)://yourdomain.tld/upgrade
sign in with your really first user
*cross your fingers*

edit every location to its needed name and set autoheckout value (still wip)

goto /users
assign userroles if needed
go on as ussual