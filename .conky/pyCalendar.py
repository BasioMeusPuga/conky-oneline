#!/usr/bin/python

import sqlite3
import datetime
import argparse
from os.path import realpath, dirname, exists

""" Todo: Alarms """

# Create the database on first run
calendar_path = dirname(realpath(__file__)) + '/calendar.db'
if not exists(calendar_path):
	database = sqlite3.connect(calendar_path)
	database.execute("CREATE TABLE events (id INTEGER PRIMARY KEY,Name TEXT,Date TEXT,Repeat TEXT)")
	database.execute("CREATE TABLE status (id INTEGER PRIMARY KEY,Date TEXT)")

database = sqlite3.connect(calendar_path)
today = datetime.date.today()


class colors:
	CYAN = '\033[96m'
	GREEN = '\033[92m'
	RED = '\033[91m'
	WHITE = '\033[97m'
	YELLOW = '\033[93m'
	ENDC = '\033[0m'


def calendar_show(timeframe):
	events_to_show = []

	""" Display all events that occur today as csv
	This is mostly for displaying in a conky instance or something similar """
	if timeframe == 'BlankForAllIntensivePurposes':

		# Do not show events in case they're marked seen in the status table
		status = database.execute("SELECT Date FROM status WHERE Date = '%s'" % (today)).fetchone()
		if status is not None:
			exit(1)

		events = database.execute("SELECT Name,Date,Repeat FROM events WHERE Date LIKE '%s'" % ('%' + str(today.month).zfill(2) + "-" + str(today.day).zfill(2) + '%')).fetchall()
		for i in events:
			date_object = datetime.datetime.strptime(i[1], '%Y-%m-%d')
			event_year = int(date_object.strftime('%Y'))
			event_repeat = i[2]

			if event_repeat == 'yes' or (event_repeat == 'no' and event_year == today.year):
				events_to_show.append(i[0])

		if __name__ == '__main__':
			print(', '.join(events_to_show))
		else:
			return ', '.join(events_to_show)

		""" Display all events in the provided timeframe
		This shows as a table not really suited for parsing elsewhere """
	else:
		if timeframe.isdigit() is True:
			tf_pf = '+'
			tf_days = int(timeframe)
		else:
			tf_pf = timeframe[0]
			tf_days = int(timeframe[1:])

		valid_dates = []
		valid_dates_cfr = []
		for i in range(tf_days + 1):
			my_timedelta = datetime.timedelta(days=i)
			if tf_pf == '+':
				next_valid_date = str(today + my_timedelta)
			elif tf_pf == '-':
				next_valid_date = str(today - my_timedelta)

			valid_dates.append(next_valid_date)
			valid_dates_cfr.append(next_valid_date[5:])

		events = database.execute("SELECT Name,Date,Repeat FROM events").fetchall()

		for check_date in valid_dates:
			for j in events:
				event_date_full = j[1]
				event_date_dm = j[1][5:]
				event_date = int(j[1][8:])
				event_month = int(j[1][5:7])

				if check_date == event_date_full or (check_date[5:] == event_date_dm and j[2]) == 'yes':
					check_date_year = int(check_date[:4])
					days_away = abs(today - datetime.date(check_date_year, event_month, event_date))
					date_object = datetime.datetime.strptime(str(check_date_year) + '-' + event_date_dm, '%Y-%m-%d')
					sexy_date = date_object.strftime('%A, %d %B %Y')
					if j[2] == 'no':
						events_to_show.append([j[0], sexy_date, days_away.days, 'xrep'])
					else:
						events_to_show.append([j[0], sexy_date, days_away.days, 'rep'])

		if events_to_show == []:
			print(colors.RED + 'Nope.' + colors.ENDC)
		else:
			events_to_show = sorted(events_to_show, key=lambda x: x[2])
			template = "{0:35}{1:30}{2:10}"
			print()
			if tf_pf == '-':
				day_display = colors.RED + '-Days'.rjust(10) + colors.ENDC
			else:
				day_display = colors.GREEN + '+Days'.rjust(10) + colors.ENDC
			print(template.format(colors.CYAN + 'Name', 'Date'.rjust(35), day_display))
			for k in events_to_show:
				if k[3] == 'xrep':
					print(template.format(colors.YELLOW + k[0] + colors.ENDC, k[1].rjust(39), k[2]))
				else:
					print(template.format(k[0], k[1].rjust(30), k[2]))


def calendar_search(event_name):
	events_to_show = []
	events = database.execute("SELECT Name,Date,Repeat FROM events WHERE Name LIKE '%s'" % ('%' + event_name + '%')).fetchall()
	for i in events:
		event_date = int(i[1][8:])
		event_month = int(i[1][5:7])

		try:
			next_year = False
			if event_month < today.month or (event_date < today.day and event_month == today.month):
				if i[2] == 'no':
					raise
				next_year = True

			if next_year is False:
				days_away = abs(today - datetime.date(today.year, event_month, event_date))
				date_object = datetime.datetime.strptime(str(today.year) + "-" + i[1][5:], '%Y-%m-%d')
				sexy_date = date_object.strftime('%A, %d %B %Y')
			elif next_year is True:
				days_away = abs(today - datetime.date(today.year + 1, event_month, event_date))
				date_object = datetime.datetime.strptime(str(today.year + 1) + "-" + i[1][5:], '%Y-%m-%d')
				sexy_date = date_object.strftime('%A, %d %B %Y')

			events_to_show.append([i[0], sexy_date, days_away.days])
		except:
			pass

	if events_to_show == []:
			print(colors.RED + 'Nope.' + colors.ENDC)
	else:
		events_to_show = sorted(events_to_show, key=lambda x: x[2])
		template = "{0:35}{1:30}{2:10}"
		print()
		print(template.format(colors.GREEN + 'Name', 'Date'.rjust(35), '+Days'.rjust(10) + colors.ENDC))
		for k in events_to_show:
			print(template.format(k[0], k[1].rjust(30), k[2]))


