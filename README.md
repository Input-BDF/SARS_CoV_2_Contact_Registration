# SARS CoV 2 Contact Registration
A simple web application to collect contact information from visitors during the SARS CoV 2 pandemic.

## Intention
The basic intention is to provide an alternative way of collecting visitor data during the SARS CoV 2 pandemic. The regulations force us to collect this data. In order not to suffocate in thousands of paper forms and to collect data as "technology-neutral" as possible, no mobile phone app should be used. So we started this approach. Hope that helps you too.

## How it works
Basically a visitor opens the web url, enters their data and retrives a qr code containing an unique id. On site this qr code is scanned by an employee on begin and end of the visitor visit. This way personal data is only tranfered once and you save a lot of paper. Also an checkin/ checkout is independent of a mobile device since the visitor can also print this qr code.
Visitor data is stored asymetric (why? because i can) within database and only users with appropriate admin role can read this data. Visits and visitor data older than the given threshold will be deleted automatically.

## Requirements
All you need on the visitor's side is an internet connection and a browser.
To run this application server side Python >= 3.7 is needed. All required modules are listet within requirements.txt. For SSL connection valid certificates are needed. <a href="https://letsencrypt.org/">Let's encrypt</a> is your friend. If you have a guest wifi you could run all this e.g. on a Raspberry Pi accessible over your network.

## Usage visitor
1. Open Url
1. Enter Data
1. Show qr code to a responsible employee

## Usage employee
1. open `[yourdomain]:[port]/signin`
1. scan visitor qr code via web interface at the beginning of the visit (checks in automatically)
1. scan visitor qr code via web interface at the end of the visit (via "checkout" button)

## Supported devices
Actually every device with an browser. For scanning every mobile device with a camera or pc with a webcam

## Limitations
Scanning is not available for ios devices as the used library can not access camera on these devices.

## Installation
1. clone repository to your server
1. rename/ move `ilsc.cfg_default` to `ilsc.cfg` and `flask.cfg_default` to `flask.cfg`
1. edit both configuration files to your needs
   1. sqlite database is created automatically, same for gpg-keys
1. rename & edit `default_gprd.html` and `default_imprint.html` to your needs. Also address these files within `ilsc.cfg`
1. (optionally if you want to use ssl) set `usessl` within `ilsc.cfg` to `True` and configure location of server certificates within this file
1. run `python main.py --config ./ilsc.cfg --flask-config ./flask.cfg` either via screen or as system service
1. login at `[yourdomain]:[port]/signin`
   1. default user: `admin`
   1. default password: `admin`
1. open backend via "backend" top right
1. change username and password and add (optional) users

## I used the last release? What now?

Do a backup and check [UPGRADE.md](UPGRADE.md). Things can go wrong. If you have any trouble -> contact me!

## Used third party modules  
https://github.com/schmich/instascan thx a lot, nice work done dude

## Disclaimer
I absolutely do not take over any responsibility for the correctness of imprint and gprd. If there is something wrong ... let me know
