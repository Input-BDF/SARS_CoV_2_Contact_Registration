BACKUP! BACKUP! BACKUP!
stop racoontrace. Important!

copy migrate.cfg_default to migrate.cfg and adjust needed stuff like db location and secret key

(if you used migrate before: delete table "alembic_version" and every "migrations" folder)

"c:\Python\Python3.8.3\python.exe" migrate.py db init
"c:\Python\Python3.8.3\python.exe" migrate.py db migrate -m "move to v0.5"
"c:\Python\Python3.8.3\python.exe" migrate.py db upgrade

Start racoontrace

goto http(s)://yourdomain.tld/upgrade
sign in with your really!! first user
*cross your fingers*

edit every location to its needed name and set autoheckout value (still wip)
edit user permissions if needed/ wanted

goto /users
assign userroles if needed
go on as ussual