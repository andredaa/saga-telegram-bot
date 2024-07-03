import urllib.request, urllib.error
import requests
import time
from datetime import datetime
import json
from bs4 import BeautifulSoup
import re

from typing import List

from zipcodes import get_neighborhoods_for_zipcode


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
    if html == "":
        print("COULD NOT READ HTML FROM SAGA")
        return {}

    all_links = []

    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all('a'):
        # print(link.get('href'))
        if "/immobiliensuche/immo-detail/" in link.get("href", ""):
            all_links.append("https://saga.hamburg" + link.get("href", ""))

    # remove duplicates
    all_links = list(set(all_links))

    return {
        "apartments": [link for link in all_links if any(x in link.lower() for x in ["wohnung", "apartment", "zimmer"])],
        "offices":  [link for link in all_links if any(x in link.lower() for x in ["buro", "büro", "gewerbe"])],
        "parking":  [link for link in all_links if any(x in link.lower() for x in ["stellplatz", ""])]
    }



def get_html_from_saga():
    post_address = "https://www.saga.hamburg/immobiliensuche?Kategorie=APARTMENT"
    

    try:
        req = urllib.request.Request(post_address)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0')
        req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
        req.add_header('Accept-Language', 'en-US,en;q=0.5')

        r = urllib.request.urlopen(req)

        if not r.code == 200:
            print("could not post to saga")
            print("Error code", r.code)
            print("Error", r.reason)
            return ""
        else:
            return r.read().decode('utf-8')

    except urllib.error.HTTPError as e:
        print("error while posting to saga " + str(e))
        return ""


def get_offer_title(link_to_offer):
    try:
        get_url = requests.get(link_to_offer)
        get_text = get_url.text
        soup = BeautifulSoup(get_text, "html.parser")

        title = soup.find_all('h1', class_='h3 ft-bold', limit=1)[0]

        return title.text

    except:
        return 'notitle '


# posts all information about an offer to telegram
def post_offer_to_telegram(offer_details, chat_id):
    send_msg_to_telegram("*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*", chat_id)

    def details_to_str(offer_details):
        if zipcode := offer_details.get("zipcode", None):
            neighborhoods = get_neighborhoods_for_zipcode(zipcode)
            
            return  f"Rent: {offer_details.get('rent')}€, Rooms: {offer_details.get('rooms', '?')}, Location: {offer_details.get('zipcode')} {', '.join(neighborhoods)}"
        
        return  f"Rent: {offer_details.get('rent')}€, Rooms: {offer_details.get('rooms', '?')}"


    for msg in [details_to_str(offer_details), offer_details.get("link")]:
        send_msg_to_telegram(msg, chat_id)



# sends a message to a telegram chat
def send_msg_to_telegram(msg, chat_id):
    token = get_value_from_config(["telegram_token"])

    msg = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + chat_id + '&parse_mode=Markdown&text=' + msg

    try:
        response = requests.get(msg)
        if not response.status_code == 200:
            print("could not forward to telegram")
            print("Error code", response.status_code, response.text)
            print(msg)
            exit()
            return False
    except requests.exceptions.RequestException as e:
        print("could not forward to telegram" + str(e))
        print("this was the message I tried to send: " + msg)



def is_offer_known(offer: str):
    return offer in open("known_offers.txt").read().splitlines()


def add_offers_to_known_offers(offers: dict):
    for offer_list in offers.values():
        for link in offer_list:
            if not is_offer_known(link):
                print("adding offer to known offers")
                file = open("known_offers.txt", "a+")
                file.write(link)
                file.write("\n")
                file.close()


def get_zipcode(offer_soup) -> int|None:
    zipcode = None

    text_xl_divs = offer_soup.find_all('div', class_='text-xl')  # address is in "text-xl" class
    if text_xl_divs:
        for div in text_xl_divs:
            print(div.string)

            if zipcode_like_strings:=re.findall('\d{5}', str(div.string)):
                zipcode = int(zipcode_like_strings[0])  # find zipcode by regex for 5digits
                break

    if not zipcode:
        return None
    
    return zipcode



def get_rent(offer_soup) -> float:
    # Example rent_string 1.002,68 €
    rent_string = offer_soup.find("td", text="Gesamtmiete").findNext("td").string
    rent_string = rent_string.replace('€', '').replace(' ', '')
    rent_string = rent_string.split(',')[0]  # ignore cents
    rent = rent_string.replace('.', '')  # replace 1.000 to be 1000

    return float(rent)


def get_rooms(offer_soup) -> int|None:
    try:
        rooms_string = offer_soup.find("td",string="Zimmer").findNext("td").string
    except AttributeError:
        # no info on rooms (happens for offices)
        return None


    try:
        rooms = int(rooms_string)
    except ValueError:
        # invalid literal for int() with base 10: '2 1/2'  there is "half rooms"
        rooms_string = rooms_string.split(" ")[0]
        rooms = int(rooms_string)

    return rooms


def get_offer_details(link:str) -> dict:
    details = {
        "rent": None,
        "zipcode": None,
        "rooms": None,
        "link": link
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
        print(f"COULD NOT GET ADDRESS FOR LINK {link}")


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
        print("new offer", offer_link)

        offer_details = get_offer_details(offer_link)

        # check rent price
        rent_until = criteria["rent_until"]       
        if offer_details.get("rent", 0) > rent_until:
            print(f"rent too high {offer_details.get('rent')}, {rent_until}")
            continue

        # check min rooms
        min_rooms = criteria.get("min_rooms", None)
        if min_rooms and min_rooms > offer_details.get("rooms", 0):
            print("not enough rooms")
            continue

        # check if zipcode is in zipcode whitelist
        zipcode_whitelist = criteria["zipcode_whitelist"]
        if zipcode_whitelist:
            if zipcode:= offer_details.get("zipcode", None):
                if zipcode not in zipcode_whitelist:
                    print("Offer not in zipcode whitelist")
                    continue

        # all criteria matched
        print("matching offer found", offer_link)
        matching_offers.append(offer_details)

    return matching_offers


if __name__ == "__main__":

    chat_ids = get_value_from_config(["chats"]).keys()

    for chat_id in chat_ids:
        if get_value_from_config(["chats", chat_id, "debug_group"]):
            send_msg_to_telegram("Bot started at " + str(datetime.now()), chat_id)

    while True:
        print("checking for updates ", datetime.now())
        current_offers = get_links_to_offers()

        # for each chat: send offer to telegram, if it meets the chat's criteria        
        for chat_id in chat_ids:
            matching_offers = offers_that_match_criteria(current_offers, chat_id)

            for offer in matching_offers:
                post_offer_to_telegram(offer, chat_id)

        # finally add to known offers
        add_offers_to_known_offers(current_offers)

        # check every 3 minutes
        time.sleep(180)
