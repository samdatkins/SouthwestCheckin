#!/usr/bin/env python
"""Southwest Checkin.

Usage:
  checkin.py FILE_NAME [-v | --verbose]
  checkin.py (-h | --help)
  checkin.py --version

Options:
  -h --help     Show this screen.
  -v --verbose  Show debugging information.
  --version     Show version.

"""
import sys
from datetime import datetime, timedelta
from math import trunc
from threading import Thread
from time import sleep, time

from dateutil.parser import parse
from docopt import docopt
from pytz import utc

from southwest import Reservation, openflights

CHECKIN_EARLY_SECONDS = 5


def schedule_checkin(flight_time, reservation):
    checkin_time = flight_time - timedelta(days=1)
    current_time = datetime.utcnow().replace(tzinfo=utc)
    # check to see if we need to sleep until 24 hours before flight
    if checkin_time > current_time:
        # calculate duration to sleep
        delta = (checkin_time - current_time).total_seconds() - \
            CHECKIN_EARLY_SECONDS
        # pretty print our wait time
        m, s = divmod(delta, 60)
        h, m = divmod(m, 60)
        print("Too early to check in.  Waiting {} hours, {} minutes, {} seconds".format(
            trunc(h), trunc(m), s))
        trusty_sleep(delta)
    data = reservation.checkin()
    for flight in data['flights']:
        for doc in flight['passengers']:
            print("{} got {}{}!".format(
                doc['name'], doc['boardingGroup'], doc['boardingPosition']))


def _auto_checkin(reservation_number, first_name, last_name, notify=[]):
    r = Reservation(reservation_number, first_name, last_name, notify)
    body = r.lookup_existing_reservation()

    # Get our local current time
    now = datetime.utcnow().replace(tzinfo=utc)
    tomorrow = now + timedelta(days=1)

    threads = []

    # find all eligible legs for checkin
    for leg in body['bounds']:
        # calculate departure for this leg
        airport = "{}, {}".format(
            leg['departureAirport']['name'], leg['departureAirport']['state'])
        takeoff = "{} {}".format(leg['departureDate'], leg['departureTime'])
        airport_tz = openflights.timezone_for_airport(
            leg['departureAirport']['code'])
        date = airport_tz.localize(
            datetime.strptime(takeoff, '%Y-%m-%d %H:%M'))
        if date > now:
            # found a flight for checkin!
            print("Flight information found, departing {} at {}".format(
                airport, date.strftime('%b %d %I:%M%p')))
            # Checkin with a thread
            t = Thread(target=schedule_checkin, args=(date, r))
            t.daemon = True
            t.start()
            threads.append(t)

    return threads


def batch_auto_checkin(file_name):
    threads = []
    with open(file_name) as file:
        content = file.readlines()

    lines = [x.strip() for x in content]
    for line in lines:
        try:
            [reservation_number, first_name, last_name, email] = line.split()
        except ValueError:
            print(f'Could not parse line {line}')
            continue

        # build out notifications
        notify = [{'mediaType': 'EMAIL', 'emailAddress': email}]
        new_threads = _auto_checkin(reservation_number,
                                    first_name, last_name, notify)
        threads.extend(new_threads)

    # cleanup threads while handling Ctrl+C
    while True:
        if len(threads) == 0:
            break
        for t in threads:
            t.join(5)
            if not t.isAlive():
                threads.remove(t)
                break

# sleep can't handle huge ints, so break it up in to smaller increments
MAX_SLEEP = 10000
def trusty_sleep(n):
    start = time()
    while (time() - start < n):
        time_remaining = n - (time() - start)
        sleep(min(time_remaining, MAX_SLEEP))

if __name__ == '__main__':

    arguments = docopt(__doc__, version='Southwest Checkin 0.2')
    file_name = arguments['FILE_NAME']

    try:
        batch_auto_checkin(file_name)
    except KeyboardInterrupt:
        print("Ctrl+C detected, canceling checkin")
        sys.exit()
