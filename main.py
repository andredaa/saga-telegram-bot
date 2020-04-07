import requests
import time
from datetime import datetime
import json
from bs4 import BeautifulSoup


def get_from_cfg(key: str) -> str:
    # import os#os.path.dirname(os.path.realpath(__file__)+
    with open("config.json") as file:
        js = json.load(file)
        return js[key]


def get_links_to_offers():
    html = get_html_from_saga()
    if html == "":
        return None

    links_to_offers = []

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all('a', class_='inner media', href=True)

    for link in links:
        if "/objekt/wohnungen/" in link['href']:
            links_to_offers.append("https://saga.hamburg" + link['href'])

    return links_to_offers


def get_html_from_saga():
    post_address = "https://www.saga.hamburg/immobiliensuche"
    request_data = {
        "sort": "preis",
        "perpage": 30,
        "type": "wohnungen",
        "rent_from": 200,
        "rent_until": 800
    }

    try:
        r = requests.post(post_address, json=request_data, headers={'Content-Type': 'application/json'})
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
    get_url = requests.get(link_to_offer)
    get_text = get_url.text
    soup = BeautifulSoup(get_text, "html.parser")

    title = soup.find_all('h1', class_='h3 ft-bold', limit=1)[0]

    return title.text


def post_offer_to_telegram(link_to_offer, offer_title=''):
    sucessfully_sent = []

    for msg in [link_to_offer, offer_title]:
        success = send_msg_to_telegram(msg)
        sucessfully_sent.append(success)

    return sucessfully_sent


def send_msg_to_telegram(msg):
    token = get_from_cfg("telegram_token")
    chat_id = get_from_cfg("chat_id")

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

        return False

    # only return True if the message was sucessfully communicated to telegram
    return True


if __name__ == "__main__":

    send_msg_to_telegram("Bot started at " + str(datetime.now()))

    while True:
        print("checking for updates ", datetime.now())
        offers = get_links_to_offers()

        for offer in offers:
            if offer not in open("known_offers.txt").read().splitlines():
                print("new offer", offer)
                # add offer to known offers, if sucessfully posted to telegram
                send_msg_to_telegram("*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*")
                if post_offer_to_telegram(offer, get_offer_title(offer)) == [True, True]:
                    file = open("known_offers.txt", "a+")
                    file.write(offer)
                    file.write("\n")
                    file.close()

        # check every 5 minutes
        time.sleep(300)
