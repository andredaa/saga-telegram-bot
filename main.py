import requests
import re
import time
import json


def getFromCfg(key: str) -> str:
    # import os#os.path.dirname(os.path.realpath(__file__)+
    with open("config.json") as file:
        js = json.load(file)
        return js[key]


def get_links_to_offers():
    html = get_html_from_saga()
    if html == "":
        return None

    links_to_offers = []
    # split html into lines
    for bytestring in html.split(b'  '):
        string = str(bytestring)

        # filter html for links to appartment offers
        if re.search(r"\/objekt\/wohnungen\/\d*\.\d*.\d*", string):
            url_to_offer = "https://saga.hamburg" + re.search(r"\/objekt\/wohnungen\/\d*\.\d*.\d*", string).group(0)
            links_to_offers.append(url_to_offer)

    return links_to_offers

def get_html_from_saga():
    post_address = "https://www.saga.hamburg/immobiliensuche"
    request_data = {
        "sort": "preis",
        "perpage": 30,
        "type": "wohnungen",
        "rent_from": 500,
        "rent_until": 600
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


def post_to_telegram(link_to_offer):
    token = getFromCfg("telegram_token")
    chat_id = getFromCfg("chat_id")
    send_text = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + chat_id + '&parse_mode=Markdown&text=' + link_to_offer

    try:
        response = requests.get(send_text)
        if not response.status_code == 200:
            print("could not forward to telegram")
            print("Error code", response.status_code)
            return False
        else:
            return True
    except requests.exceptions.RequestException:
        print("could not forward to telegram" + str(link_to_offer))
        return False


if __name__ == "__main__":

    while True:
        offers = get_links_to_offers()

        for offer in offers:
            if offer not in open("known_offers.txt").read().splitlines():
                print("new offer", offer)
                if post_to_telegram(offer):
                    file = open("known_offers.txt", "a+")
                    file.write(offer)
                    file.write("\n")
                    file.close()

        # check every 5 minutes
        time.sleep(300)


