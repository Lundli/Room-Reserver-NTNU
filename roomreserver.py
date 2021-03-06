#!/usr/bin/env python
# coding: utf-8
import requests
from lxml import html
from datetime import date, timedelta
import numpy as np
import pandas as pd
from os import path, environ
import sys

# Read arguments
args = {}
for pair in sys.argv[1:]:
    args.__setitem__(*((pair.split('=', 1) + [''])[:2]))

if 'FUSER' not in environ.keys():
	raise Exception("No feide username found. Create env var: FUSER")

if 'FPASSWORD' not in environ.keys():
	raise Exception("No feide username found. Create env var: FPASSWORD")

USERNAME = environ['FUSER'] # Feide username
PASSWORD = environ['FPASSWORD'] # Feide PASSWORD

if 'init' in args.keys():
    init = args['init'].lower() in ("yes", "true", "t", "1")
else:
    init = False

if 'reserve' in args.keys() and args['reserve'].lower() in ("no", "false", "f", "0"):
	reserve = False
else:
    reserve = True


if 'store' in args.keys()and args['store'].lower() in ("no", "false", "f", "0"):
    store_found = False
else:
    store_found = True



if 'duration' not in args.keys():
	duration='02:00'
else:
	duration = args['duration'] # Reservation time in hr, max 4hr


if 'min_size' not in args.keys():
	min_size='10'
else:
	min_size = args['min_size']

if 'reserve_in' not in args.keys():
	reserve_in_n_days = 14
else:
	reserve_in_n_days = int(args['reserve_in']) # Reserve in n_days


if 'slack_log' in args.keys():
	slack_log = args['slack_log'].lower() in ("yes", "true", "t", "1")
else:
	slack_log = False

if slack_log:
	if 'SLACK_TOKEN' not in environ.keys():
		raise Exception("No feide SLACK TOKEN found. Create env var: SLACK_TOKEN")

	if 'SLACK_CHANNEL' not in environ.keys():
		raise Exception("No SLACK CHANNEL found. Create env var: SLACK_CHANNEL")
	if 'SLACK_URL ' not in environ.keys():
		raise Exception("No SLACK URL found. Create env var: SLACK_URL")


	SLACK_TOKEN = environ['SLACK_TOKEN']
	SLACK_URL = environ['SLACK_URL']
	SLACK_CHANNEL = environ['SLACK_CHANNEL']



if not init:
	if 'start' not in args.keys():
		raise Exception("Need start time. Pass start='HH:MM'")
	else:
		start = args['start']
	if 'desc' not in args.keys() and reserve:
		raise Exception("Need description. Pass description='Your room reservation description here'")
	elif reserve:
		reservation_description = args['desc'] # Title of reservation


date_to_reserve = date.today()+timedelta(days=reserve_in_n_days)
date_to_reserve_type1 = date_to_reserve.strftime("%d.%m.%Y")
date_to_reserve_type2 = date_to_reserve.strftime("%Y-%m-%d")
day_to_reserve = date_to_reserve.strftime('%a').upper()
MAIN_URL = 'https://tp.uio.no/ntnu/rombestilling/'

room_priority_path = "room_priority.csv"
areas_path = "areas.csv"
buildings_path = "buildings.csv"
roomtypes_path = "roomtypes.csv"


# Create session and login.
session = requests.Session()
request = session.get(MAIN_URL)
newUrl = request.url
asLen = html.fromstring(request.content).xpath('//input[@name="asLen"]/@value')[0]
AuthState = html.fromstring(request.content).xpath('//input[@name="AuthState"]/@value')[0]
auth_data = {
    'feidename': USERNAME,
    'password': PASSWORD,
    'asLen': asLen,
    'AuthState': AuthState,
    'org': 'ntnu.no'
}
auth_request = session.post(newUrl, auth_data)
print("Auth request: " + str(auth_request))
action = html.fromstring(auth_request.content).xpath('//form/@action')[0]
SAMLResponse = html.fromstring(auth_request.content).xpath('//input[@name="SAMLResponse"]/@value')[0]
RelayState = html.fromstring(auth_request.content).xpath('//input[@name="RelayState"]/@value')[0]

