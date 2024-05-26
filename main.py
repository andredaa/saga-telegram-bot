import requests
import time
from datetime import datetime
import json
from bs4 import BeautifulSoup
import re

from typing import List


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
        return []

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
        r = requests.get(post_address, headers={'Content-Type': 'application/json'})
        if not r.status_code == 200:
            print("could post to saga")
            print("Error code", r.status_code)
            return ""
        else:
            return r.content

    except requests.exceptions.RequestException as e:
        print("error while posting to saga" + str(e))
        return ""


def get_offer_title(link_to_offer):
    try:
        get_url = requests.get(link_to_offer)
        get_text = get_url.text
        soup = BeautifulSoup(get_text, "html.parser")

        title = soup.find_all('h1', class_='h3 ft-bold', limit=1)[0]

        return title.text

    except:
        return ' '


# posts all information about an offer to telegram
def post_offer_to_telegram(link_to_offer, chat_id):
    send_msg_to_telegram("*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*", chat_id)
    for msg in [link_to_offer, get_offer_title(link_to_offer)]:
        send_msg_to_telegram(msg, chat_id)



# sends a message to a telegram chat
def send_msg_to_telegram(msg, chat_id):
    token = get_value_from_config(["telegram_token"])

    msg = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + chat_id + '&parse_mode=Markdown&text=' + msg

    try:
        response = requests.get(msg)
        if not response.status_code == 200:
            print("could not forward to telegram")
            print("Error code", response.status_code)
            return False
    except requests.exceptions.RequestException as e:
        print("could not forward to telegram" + str(e))
        print("this was the message I tried to send: " + msg)



def is_offer_known(offer: str):
    return offer in open("known_offers.txt").read().splitlines()


def add_offers_to_known_offers(offers: List[str]):
    for offer in offers:
        if not is_offer_known(offer):
            print("adding offer to known offers")
            file = open("known_offers.txt", "a+")
            file.write(offer)
            file.write("\n")
            file.close()


def is_offer_zipcode_in_whitelist(offer_soup, whitelisted_zipcodes:[int], link_to_offer):
    zipcode = None

    text_xl_divs = offer_soup.find_all('div', class_='text-xl')  # address is in "text-xl" class
    if text_xl_divs:
        for div in text_xl_divs:
            print(div.string)

            if zipcode_like_strings:=re.findall('\d{5}', str(div.string)):
                zipcode = int(zipcode_like_strings[0])  # find zipcode by regex for 5digits
                break

    if not zipcode:
        print("could not find address in link ", link_to_offer)
        return False
    
    if zipcode in whitelisted_zipcodes:
        print("zipcode in whitelist", zipcode)
        return True
    else:
        print("zipcode not in whitelist")
        return False



def is_offer_rent_below_max(offer_soup, max_rent) -> bool:
    # Example rent_string 1.002,68 €
    rent_string = offer_soup.find("td", text="Gesamtmiete").findNext("td").string
    rent_string = rent_string.replace('€', '').replace(' ', '')
    rent_string = rent_string.split(',')[0]  # ignore cents
    rent = rent_string.replace('.', '')  # replace 1.000 to be 1000

    print("rent", rent, max_rent)

    if float(rent) <= max_rent:
        return True

    return False


def is_offer_rooms_above_min_rooms(offer_soup, min_rooms) -> bool:
    rooms_string = offer_soup.find("td",string="Zimmer").findNext("td").string

    try:
        rooms = int(rooms_string)
    except ValueError:
        # invalid literal for int() with base 10: '2 1/2'  there is "half rooms"
        rooms_string = rooms_string.split(" ")[0]
        rooms = int(rooms_string)

    if rooms >= min_rooms:
        return True

    return False


# checks if the offer meets the criteria for this chat
def offers_that_match_criteria(links_to_all_offers, chat_id) -> List[str]:
    matching_offers = []

    criteria = get_value_from_config(["chats", chat_id, "criteria"])

    # get only offers of matching category (e.g. "apartments")
    offers = links_to_all_offers.get(criteria.get("category", "apartments"))

    for offer in offers:
        if is_offer_known(offer):
            continue    
        print("new offer", offer)

        # get details HTML
        get_url = requests.get(offer)
        get_text = get_url.text
        offer_soup = BeautifulSoup(get_text, "html.parser")
        print(offer_soup.prettify())

        # check rent price
        rent_until = criteria["rent_until"]
        print("max_rent", rent_until)
        if not is_offer_rent_below_max(offer_soup, max_rent=rent_until):
            print("rent too high")
            continue

        # check min rooms
        min_rooms = criteria.get("min_rooms", None)
        if min_rooms:
            print("min_rooms", min_rooms)
            if not is_offer_rooms_above_min_rooms(offer_soup, min_rooms=min_rooms):
                print("not enough rooms")
                continue

        # check if zipcode is in zipcode whitelist
        zipcode_whitelist = criteria["zipcode_whitelist"]
        if zipcode_whitelist and is_offer_zipcode_in_whitelist(offer_soup, zipcode_whitelist, offer):

            print("Offer not in zipcode whitelist")
            continue

        # all criteria matched
        matching_offers.append(offer)

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
