#!/usr/bin/python

import os
import re
import time
import shlex
import random
import sqlite3
import requests
import argparse
import datetime
import subprocess
import pyCalendar
import collections


database_path = os.path.dirname(os.path.realpath(__file__)) + '/conky.db'
if not os.path.exists(database_path):
	database = sqlite3.connect(database_path)
	database.execute("CREATE TABLE conky (id INTEGER PRIMARY KEY, Name TEXT, Value TEXT)")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('ping', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('reminder_time', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('updates', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('pacman_extra_cache', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('qbittorrent', '0,0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('calendar_iterations', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('calendar_event', '0')")
	database.commit()
database = sqlite3.connect(database_path)


class Options:
	# You need to be here
	interface_name = 'tplink1'  # Wifi interface name
	ping_address = '8.8.8.8'
	tolerable_extra_cache = 300  # MiB
	show_cpu_over = 50  # Percentage CPU utilization (sum of all cores?)
	qbittorrent_port = 9390
	switch_calendar_event_after_iterations = 2  # Switch to next displayed calendar event after being called this many times
												# Multiply this by the conky update interval to get the event switch duration

	""" 1st element of list:
	False if notification has to happen in the OFF state
	True if notification has to happen in the ON state
	2nd element of list:
	Preferred sexy name """
	check_services = {
		'ufw': [False, 'Firewall'],
		'emby-server': [True, 'Emby'],
		'org.cups.cupsd': [True, None],
		'sshd': [False, None]}

	# Colors
	conky_color_white = '${color}'
	conky_color_gray = '${color2}'
	conky_color_yellow = '${color3}'
	conky_color_green = '${color4}'


def format_time(time_in_seconds):
	if time_in_seconds >= 86400:
		time_format = '%-dd %-Hh'
		time_in_seconds = time_in_seconds - 86400  # Huh?
	elif time_in_seconds >= 3600:
		time_format = '%-Hh %-Mm'
	elif time_in_seconds >= 60:
		time_format = '%-Mm'
	else:
		time_format = '%-Ss'
	return time.strftime(time_format, time.gmtime(time_in_seconds))


def pending_updates():
	pacman_process = subprocess.run('pacman -Qu', shell=True, stdout=subprocess.PIPE)
	updates = pacman_process.stdout.decode('utf-8').split('\n')
	number = -1
	for i in updates:
		if '[ignored]' not in i:
			number += 1
	return number


def pacman_extra_cache():
	all_installed_process = subprocess.run('pacman -Qqs', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE)
	all_installed = all_installed_process.stdout.decode().strip().split('\n')
	aur_installed_process = subprocess.run('pacman -Qmq', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE)
	aur_installed = aur_installed_process.stdout.decode().strip().split('\n')

	packages = {}
	duplicates = []

	pacman_cache = os.listdir('/var/cache/pacman/pkg')
	for i in pacman_cache:
		_regex_match = re.search(r"^(.+?)-\d{1,}\.", i)
		if _regex_match:
			try:
				packages[_regex_match.group(1)].append(i)
			except:
				packages[_regex_match.group(1)] = [i]

	duplicates = [packages[package] for package in packages.keys() if len(packages[package]) > 1]

	cached_not_installed = set(packages.keys()) - set(all_installed) - set(aur_installed)
	for l in cached_not_installed:
		duplicates.append(packages[l])

	""" This approximates file sizes but the
	code for version number comparison is well
	outside the scope of this script """
	total_extra = 0
	for k in duplicates:
		random.shuffle(k)
		for count, m in enumerate(k):
			check_package = '/var/cache/pacman/pkg/' + m
			package_size_lel = os.path.getsize(check_package)
			total_extra = total_extra + package_size_lel
			if count == len(k) - 2:
				break
	output = int(float('%.1f' % (total_extra * 9.5367e-7)))  # Convert to MiB - significant figure accuracy is horrible owing to questionable design decisions
	return output


def ping():
	args_to_subprocess = shlex.split('iwgetid ' + Options.interface_name)
	interface_process = subprocess.run(args_to_subprocess, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
	try:
		essid = interface_process.stdout.decode('utf-8').split()[1].split(':')[1].replace('"', '')
	except IndexError:
		return None

	time_diff = 0
	args_to_subprocess = shlex.split('ping -c1 -w1 ' + Options.ping_address)  # ping timeout is set to 1000 ms
	ping_process = subprocess.run(args_to_subprocess, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	if ping_process.returncode == 0:
		database.execute("UPDATE conky SET Value = 0 WHERE Name = 'ping'")
		database.commit()
	else:
		last_time = float(database.execute("SELECT Value FROM conky WHERE Name = 'ping'").fetchone()[0])
		current_time = time.time()
		if last_time == 0:
			database.execute("UPDATE conky SET Value = {0} WHERE Name = 'ping'".format(current_time))
			database.commit()
		else:
			time_diff = current_time - last_time

	return essid, time_diff


def service_status():
	def special_case(service_name):
		if i == 'ufw':
			ufw_internal = subprocess.run('sudo ufw status', shell=True, stdout=subprocess.PIPE)
			ufw_internal_status = ufw_internal.stdout.decode('utf-8').split()[1].strip()
			if ufw_internal_status == 'inactive':
				return (False, 'UFW (I)')
			else:
				return (True,)

	services = Options.check_services
	special_cases = ['ufw']

	toggled_services = []
	for i in services.keys():
		args_to_subprocess = shlex.split('systemctl status {0}'.format(i))
		systemctl_process = subprocess.run(args_to_subprocess, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output = systemctl_process.stdout.decode('utf-8').split('\n')

		try:
			if services[i][1] is not None:
				service_sexyname = services[i][1]
			else:
				service_sexyname = output[0].replace(i + '.service', '').split('-')[1].strip()

			if i in special_cases:
				_output = special_case(i)  # Output is added to whatever systemctl tells us
				if _output[0] is False:
					toggled_services.append(Options.conky_color_yellow + _output[1])

			service_status = output[2].split()[1]
			if service_status == 'active' and services[i][0] is True:
				toggled_services.append(Options.conky_color_green + service_sexyname)
			elif (service_status == 'inactive' or service_status == 'failed') and services[i][0] is False:
				toggled_services.append(Options.conky_color_yellow + service_sexyname)
		except IndexError:  # In case of deleted or invalid service files
			pass

	return ' '.join(toggled_services)


def qbittorrent():
	try:
		global_statistics = requests.get('http://localhost:{0}/query/transferInfo'.format(Options.qbittorrent_port)).json()
		active_torrents = requests.get('http://localhost:{0}/query/torrents?filter=active'.format(Options.qbittorrent_port)).json()
		all_torrents = requests.get('http://localhost:{0}/query/torrents?filter=downloading'.format(Options.qbittorrent_port)).json()
		if not active_torrents:
			raise
	except:
		return 0

	# Speed statistics
	def average_speed():
		""" Much more reliable as a function since this excludes all the
		error contingent returns """
		current_download_speed = global_statistics['dl_info_speed']
		database_speed = database.execute("SELECT Value FROM conky WHERE Name = 'qbittorrent'").fetchone()[0].split(',')

		speed_sum = int(database_speed[0]) + current_download_speed
		speed_iterations = int(database_speed[1]) + 1
		database.execute("UPDATE conky SET Value = '{0}' WHERE Name = 'qbittorrent'".format(str(speed_sum) + ',' + str(speed_iterations)))
		database.commit()

		average = float('%.1f' % (speed_sum / speed_iterations * 9.5367e-4))
		return average

	# Torrent statistics
	total_active = len(active_torrents)
	total_all = len(all_torrents)
	torrent_statistics = [[i['eta'], i['progress'], i['size']] for i in active_torrents]
	torrent_statistics.sort()

	first_torrent_eta_seconds = torrent_statistics[0][0]
	first_torrent_eta = format_time(first_torrent_eta_seconds)

	total_progress = 0
	total_size = 0
	for j in torrent_statistics:
		total_progress += j[1] * j[2]
		total_size += j[2]
	try:
		total_progress_percentage = total_progress / total_size * 100
	except ZeroDivisionError:  # Occurs when metadata is being fetched for just one active torrent
		return 1

	return total_active, total_all, round(total_progress_percentage, 2), first_torrent_eta, average_speed()


def cpu_top():
	""" Show CPU utilization for a process/processes exceeding Options.show_cpu_over
	Return None if no processes meet that criteria
	Processes with the same name are grouped together """

	args_to_subprocess = shlex.split('ps -eo pcpu,comm --sort=-%cpu --no-header')
	myProcess = subprocess.run(args_to_subprocess, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE)
	myProcess_out = myProcess.stdout.decode().split()

	cpu_util = {}
	for i in range(1, len(myProcess_out), 2):
		if myProcess_out[i] in cpu_util.keys():
			cpu_util[myProcess_out[i]] = round(cpu_util[myProcess_out[i]] + float(myProcess_out[i - 1]))
		else:
			try:
				cpu_util[myProcess_out[i]] = float(myProcess_out[i - 1])
			except ValueError:  # I'm not completely sure what's happening here
				pass

	cpu_util = {k: v for k, v in cpu_util.items() if v > Options.show_cpu_over and k != 'ConkyScript.py'}
	cpu_util = collections.OrderedDict(sorted(cpu_util.items(), key=lambda x: x[1], reverse=True))

	if cpu_util:
		return ', '.join(cpu_util.keys())
	else:
		return None


class Calendar:
	def __init__(self):
		pass

	def calendar_show(self):
		""" The pyCalendar module displays events in a tabulated manner for
		any integer interval passed as a string. """
		_today = pyCalendar.calendar_show('BlankForAllIntensivePurposes')
		number_of_events_today = len(_today)

		if number_of_events_today == 0:
			return None
		elif number_of_events_today == 1:
			return _today[0]
		else:
			""" Switch between the events of the day in case there are more than 1 """
			iterations = int(database.execute("SELECT Value FROM conky WHERE name = 'calendar_iterations'")
				.fetchone()[0]) + 1  # Because you had the bright idea of zero indexing this
			event_index = int(database.execute("SELECT Value FROM conky WHERE name = 'calendar_event'").fetchone()[0])

			if iterations < Options.switch_calendar_event_after_iterations:
				iterations += 1
			else:
				iterations = 0
				event_index += 1
				if event_index + 1 > number_of_events_today:
					event_index = 0

			database.execute("UPDATE conky SET Value = {0} WHERE Name = 'calendar_iterations'".format(iterations))
			database.execute("UPDATE conky SET Value = {0} WHERE Name = 'calendar_event'".format(event_index))
			database.commit()

			return '{0}. {1}'.format(event_index + 1, _today[event_index])

	def calendar_add(self):
		pyCalendar.calendar_add()

	def calendar_seen(self):
		pyCalendar.calendar_seen()

	def parse_ics(self, ics_file):
		pyCalendar.parse_ics(ics_file)


class Timer:
	def __init__(self):
		pass

	def set_timer(self, timer_interval):
		timer_interval.replace(' ', '')
		try:
			time_format = '%Hh%Mm'
			date_object = datetime.datetime.strptime(timer_interval, time_format)
		except ValueError:
			try:
				time_format = '%Mm'
				date_object = datetime.datetime.strptime(timer_interval, time_format)
			except:
				print('Valid formatting is <n>h<n>m or <n>m')
				exit(1)

		interval_seconds = date_object.hour * 3600 + date_object.minute * 60
		reminder_time = time.time() + interval_seconds
		print('Timer expires at ' + time.ctime(reminder_time))

		database.execute("UPDATE conky SET Value = {0} WHERE Name = 'reminder_time'".format(reminder_time))
		database.commit()

	def get_timer(self):
		timer_time = float(database.execute("SELECT Value FROM conky WHERE Name = 'reminder_time'").fetchone()[0])
		if timer_time > 0:
			time_remaining = timer_time - time.time()
			if time_remaining > 0:
				return time.strftime('%H:%M:%S', time.gmtime(time_remaining))
			else:
				args_to_subprocess = 'notify-send --urgency=critical -i dialog-information "Timer" "Expired at "' + time.ctime(timer_time)
				subprocess.run(shlex.split(args_to_subprocess))
				database.execute("UPDATE conky SET Value = '0' WHERE Name = 'reminder_time'")
				database.commit()

	def unset_timer(self):
		database.execute("UPDATE conky SET Value = '0' WHERE Name = 'reminder_time'")
		database.commit()


def main():
	parser = argparse.ArgumentParser(description='Display stupid stuff in your conky instance. IT\'S THE FUTURE.')
	parser.add_argument('--pacman', action='store_true', help='Pending pacman updates')
	parser.add_argument('--pacmancache', action='store_true', help='Pacman redundant cache')
	parser.add_argument('--services', action='store_true', help='Service status')
	parser.add_argument('--qbittorrent', action='store_true', help='Qbittorrent status')
	parser.add_argument('--ping', action='store_true', help='Ping status to specificed server')
	parser.add_argument('--calendar', nargs=1, help='Calendar functions', metavar='[show / add / seen / parse-ics <file>]')
	parser.add_argument('--timer', nargs='+', help='Timer functions (set requires an argument)', metavar='[set <time> / reset / get]')
	parser.add_argument('--createchecks', action='store_true', help='Create database entries')
	parser.add_argument('--top', action='store_true', help='Show processes that exceed specified CPU utilization')
	parser.add_argument('--showchecks', nargs=1, help='Display database entries created by --createchecks', metavar='[updates / cache]')
	parser.add_argument('--everything', action='store_true', help='EVERY SINGLE FUNCTION IS RETURNED AT ONCE')

	args = parser.parse_args()

	# Called in --everything _______________________________________________________
	if args.pacman:
		print(Options.conky_color_yellow + str(pending_updates()))

	elif args.pacmancache:
		print(Options.conky_color_yellow + str(pacman_extra_cache()) + ' MiB')

	elif args.services:
		print(service_status())

	elif args.top:
		cpu_top()

	elif args.timer:
		mytimer = Timer()
		if args.timer[0] == 'set':
			try:
				timer_interval = args.timer[1]
				mytimer.set_timer(timer_interval)
			except IndexError:
				print('Time required in format: <n>h<n>m or <n>m')
		elif args.timer[0] == 'reset':
			mytimer.unset_timer()
			print('Timer reset')
		elif args.timer[0] == 'get':
			output = mytimer.get_timer()
			if output is not None:
				print(output)

	elif args.calendar:
		mycalendar = Calendar()
		if args.calendar[0] == 'show':
			print(mycalendar.calendar_show())

			# All of the following are interactive
		elif args.calendar[0] == 'add':
			mycalendar.calendar_add()
		elif args.calendar[0] == 'seen':
			mycalendar.calendar_seen()
		elif args.calendar[0] == 'parse-ics':
			mycalendar.parse_ics(args.calendar[1])

		# NOT called in --everything _______________________________________________________
	elif args.qbittorrent:
		qbittorrent_status = qbittorrent()
		""" List index:
		0: Active torrents
		1: Queued torrents
		2: First torrent eta
		3: Total progress percentage """
		if qbittorrent_status == 0:
			print('idle')
		elif qbittorrent_status == 1:
			print('fetching metadata')
		else:
			print(str(qbittorrent_status[0]) +
				' (' + str(qbittorrent_status[1]) + ') | ' +
				str(qbittorrent_status[2]) + '% | ' +
				qbittorrent_status[3] + ' | ' +
				str(qbittorrent_status[4]) + ' KiB/s')

	elif args.ping:
		ping_output = ping()
		if ping_output is None:
			print('None')
			return
		if ping_output[1] > 0:
			print(Options.conky_color_yellow + ping_output[0] + ' (' + format_time(ping_output[1]) + ')')
		else:
			print(ping_output[0])

		""" The following arguments hopefully decrease resource utilization.
		Instead of calling the relevant functions directly, it's a
		little better to just write the values to the database every
		few minutes and then check that instead """

	elif args.createchecks:
		""" Zero out collected values for the qbittorent session
		The createchecks thingy is done only once every 120s though. So it won't work as intended if qbittorrent is restarted before that
		The actual number is unaffected despite that """
		qbittorrent_process = subprocess.run('pgrep qbittorrent', shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
		if qbittorrent_process.returncode != 0:
			database.execute("UPDATE conky SET Value = '0,0' WHERE Name = 'qbittorrent'")

		database.execute("UPDATE conky SET Value = {0} WHERE Name = 'updates'".format(pending_updates()))
		database.execute("UPDATE conky SET Value = {0} WHERE Name = 'pacman_extra_cache'".format(pacman_extra_cache()))
		database.commit()

	elif args.showchecks:
		if args.showchecks[0] == 'updates':
			print(database.execute("SELECT Value FROM conky WHERE Name = 'updates'").fetchone()[0])
		elif args.showchecks[0] == 'cache':
			print(database.execute("SELECT Value FROM conky WHERE Name = 'pacman_extra_cache'").fetchone()[0])

		# IS everything _______________________________________________________
	elif args.everything:
		""" Everything is called all at once here.
		Should decrease resource utilization considerably over checking everything in the conkyrc
		and then executing it twice over if the check succeeds"""
		final_output = []

		pacman_updates = int(database.execute("SELECT Value FROM conky WHERE Name = 'updates'").fetchone()[0])
		if pacman_updates > 0:
			final_output.append(Options.conky_color_gray + ' updates: ' + Options.conky_color_yellow + str(pacman_updates))

		pacman_cache = int(database.execute("SELECT Value FROM conky WHERE Name = 'pacman_extra_cache'").fetchone()[0])
		if pacman_cache > Options.tolerable_extra_cache:
			final_output.append(Options.conky_color_gray + ' cache: ' + Options.conky_color_yellow + str(pacman_cache) + ' MiB')

		calendar_today = Calendar().calendar_show()
		if calendar_today:
			final_output.append(Options.conky_color_gray + ' today: ' + Options.conky_color_white + calendar_today)

		services = service_status()
		if services:
			final_output.append(Options.conky_color_gray + ' services: ' + services)

		mytimer = Timer().get_timer()
		if mytimer:
			final_output.append(Options.conky_color_gray + ' timer: ' + Options.conky_color_white + mytimer)

		_cpu_top = cpu_top()
		if _cpu_top:
			final_output.append(Options.conky_color_gray + ' cpu: ' + Options.conky_color_yellow + _cpu_top)

		print(''.join(final_output))

	else:
		exit(1)


if __name__ == '__main__':
	main()
