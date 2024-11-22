import urllib.request, urllib.error
import requests
import time
from datetime import datetime
import json
from bs4 import BeautifulSoup
import re
from typing import List
import logging
from zipcodes import get_neighborhoods_for_zipcode

# If don't want this script to send anything to telegram,
# set this to True.
TEST_MODE = False

# Loglevel (logging.(DEBUG|INFO|WARNING|ERROR))
LOG_LEVEL = logging.DEBUG

# Logfile path (Set to None to disable file logging)
LOG_FILE  = None #'log.txt'

# Format of single logmessage
LOG_FORMAT='[%(levelname)s] %(asctime)s %(message)s'


# gets a values from a nested object
def get_value_from_config(path):
	with open("config.json") as file:
		config_json = json.load(file)

		data = config_json

		for prop in path:
			if len(prop) == 0:
				continue
			if prop.isdigit():
				prop = int(prop)
			data = data[prop]
	return data


def get_links_to_offers() -> dict:
	html = get_html_from_saga()
	if html == "": return {}

	all_links = []
	soup = BeautifulSoup(html, "html.parser")

	for link in soup.find_all('a'):
		if "/immobiliensuche/immo-detail/" in link.get("href", ""):
			all_links.append("https://saga.hamburg"\
				 + link.get("href", ""))
	# remove duplicates
	all_links = list(set(all_links))

	return {
		"apartments": [link for link in all_links if any(x in link.lower() for x in ["wohnung", "apartment", "zimmer"])],
		"offices":  [link for link in all_links if any(x in link.lower() for x in ["buro", "büro", "gewerbe"])],
		"parking":  [link for link in all_links if any(x in link.lower() for x in ["stellplatz", ""])]
	}



def get_html_from_saga():
	url = "https://www.saga.hamburg/immobiliensuche?Kategorie=APARTMENT"

	try:
		req = urllib.request.Request(url)
		req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0')
		req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
		req.add_header('Accept-Language', 'en-US,en;q=0.5')

		resp = urllib.request.urlopen(req)

		if not resp.code == 200:
			logging.warning("Error receiving data from saga!")
			logging.warning(">> " + str(resp.code) + " "\
				 + resp.reason)
			return None
		else:
			return resp.read().decode('utf-8')

	except urllib.error.HTTPError as e:
		logging.error("Error while getting request, " + str(e))
		return None


def get_offer_title(link_to_offer):
	try:
		resp = requests.get(link_to_offer)
		soup = BeautifulSoup(resp.text, "html.parser")
		title = soup.find_all('h1', class_='h3 ft-bold', limit=1)[0]
		return title.text
	except:
		return 'notitle '


# posts all information about an offer to telegram
def post_offer_to_telegram(offer_details, chat_id):
	send_msg_to_telegram("*-"*31 + "*", chat_id)

	def details_to_str(offer_details):
		if zipcode := offer_details.get("zipcode", None):
			neighborhoods = get_neighborhoods_for_zipcode(zipcode)
			return "Rent: {}€, Rooms: {}, Location: {} {}"\
				.format(offer_details.get('rent'),
					offer_details.get('rooms', '?'),
					offer_details.get('zipcode'),
					', '.join(neighborhoods))

		return  "Rent: {}€, Rooms: {}"\
			.format(offer_details.get('rent'),
				offer_details.get('rooms', '?'))

	for msg in [details_to_str(offer_details), offer_details.get("link")]:
		send_msg_to_telegram(msg, chat_id)



# sends a message to a telegram chat
def send_msg_to_telegram(msg, chat_id):
	token = get_value_from_config(["telegram_token"])
	msg = 'https://api.telegram.org/bot' + token\
		 + '/sendMessage?chat_id=' + chat_id\
		 + '&parse_mode=Markdown&text=' + msg
	try:
		resp = requests.get(msg)
		if resp.status_code != 200:
			logging.error("Could not forward to telegram api")
			logging.error(">> " + str(resp.status_code)\
				+ " " + resp.text)
			logging.error(">> Sent msg: '" + msg + "'")
#			exit()

	except requests.exceptions.RequestException as e:
		logging.error("Could not forward to telegram api")
		logging.error(">> Error: " + str(e))
		logging.error(">> Sent msg: '" + msg + "'")


def is_offer_known(offer: str):
	return offer in open("known_offers.txt").read().splitlines()


def add_offers_to_known_offers(offers: dict):
	for offer_list in offers.values():
		for link in offer_list:
			if not is_offer_known(link):
				file = open("known_offers.txt", "a+")
				file.write(link + "\n")
				file.close()


