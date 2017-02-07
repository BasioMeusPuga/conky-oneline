#!/usr/bin/python

import sqlite3
import datetime
import argparse
from os.path import realpath, dirname, exists

""" Todo: Alarms, .ics parsing """

calendar_path = dirname(realpath(__file__)) + "/calendar.db"
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

	# Display all events that occur today
	if timeframe is None:

		status = database.execute("SELECT Date FROM status WHERE Date = '%s'" % (today)).fetchone()
		if status is not None:
			exit(1)

		events = database.execute("SELECT Name,Date,Repeat FROM events WHERE Date LIKE '%s'" % ('%' + str(today.month).zfill(2) + "-" + str(today.day).zfill(2) + '%')).fetchall()
		for i in events:
			date_object = datetime.datetime.strptime(i[1], '%Y-%m-%d')
			event_year = int(date_object.strftime('%Y'))
			event_repeat = i[2]

			if event_repeat == "yes" or (event_repeat == "no" and event_year == today.year):
				events_to_show.append(i[0])

		print(", ".join(events_to_show))

	# Display all events in the provided timeframe
	else:
		if timeframe.isdigit() is True:
			tf_pf = "+"
			tf_days = int(timeframe)
		else:
			tf_pf = timeframe[0]
			tf_days = int(timeframe[1:])

		valid_dates = []
		valid_dates_cfr = []
		for i in range(tf_days + 1):
			my_timedelta = datetime.timedelta(days=i)
			if tf_pf == "+":
				next_valid_date = str(today + my_timedelta)
			elif tf_pf == "-":
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

				if check_date == event_date_full or (check_date[5:] == event_date_dm and j[2]) == "yes":
					check_date_year = int(check_date[:4])
					days_away = abs(today - datetime.date(check_date_year, event_month, event_date))
					date_object = datetime.datetime.strptime(str(check_date_year) + "-" + event_date_dm, '%Y-%m-%d')
					sexy_date = date_object.strftime('%A, %d %B %Y')
					if j[2] == "no":
						events_to_show.append([j[0], sexy_date, days_away.days, "xrep"])
					else:
						events_to_show.append([j[0], sexy_date, days_away.days, "rep"])

		if events_to_show == []:
			print(colors.RED + "Nope." + colors.ENDC)
		else:
			events_to_show = sorted(events_to_show, key=lambda x: x[2])
			template = "{0:35}{1:30}{2:10}"
			print()
			if tf_pf == "-":
				day_display = colors.RED + "-Days".rjust(10) + colors.ENDC
			else:
				day_display = colors.GREEN + "+Days".rjust(10) + colors.ENDC
			print(template.format(colors.CYAN + "Name", "Date".rjust(35), day_display))
			for k in events_to_show:
				if k[3] == "xrep":
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
				if i[2] == "no":
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
			print(colors.RED + "Nope." + colors.ENDC)
	else:
		events_to_show = sorted(events_to_show, key=lambda x: x[2])
		template = "{0:35}{1:30}{2:10}"
		print()
		print(template.format(colors.GREEN + "Name", "Date".rjust(35), "+Days".rjust(10) + colors.ENDC))
		for k in events_to_show:
			print(template.format(k[0], k[1].rjust(30), k[2]))


def calendar_add():
	event_name = input("Name: ")
	event_name = event_name.replace("'", "")
	event_date = input("Date YYYY-MM-DD: ")
	try:
		datetime.datetime.strptime(event_date, '%Y-%m-%d')
	except:
		print(colors.RED + "Invalid date." + colors.ENDC)
		exit()
	event_repeat = input("Repeat? (Y/no) ")
	if event_repeat != "no":
		event_repeat = "yes"

	event_insert = input("Insert into Database? (yes/N) ")
	if event_insert == "yes":
		database.execute("INSERT INTO events (Name,Date,Repeat) VALUES ('{0}','{1}','{2}')".format(event_name, event_date, event_repeat))
		database.commit()


def calendar_seen():
	status = database.execute("SELECT Date FROM status WHERE Date = '%s'" % (today)).fetchone()
	if status is None:
		print("Today's events are marked " + colors.GREEN + "unseen" + colors.ENDC)
	else:
		print("Today's events are marked " + colors.RED + "seen" + colors.ENDC)
	events_seen = input("Toggle? (Y/no) ")
	if events_seen != "no":
		if status is None:
			database.execute("INSERT INTO status (Date) VALUES ('{0}')".format(today))
			database.commit()
		else:
			database.execute("DELETE FROM status")
			database.execute("VACUUM")


def main():
	parser = argparse.ArgumentParser(description='A CLI CALENDAR. IT\'S THE FUTURE.')
	parser.add_argument('searchfor', type=str, nargs='?', help='Search for event name', metavar="*searchstring*")
	parser.add_argument('--add', action='store_true', help='Add date to calendar')
	parser.add_argument('--seen', action='store_true', help='Toggle seen status for today\'s events')
	parser.add_argument('--show', type=str, nargs='?', const='BlankForAllIntensivePurposes', help='Show calendar events', metavar="±days")
	args = parser.parse_args()

	if args.searchfor:
		calendar_search(args.searchfor)
	elif args.add:
		calendar_add()
	elif args.seen:
		calendar_seen()
	elif args.show:
		calendar_show(args.show)
	else:
		parser.print_help()


if __name__ == '__main__':
	main()
	database.close()