auth_confirmation_data = {
    'SAMLResponse': SAMLResponse,
    'RelayState': RelayState
}

nojs_auth_confirmation_request = session.post(action, auth_confirmation_data)
print("Auth confirmation nojs request: " + str(nojs_auth_confirmation_request))


def find_areas(request):
    areas = html.fromstring(request.content).xpath('//select[contains(@name,"area")]/option/text()')
    area_ids = html.fromstring(request.content).xpath('//select[contains(@name,"area")]/option/@value')
    area_df = pd.DataFrame(np.array([areas, area_ids]).T, columns = ["area", "area_id"])
    area_df["rank"] = 0
    area_df.to_csv(areas_path, index=False)

def find_buildings(request):
    buildings = html.fromstring(request.content).xpath('//select[contains(@name,"building")]/option/text()')
    buildings_ids = html.fromstring(request.content).xpath('//select[contains(@name,"building")]/option/@value')
    buildings_df = pd.DataFrame(np.array([buildings, buildings_ids]).T, columns = ["building", "building_id"])
    buildings_df["rank"] = 0
    buildings_df.to_csv(buildings_path, index=False)

def find_roomtypes(request):
    roomtypes = html.fromstring(request.content).xpath('//select[contains(@name,"roomtype")]/option/text()')
    roomtypes_ids = html.fromstring(request.content).xpath('//select[contains(@name,"roomtype")]/option/@value')
    roomtypes_df = pd.DataFrame(np.array([roomtypes, roomtypes_ids]).T, columns = ["roomtype", "roomtype_id"])
    roomtypes_df["rank"] = 0
    roomtypes_df.to_csv(roomtypes_path, index=False)

def max_room_rank(room_id, found_rooms):
    room_ranks = found_rooms.loc[found_rooms['room_id'] == room_id]['rank'].values
    if len(room_ranks) == 0:
        return -1

    return max(room_ranks)


def find_available_rooms(area, roomtype, building, store_found = False, prioritize = True):
    room_filter_data = {
      'start': start,
      'duration': duration,
      'preset_date': date_to_reserve_type1,
      'area': area,
      'building': building,
      'roomtype': roomtype,
      'size': min_size,
      'new_equipment': '',
      'preformsubmit': '1'
    }

    request = session.post(MAIN_URL, data=room_filter_data)
    print("Find available rooms request: " + str(request))

    available_room_ids = html.fromstring(request.content).xpath('//form//table[contains(@class,"possible-rooms-table")]/tbody/tr/td/@title')
    available_room_ids = available_room_ids[0::3]

    available_room_names = html.fromstring(request.content).xpath('//form//table[contains(@class,"possible-rooms-table")]/tbody/tr/td/a/text()')
    available_room_names = [room.strip() for room in available_room_names]

    if len(available_room_ids) == 0:
        return np.array([])

    new_rooms = []
    if store_found:
        path_exists = path.exists(room_priority_path)
        if path_exists:
            found_rooms = pd.read_csv(room_priority_path, encoding='utf8')

        for room in np.c_[available_room_names, available_room_ids]:
            if not path_exists or not room[0] in found_rooms['room_name'].values:
                new_rooms.append([room[0],room[1], 0])
        new_rooms = pd.DataFrame(new_rooms,columns=['room_name','room_id','rank'])
        with open(room_priority_path, 'a+') as f:
            new_rooms.to_csv(f, header=(not path_exists),index = False, encoding='utf8')

    if prioritize:
        path_exists = path.exists(room_priority_path)
        if path_exists:
            found_rooms = pd.read_csv(room_priority_path, encoding='utf8')
        else:
            return np.array(available_room_ids)

        available_room_ids_ordered = []

        for room_id in available_room_ids:
            max_room_rank_value =  max_room_rank(room_id, found_rooms)
            if max_room_rank_value < 0:
                continue
            available_room_ids_ordered += [[room_id, max_room_rank_value]]
        available_room_ids_ordered = sorted(available_room_ids_ordered, key=lambda row: row[1], reverse = True)

        return np.array(available_room_ids_ordered)[:,0]
    return np.array(available_room_ids)