def calendar_add():
	event_name = input('Name: ')
	event_name = event_name.replace('\'', '\'\'')
	event_date = input('Date YYYY-MM-DD: ')
	try:
		datetime.datetime.strptime(event_date, '%Y-%m-%d')
	except:
		print(colors.RED + 'Invalid date.' + colors.ENDC)
		exit()
	event_repeat = input('Repeat? (Y/n) ')
	if event_repeat.lower() != 'no' or event_repeat.lower() != 'n':
		event_repeat = 'yes'

	event_insert = input('Insert into Database? (y/N) ')
	if event_insert.lower() == 'yes' or event_insert.lower() == 'y':
		database.execute("INSERT INTO events (Name,Date,Repeat) VALUES ('{0}','{1}','yes')".format(event_name, event_date))
		database.commit()


def calendar_seen():
	status = database.execute("SELECT Date FROM status WHERE Date = '%s'" % (today)).fetchone()
	if status is None:
		print('Today\'s events are marked ' + colors.GREEN + 'unseen' + colors.ENDC)
	else:
		print('Today\'s events are marked ' + colors.RED + 'seen' + colors.ENDC)
	events_seen = input('Toggle? (Y/no) ')
	if events_seen != 'no':
		if status is None:
			database.execute("INSERT INTO status (Date) VALUES ('{0}')".format(today))
		else:
			database.execute("DELETE FROM status")
		database.commit()


def parse_ics(ics_file):
	""" The idea is to parse the .ics file for birthdays (and anniversaries)
	That means checking for 1 day long yearly recurrent events """

	# Open calendar file.
	my_cal = open(realpath(ics_file), 'r')
	_calendar = my_cal.readlines()
	my_cal.close()

	# Entries to pick up (or force ignore) from the .ics file
	valid_entries = ['DTSTART;', 'DTEND;', 'RRULE:FREQ=YEARLY', 'SUMMARY:']
	invalid_entries = ['SUMMARY:Alarm notification\n']

	# Check to see if the parsed yearly event is a valid birthday
	def isBirthday(event):

		# Reject anything that has less than 4 entries
		if len(event) < 4:
			return False, None

		# Reject a duration of more than 1 day
		start_date = event[0].split(':')[1].split('T')[0]
		date_object_start = datetime.datetime.strptime(start_date, '%Y%m%d')
		end_date = event[1].split(':')[1].split('T')[0]
		date_object_end = datetime.datetime.strptime(end_date, '%Y%m%d')

		time_delta = date_object_end - date_object_start
		if time_delta.days > 1:
			return (False,)

		# Reject if UNTIL date has already passed
		if 'UNTIL=' in event[2]:
			until_date = event[2].split('UNTIL=')[1].split(';')[0].split('T')[0]
			date_object_until = datetime.datetime.strptime(until_date, '%Y%m%d')
			today = datetime.datetime.today()
			if today - date_object_until < datetime.timedelta(0):  # This is the 'official' way to calculate a negative timedelta
				return (False,)

		""" If the above conditions aren't met, return True
		With a dictionary object containing the name and the date
		This will continue to be repeated """

		birthday_event = {
			'Name': event[3][8:],
			'Date': date_object_start
		}
		return (True, birthday_event)

	# Run through the .ics file
	event_list = []
	_copy = False
	for i in _calendar:

		""" Calendar events start with BEGIN:VEVENT, and end with END:VEVENT.
		We want them as long as RRULE:FREQ=YEARLY is present
		and the UNTIL value hasn't been exceeded """

		if _copy is False:
			if i == 'BEGIN:VEVENT\n':
				_copy = True
				this_event = []

		elif _copy is True:
			if i == 'END:VEVENT\n':
				_copy = False
				_check = isBirthday(this_event)
				if _check[0] is True:
					event_list.append(_check[1])

			positives = [i for j in valid_entries if j in i]
			if positives and positives[0] not in invalid_entries:
				this_event.append(positives[0].replace('\n', ''))

	""" We have the parsed data at this point
	Check to see if you really, really want to remember these ungrateful people
	and then add the relevant events to the calendar """
	_confirm = input('Found {0} events. Add them to the database? (y/N) '.format(len(event_list)))
	if _confirm == 'y' or _confirm == 'Y':
		for j in event_list:
			event_name = j['Name'].replace('\'', '\'\'')
			event_date = j['Date'].strftime('%Y-%m-%d')
			database.execute("INSERT INTO events (Name,Date,Repeat) VALUES ('{0}','{1}','yes')".format(event_name, event_date))
		database.commit()


def main():
	parser = argparse.ArgumentParser(description='A CLI CALENDAR. IT\'S THE FUTURE.')
	parser.add_argument('searchfor', type=str, nargs='?', help='Search for event name', metavar='*searchstring*')
	parser.add_argument('--add', action='store_true', help='Add date to calendar')
	parser.add_argument('--seen', action='store_true', help='Toggle seen status for today\'s events')
	parser.add_argument('--show', type=str, nargs='?', const='BlankForAllIntensivePurposes', help='Show calendar events', metavar='±days')
	parser.add_argument('--ics', type=str, nargs='+', help='Parse ics file for yearly events')
	args = parser.parse_args()

	if args.searchfor:
		calendar_search(args.searchfor)
	elif args.add:
		calendar_add()
	elif args.seen:
		calendar_seen()
	elif args.show:
		calendar_show(args.show)
	elif args.ics:
		parse_ics(args.ics[0])
	else:
		parser.print_help()


if __name__ == '__main__':
	main()
	database.close()
