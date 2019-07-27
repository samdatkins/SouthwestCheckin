#!/usr/bin/env python
"""Southwest Checkin.

Usage:
  checkin.py [-v | --verbose]
  checkin.py (-h | --help)
  checkin.py --version

Options:
  -h --help     Show this screen.
  -v --verbose  Show debugging information.
  --version     Show version.

"""
import logging
import sys
from datetime import date, datetime, timedelta
from math import trunc
from threading import Event, Thread
from time import sleep, time

from dateutil.parser import parse
from docopt import docopt
from pytz import utc

from gSheets import build_creds, get_last_modified_date, get_sheet_value_rows
from southwest import Reservation, openflights

CHECKIN_EARLY_SECONDS = 5

def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler('log.txt', mode='w')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(screen_handler)
    return logger

my_logger = setup_custom_logger("southwest")

def schedule_checkin(flight_time, reservation, force_stop_thread):
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
        my_logger.info("Too early to check in.  Waiting {} hours, {} minutes, {} seconds".format(
            trunc(h), trunc(m), s))
        
        # loop and sleep
        sleep_unless_thread_should_die(delta, force_stop_thread)
        if force_stop_thread.is_set():
            return
    data = reservation.checkin()
    for flight in data['flights']:
        for doc in flight['passengers']:
            my_logger.info("{} got {}{}!".format(
                doc['name'], doc['boardingGroup'], doc['boardingPosition']))


def _auto_checkin(reservation_number, first_name, last_name, notify=[]):
    r = Reservation(reservation_number, first_name, last_name, notify)
    body = r.lookup_existing_reservation()

    if body is None:
        my_logger.warning("Giving up on " + reservation_number)
        return

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
            my_logger.info("Flight information found, departing {} at {}".format(
                airport, date.strftime('%b %d %I:%M%p')))
            # Checkin with a thread
            stop_signal = Event()
            t = Thread(target=schedule_checkin, args=(date, r, stop_signal))
            t.daemon = True
            t.start()
            threads.append({'thread': t, 'signal': stop_signal})

    return threads


def batch_auto_checkin():
    threads = []

    creds = build_creds()
    try:
        time_sheet_last_modified = get_last_modified_date(creds)
    except:
        my_logger.error('Failed to load last modified date from sheets')
        return
    
    try:
        valuesRows = get_sheet_value_rows(creds)
    except:
        my_logger.error('Failed to load from google sheets')
        return

    for row in valuesRows:
        try:
            [reservation_number, first_name, last_name, email] = row
        except ValueError:
            print('Could not parse line ' + line)
            continue

        # build out notifications
        notify = [{'mediaType': 'EMAIL', 'emailAddress': email}]
        new_threads = _auto_checkin(reservation_number,
                                    first_name, last_name, notify)

        if new_threads is not None:
            threads.extend(new_threads)

    # cleanup threads while handling Ctrl+C
    while True:
        if len(threads) == 0:
            return
        for thread_and_signal in threads:
            t = thread_and_signal['thread']
            signal = thread_and_signal['signal']
            t.join(5)
            if not t.isAlive():
                threads.remove(thread_and_signal)
                break
            try:
                cur_modified_date = get_last_modified_date(creds)
            except:
                my_logger.error('Failed to load last modified date from sheets')
            if cur_modified_date > time_sheet_last_modified:
                # send signal to all threads to die
                [thread_signal['signal'].set() for thread_signal in threads]
                my_logger.info('Found new version of sheet, reloading')

MAX_SLEEP = 3
def sleep_unless_thread_should_die(n, force_stop_thread):
    start = time()
    while (time() - start < n):
        if force_stop_thread.is_set():
            return
        time_remaining = n - (time() - start)
        sleep(min(time_remaining, MAX_SLEEP))

if __name__ == '__main__':

    arguments = docopt(__doc__, version='Southwest Checkin 0.2')

    thread = None
    try:
        while True:
            batch_auto_checkin()
    except KeyboardInterrupt:
        print("Ctrl+C detected, canceling checkin")
        sys.exit()
