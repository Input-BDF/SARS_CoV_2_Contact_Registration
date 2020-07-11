# SARS CoV 2 Contact Registration
A simple web application to collect contact information from visitors during the SARS CoV 2 pandemic.

## Intention
Basic intention is to provide an alternative way to collect visitor data during SARS CoV 2 pandemic. Since regulations force us to collect this data and no mobile phone app should be used we started this approach

## How it works
Basicly an customer opens the web url, enters his/her data and retrives a qr code containing an unique id. On site this qr code is scanned by an employee on begin and end of the customer visit. This way personal data is only tranfered once and you safe a lot of paper. Also an checkin/ checkout is independent of a mobile device since the customer can also print this qr code.
Customer data is stored assymetric (why cause i can) within database and only users with admin permission can read this data

## Requirements
On customer side ther is only a internet connection needed.
To run this application server side Python >= 3.7 is needed. All required modules are listet within requirements.txt.

## Usage Costumer
1. Open Url
1. Enter Data
1. Show qr code to a responsible employee

## Usage employee
1. open `[yourdomain]:[port]/signin`
1. scan customer qr code via web interface at the beginning of the visit (checks in automatically)
1. scan customer qr code via web interface at the end of the visit (via "checkout" button)

## Supported devices
Actually every device with an browser. For scanning every mobile device with a camera or pc with a webcam

## Limitations
Scanning is not available for ios devices as the used library can not access camera on these devices.

## Installation
1. clone repository to your server
1. rename/ move `ilsc.cfg_default` to `ilsc.cfg` and `flask.cfg_default` to `flask.cfg`
1. edit both configuration files to your needs
1. rename & edit `default_gprd.html` and `default_imprint.html` to your needs. Also address these files within `ilsc.cfg`
1. (optionally if you want to use ssl) set `usessl` within `ilsc.cfg` to `True` and configure location of server certificates within this file
1. run `python main.py --config ./ilsc.cfg --flask-config ./flask.cfg` either via screen or as system service
1. login at `[yourdomain]:[port]/signin`
  1. default user: `admin`
  1. default password: `admin`
1. open backend via "backend" top right
1. change username and password and add (optional) users

## Used third party modules  
https://github.com/schmich/instascan thxalot nice work done dude

## Disclaimer
I absolutely do not take over any responsibility for the correctness of imprint and gprd. If there is something wrong ... let me now