def get_zipcode(offer_soup) -> int|None:
	# address is in "text-xl" class
	text_xl_divs = offer_soup.find_all('div', class_='text-xl')
	if text_xl_divs:
		for div in text_xl_divs:
			#print(div.string)
			res = re.findall(r'\d{5}', str(div.string))
			if res: return res[0]
	return None



def get_rent(offer_soup) -> float:
	# Example rent_string 1.002,68 €
	rent_string = offer_soup.find("td", text="Gesamtmiete")\
			.findNext("td").string
	rent_string = rent_string.replace('€', '').replace(' ', '')
	rent_string = rent_string.split(',')[0]  # ignore cents
	rent = rent_string.replace('.', '')  # replace 1.000 to be 1000
	return float(rent)


def get_rooms(offer_soup) -> int|None:
	try:
		rooms_string = offer_soup.find("td", string="Zimmer")\
				.findNext("td").string
		rooms_string = rooms_string.strip()
	except AttributeError:
		# no info on rooms (happens for offices)
		return None

	# Seems like a nifty coder changed the room-number format
	# within the new website...
	try:
		rooms = int(rooms_string)
	except ValueError:
		# Let's see if we have a 'half' room formatted
		# like '2,5' or '2 1/2'...
		if ',' in rooms_string:
			rooms = int(rooms_string.split(',')[0])
		elif '1/2' in rooms_string:
			rooms = int(rooms_string.split(' ')[0])
		else:
			logging.warning("Invalid number of rooms '"\
				+ rooms_string + "'")
			return None
	return rooms


def get_offer_details(link:str) -> dict:
	details = {
		"rent"    : None,
		"zipcode" : None,
		"rooms"   : None,
		"link"    : link
	}

	# get details HTML
	req = urllib.request.Request(link)
	req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0')
	req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
	req.add_header('Accept-Language', 'en-US,en;q=0.5')

	get_url = urllib.request.urlopen(req)
	get_text = get_url.read().decode("utf-8")
	offer_soup = BeautifulSoup(get_text, "html.parser")

	# get rent price
	details["rent"] = get_rent(offer_soup)

	# get rooms
	details["rooms"] = get_rooms(offer_soup)

	# check if zipcode is in zipcode whitelist
	details["zipcode"] = get_zipcode(offer_soup)
	if not details["zipcode"]:
		logging.warning("Failed to get zipcode for offer: " + link)

	return details


# checks if the offer meets the criteria for this chat
def offers_that_match_criteria(links_to_all_offers, chat_id) -> List[str]:
	matching_offers = []
	criteria = get_value_from_config(["chats", chat_id, "criteria"])

	# get only offers of matching category (e.g. "apartments")
	offers = links_to_all_offers.get(criteria.get("category", "apartments"), [])

	for offer_link in offers:
		if is_offer_known(offer_link):
			continue

		logging.debug("New offer: " + offer_link)
		offer_details = get_offer_details(offer_link)

		# check rent price
		rent_until = criteria["rent_until"]
		if offer_details.get("rent", 0) > rent_until:
			logging.debug("Rent too high ({}, {})"\
				.format(offer_details.get('rent'), rent_until))
			continue

		# check min rooms
		min_rooms = criteria.get("min_rooms", None)
		if min_rooms and min_rooms > offer_details.get("rooms", 0):
			logging.debug("Not enough rooms")
			continue

		# check if zipcode is in zipcode whitelist
		if criteria["zipcode_whitelist"]:
			zipcode = offer_details.get("zipcode", None)
			if not zipcode or zipcode not in criteria["zipcode_whitelist"]:
				logging.debug("Offer not in zipcode whitelist")
				continue

		# all criteria matched
		logging.info("Found matching offer: " + offer_link)
		matching_offers.append(offer_details)

	return matching_offers


if __name__ == "__main__":

	if LOG_FILE:
		logging.basicConfig(level=LOG_LEVEL, filename=LOG_FILE,
			format=LOG_FORMAT)
	else: logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

	chat_ids = get_value_from_config(["chats"]).keys()

	if not TEST_MODE:
		for chat_id in chat_ids:
			if get_value_from_config(["chats", chat_id, "debug_group"]):
				send_msg_to_telegram("Bot started at " + str(datetime.now()), chat_id)

	while True:
		logging.debug("Checking for updates ...")
		current_offers = get_links_to_offers()

		# for each chat: send offer to telegram, if it meets the chat's criteria
		for chat_id in chat_ids:
			matching_offers = offers_that_match_criteria(current_offers, chat_id)

			if not TEST_MODE:
				for offer in matching_offers:
					post_offer_to_telegram(offer, chat_id)

		# finally add to known offers
		add_offers_to_known_offers(current_offers)

		# check every 3 minutes
		time.sleep(180)
