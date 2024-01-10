# saga-telegram-bot

This bot sends messages to telegram if new offers for apartment are posted on https://www.saga.hamburg/immobiliensuche .

## Make your own saga-telegram-bot

Create a telegram bot and add it to a group.
Get your telegram token and chat id.
Put them into a file called config.json, place it in the project dir. See config.json.example

__Example conf entry__

`{ 

    "telegram_token": "YOUR_TOKEN",
    "chats": {
        "-CHAT_ID_1": {
            "debug_group": false,
            "criteria": {
              "min_rooms": 1,
              "rent_from": 200,
              "rent_until": 800,
              "zipcode_whitelist": false
          }
        }
    }
}`

__CHAT_ID_1__ --> your chat id; str;

___debug_group__ --> Error messages will be forwarded to this group; boolean; 

__criteria__ 

    - min_rooms -->  min room count ;  int; 

    - rent_from --> min rent in Euro ;  int; 

    - rent_until --> max rent in Euro ;  int; 

    - zipcode_whitelist --> array of zipcodes to be considered ;  false or [int]; 


Run main.py



