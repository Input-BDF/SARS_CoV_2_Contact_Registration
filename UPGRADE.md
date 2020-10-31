BACKUP! BACKUP! BACKUP!<br>
stop racoontrace. Important!

copy *migrate.cfg_default* to *migrate.cfg* and adjust needed stuff like db location and secret key


run:<br>
`python migrate.py db init`<br>
`python migrate.py db migrate -m "move to v0.5"`<br>
`python migrate.py db upgrade`<br>

Start racoontrace

goto *http(s)://yourdomain.tld/upgrade*<br>
sign in with your really!! first user<br>
*cross your fingers*

edit every location to its needed name and set autoheckout value
edit user permissions if needed/ wanted

goto *http(s)://yourdomain.tld//users*<br>
assign userroles if needed<br>
go on as ussual
