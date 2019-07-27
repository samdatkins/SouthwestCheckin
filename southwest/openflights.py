import json

import pytz
import requests


    tzrequest = {
        "iata": airport_code,
        "country": "ALL",
        "db": "airports",
        "iatafilter": "true",
        "action": "SEARCH",
        "offset": "0",
    }
                 'offset': '0'}
    airport_tz = pytz.timezone(json.loads(tzresult.text)["airports"][0]["tz_id"])
    airport_tz = pytz.timezone(json.loads(tzresult.text)['airports'][0]['tz_id'])
    return airport_tz
