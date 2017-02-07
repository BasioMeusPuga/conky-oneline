#!/usr/bin/python

import os
import time
import shlex
import random
import sqlite3
import requests
import argparse
import datetime
import subprocess
import pyCalendar


database_path = os.path.dirname(os.path.realpath(__file__)) + '/conky.db'
if not os.path.exists(database_path):
	database = sqlite3.connect(database_path)
	database.execute("CREATE TABLE conky (id INTEGER PRIMARY KEY, Name TEXT, Value TEXT)")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('ping', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('reminder_time', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('updates', '0')")
	database.execute("INSERT INTO conky (Name,Value) VALUES ('pacman_extra_cache', '0')")
	database.commit()
database = sqlite3.connect(database_path)


class Options:
	conky_color_yellow = '${color3}'
	conky_color_green = '${color4}'
	interface_name = 'tplink1'  # Wifi interface name
	ping_address = '8.8.8.8'
	tolerable_extra_cache = 300  # MiB
	qbittorrent_port = 9390


def format_time(time_in_seconds):
	if time_in_seconds >= 3600:
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
		for j in range(len(i)):
			if i[j] == '-' and i[j + 1].isdigit() is True:
				try:
					packages[i[:j]].append(i)
				except:
					packages[i[:j]] = [i]
				break

	duplicates = [packages[package] for package in packages.keys() if len(packages[package]) > 1]

	# The preceding code looks for a hyphen followed by a number to decide what the package name is.
	# That's clearly an affront to humanity. So:
	exceptions = ['ntfs']

	cached_not_installed = set(packages.keys()) - set(all_installed) - set(aur_installed)
	for l in cached_not_installed:
		if l not in exceptions:  # Calculated later so that extra cached packages are still included in the duplicate list
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
	output = '%.1f' % (total_extra * 9.5367e-7)  # Convert to MiB
	return int(float(output))  # This is because significant figure accuracy is horrible owing to questionable design decisions


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

	""" False if notification has to happen in the OFF state
	True if notification has to happen in the ON state
	The 2nd element of the list refers to a preferred sexy name """
	services = {
		'ufw': [False, 'Firewall'],
		'emby-server': [True, 'Emby'],
		'org.cups.cupsd': [True, None],
		'sshd': [False, None]}
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
				_output = special_case(i)
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
		active_torrents = requests.get('http://localhost:{0}/query/torrents?filter=active'.format(Options.qbittorrent_port)).json()
		all_torrents = requests.get('http://localhost:{0}/query/torrents?filter=downloading'.format(Options.qbittorrent_port)).json()
		if not active_torrents:
			raise
	except:
		return 0

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

	return total_active, total_all, first_torrent_eta, round(total_progress_percentage, 2)


class CalendarStuff:
	def __init__(self):
		pass

	def calendar_show(self, interval):
		pyCalendar.calendar_show(interval)  # Interval should be passed as a string

	def calendar_add(self):
		pyCalendar.calendar_add()

	def calendar_seen(self):
		pyCalendar.calendar_seen()


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
		reminder_time = float(database.execute("SELECT Value FROM conky WHERE Name = 'reminder_time'").fetchone()[0])
		if reminder_time > 0:
			reminder_time_remaining = reminder_time - time.time()
			return time.strftime('%H:%M:%S', time.gmtime(reminder_time_remaining))

	def unset_timer(self):
		database.execute("UPDATE conky SET Value = '0' WHERE Name = 'reminder_time'")
		database.commit()


def main():
	parser = argparse.ArgumentParser(description='Display stupid stuff in your conky instance. IT\'S THE FUTURE.')
	parser.add_argument('--pacman', action='store_true', help='Pending pacman updates')
	parser.add_argument('--pacmancache', action='store_true', help='Pacman redundant cache')
	parser.add_argument('--qbittorrent', action='store_true', help='Qbittorrent status')
	parser.add_argument('--ping', action='store_true', help='Ping status to specificed server')
	parser.add_argument('--timer', nargs='+', help='Timer functions (set requires an argument)', metavar='set <time> / reset / get')
	parser.add_argument('--services', action='store_true', help='Service status')
	parser.add_argument('--createchecks', action='store_true', help='Create database entries')
	parser.add_argument('--showchecks', nargs='+', help='Create database entries', metavar='updates / cache')

	args = parser.parse_args()

	# calendar functions still remain
	if args.pacman:
		print(Options.conky_color_yellow + str(pending_updates()))

	elif args.pacmancache:
		# This is an expensive function; I won't recommend putting it where it's executed continuously
		print(Options.conky_color_yellow + str(pacman_extra_cache()) + ' MiB')

	elif args.qbittorrent:
		qbittorrent_status = qbittorrent()
		if qbittorrent_status == 0:
			print('idle')
		elif qbittorrent_status == 1:
			print('fetching metadata')
		else:
			print(str(qbittorrent_status[0]) + ' (' + str(qbittorrent_status[1]) + ') | ' + str(qbittorrent_status[3]) + '% | ' + qbittorrent_status[2])

	elif args.ping:
		ping_output = ping()
		if ping_output is None:
			print('None')
			return
		if ping_output[1] > 0:
			print(Options.conky_color_yellow + ping_output[0] + ' (' + format_time(ping_output[1]) + ')')
		else:
			print(ping_output[0])

	elif args.services:
		print(service_status())

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

		""" The following helps with decreasing resource utilization.
		Instead of calling the relevant functions directly, it's a
		little better to just write the values to the database every
		few minutes and then check that instead """

	elif args.createchecks:
		database.execute("UPDATE conky SET Value = {0} WHERE Name = 'updates'".format(pending_updates()))
		database.execute("UPDATE conky SET Value = {0} WHERE Name = 'pacman_extra_cache'".format(pacman_extra_cache()))
		database.commit()

	elif args.showchecks:
		if args.showchecks[0] == 'updates':
			print(database.execute("SELECT Value FROM conky WHERE Name = 'updates'").fetchone()[0])
		elif args.showchecks[0] == 'cache':
			print(database.execute("SELECT Value FROM conky WHERE Name = 'pacman_extra_cache'").fetchone()[0])

	else:
		exit(1)


if __name__ == '__main__':
	main()