# Start reservation of room
def reserve_room(room, area, roomtype, building):
    reservation_data = {
      'start': start,
      'size': min_size,
      'roomtype': roomtype,
      'duration': duration,
      'area': area,
      'building': building,
      'preset_date': date_to_reserve_type1,
      'exam': '',
      'single_place': '',
      'room[]': room,
      'submitall': 'Bestill \u21E8'
    }

    reserve_request = session.post(MAIN_URL, data=reservation_data)
    print("reserve request: " + str(reserve_request))

    # Confrim reservation
    tokenrb = html.fromstring(reserve_request.content).xpath('//form//input[contains(@name, "tokenrb")]/@value')[0]
    reservation_confirmation_data = {
      'name': reservation_description,
      'notes': '',
      'confirmed': 'true',
      'confirm': '',
      'start': start,
      'size': min_size,
      'roomtype': roomtype,
      'duration': duration,
      'area': area,
      'room[]': room,
      'building': building,
      'preset_day': day_to_reserve,
      'preset_date': date_to_reserve_type2,
      'exam': '',
      'single_place': '',
      'dates[]': date_to_reserve_type2,
      'tokenrb': tokenrb
    }

    reserve_confirmation_request = session.post(MAIN_URL, data=reservation_confirmation_data)
    print("reserve_confirmation_request: " + str(reserve_confirmation_request))
    return reserve_confirmation_request

def find_room_to_reserve():
	if len(areas["area_id"].values)==0:
		print("Need to set area ranks")
	if len(roomtypes["roomtype_id"].values) == 0:
		print("Need to set roomtype ranks")
	if len(buildings["building_id"].values) == 0:
		print("Need to set building ranks")

	for area in areas["area_id"].values:
		for roomtype in roomtypes["roomtype_id"].values:
			for building in buildings["building_id"].values:
				print(area, roomtype, building)
				rooms = find_available_rooms(area, roomtype, building, store_found = store_found, prioritize = True)
				if len(rooms)>0 and reserve:
					return (area, roomtype, building, rooms[0])
	return "", "", "", ""



if not path.exists(buildings_path):
    find_buildings(nojs_auth_confirmation_request)
if not path.exists(roomtypes_path):
    find_roomtypes(nojs_auth_confirmation_request)
if not path.exists(areas_path):
    find_areas(nojs_auth_confirmation_request)

buildings = pd.read_csv(buildings_path)
buildings = buildings.loc[buildings["rank"] != 0]
buildings = buildings.sort_values(by=["rank"], ascending = False)
buildings["building_id"] = buildings["building_id"].astype(int)

areas = pd.read_csv(areas_path)
areas = areas.loc[areas["rank"] != 0]
areas = areas.sort_values(by=["rank"], ascending = False)
areas["area_id"] = areas["area_id"].astype(int)

roomtypes = pd.read_csv(roomtypes_path)
roomtypes = roomtypes.loc[roomtypes["rank"] != 0]
roomtypes = roomtypes.sort_values(by=["rank"], ascending = False)


def log_to_slack(request):

    header = {"Content-Type": "text/plain; charset=utf-8"}
    params = (('token', SLACK_TOKEN),('channel', SLACK_CHANNEL))
    main_string = ''.join(html.fromstring(request.content).xpath('//h3/../section/div/span//text()')) + ":mazemap: :tornadotor: :powerstonk:"
    data = main_string.encode('utf-8')
    response = requests.post(SLACK_URL, params=params, data=data, headers=header)


if not init:
	area, roomtype, building, room = find_room_to_reserve()
	if reserve and len(room)>0:
		reserve_request = reserve_room(room, area, roomtype, building)
		if slack_log:
			log_to_slack(reserve_request)
