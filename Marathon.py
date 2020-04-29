#Imports
from netmiko import ConnectHandler
import re, csv, sys, os
import logging
import datetime, time
import multiprocessing as mp

#Module 'Global' variables
DEVICE_FILE_PATH = 'devices.csv' # file should contain a list of devices in format: ip,username,password,device_type
BACKUP_DIR_PATH = os.path.join(sys.path[0],'backups') # backup directory

def enable_logging():
	# This function enables netmiko logging for reference

	logging.basicConfig(filename='test.log', level=logging.DEBUG)
	logger = logging.getLogger("netmiko")

def get_devices_from_file(device_file):
	# This function takes a CSV file with inventory and creates a python list of dictionaries out of it
	# Each disctionary contains information about a single device

	# creating empty structures
	device_list = list()
	device = dict()

	# reading a CSV file with ',' as a delimeter
	with open(device_file, 'r') as f:
		reader = csv.DictReader(f, delimiter=',')

		# every device represented by single row which is a dictionary object with keys equal to column names.
		for row in reader:
			device_list.append(row)

	print ("Got the device list from inventory")
	print('-*-' * 10)
	print ()

	# returning a list of dictionaries
	return device_list

def get_current_date_and_time():
	# This function returns the current date and time
	now = datetime.datetime.now()

	print("Got a timestamp")
	print('-*-' * 10)
	print()

	# Returning a formatted date string
	# Format: yyyy_mm_dd-hh_mm_ss
	return now.strftime("%Y_%m_%d-%H_%M_%S")

def connect_to_device(device):
	# This function opens a connection to the device using Netmiko
	# Requires a device dictionary as an input

	# Since there is a 'hostname' key, this dictionary can't be used as is
	connection = ConnectHandler(
		host = device['ip'],
		username = device['username'],
		password=device['password'],
		device_type=device['device_type'],
#		secret=device['secret']
	)

	print ('Opened connection to '+device['ip'])
	print('-*-' * 10)
	print()

	# returns a "connection" object
	return connection

def disconnect_from_device(connection, hostname):
	#This function terminates the connection to the device

	connection.disconnect()
	#print ('Connection to device {} terminated'.format(hostname))

def get_backup_file_path(hostname,timestamp):
	# This function creates a backup file name (a string)
	# backup file path structure is hostname/hostname-yyyy_mm_dd-hh_mm

	# checking if backup directory exists for the device, creating it if not present
	if not os.path.exists(os.path.join(BACKUP_DIR_PATH, hostname)):
		os.mkdir(os.path.join(BACKUP_DIR_PATH, hostname))

	# Merging a string to form a full backup file name
	backup_file_path = os.path.join(BACKUP_DIR_PATH, hostname, '{}-{}.txt'.format(hostname, timestamp))
	print('Backup file path will be '+backup_file_path)
	print('-*-' * 10)
	print()

	# returning backup file path
	return backup_file_path

def create_backup(connection, backup_file_path, hostname):
	# This function pulls running configuration from a device and writes it to the backup file
	# Requires connection object, backup file path and a device hostname as an input

	try:
		# sending a CLI command using Netmiko and printing an output
		connection.enable()
		output = connection.send_command('sh run')

		# creating a backup file and writing command output to it
		with open(backup_file_path, 'w') as file:
			file.write(output)
		print("Backup of " + hostname + " is complete!")
		print('-*-' * 10)
		print()

		# if successfully done
		return True

	except Error:
		# if there was an error
		print('Error! Unable to backup device ' + hostname)
		return False

def check_cdp(connection, hostname):
	# This function checks if CDP is on and tries to make it on if it's not
	# Requires connection object and a device hostname as an input

	try:
		# sending a CLI command using Netmiko and printing an output
		connection.enable()
		output = connection.send_command('sho run | in no cdp run')

		if not 'no cdp run' in output:
			print("CDP is OK in " + hostname)
			print('-*-' * 10)
		else:
			output = connection.send_config_set('cdp run')
			print("CDP is OK in " + hostname)
			print('-*-' * 10)
		
		output = connection.send_command('sho cdp neigh')
		cdp_neigh_num = len(parse_cdp_nei(output))
		if cdp_neigh_num:
			return 'CDP is on, ' + str(cdp_neigh_num) + ' peers'
		else:
			return 'CDP is off'

	except Error:
		# if there was an error
		print('Error! Unable to chaeck CDP on the device ' + hostname)
		return False

def parse_cdp_nei(cdp_nei_output):
	device_name = cdp_nei_output.split('>')[0].replace('\n','')
	# Split output to strings
	neighbors = cdp_nei_output.split('Port ID')[1].split('\n')
	
	connections_dict = {}
	
	# Delete empty elements 
	while '' in neighbors:
		neighbors.remove('')

	# Make dict for each string
	for neighbor_line in neighbors:
		connections_dict.update({(device_name, neighbor_line.split()[1]+neighbor_line.split()[2]):(neighbor_line.split()[0],neighbor_line.split()[-2]+neighbor_line.split()[-1])}) 
		
	return connections_dict

def config_ntp(connection, hostname, ntp_type):
	try:
		connection.enable()
		output = connection.send_config_set('clock timezone GMT 0')
		if ntp_type == 'server':
			output = connection.send_config_set('ntp master')
		elif ntp_type == 'client':
			output = connection.send_config_set('ntp server 192.168.194.101')
		time.sleep(5.0)
		output = connection.send_command('sho ntp status')
		if 'Clock is synchronized' in output:
			print("NTP is OK in " + hostname)
			print('-*-' * 10)
			# if successfully done
			return 'Clock in Sync'
		else:
			print("NTP is not OK in " + hostname)
			print('-*-' * 10)
			return 'Clock not in Sync'

	except Error:
		# if there was an error
		print('Error! Unable to check NTP on the device ' + hostname)
		return False

def Check_NPE(connection, hostname):
	try:
		connection.enable()
		output = connection.send_command('sho ver | in IOS')
		if 'k9' or 'K9' in output:
			print("PE IOS in " + hostname)
			print('-*-' * 10)
			return 'PE'
		else:
			print("NPE IOS in " + hostname)
			print('-*-' * 10)
			return 'NPE'

	except Error:
		# if there was an error
		print('Error! Unable to check ver on the device ' + hostname)
		return False

def Check_ver(connection, hostname):
	try:
		connection.enable()
		output = connection.send_command('sho ver | in IOS')
		ver = output.split(',')[2]
		print("IOS ver" + ver +' in ' + hostname)
		print('-*-' * 10)
		return ver
	except Error:
		# if there was an error
		print('Error! Unable to check ver on the device ' + hostname)
		return False

def Check_dev_pid(connection, hostname):
	try:
		connection.enable()
		output = connection.send_command('sho ver | in IOS')
		dev_pid = output.split(',')[1].split('Software')[0]
		print(hostname + ' is ' + dev_pid)
		print('-*-' * 10)
		return dev_pid
	except Error:
		# if there was an error
		print('Error! Unable to check ver on the device ' + hostname)
		return False

def process_target(device,timestamp,result):
	# This function will be run by each of the processes in parallel
	# This function implements a logic for a single device using other functions defined above:


	connection = connect_to_device(device)
	
	backup_file_path = get_backup_file_path(device['hostname'], timestamp)
	backup_result = create_backup(connection, backup_file_path, device['hostname'])
	pid = Check_dev_pid(connection, device['hostname'])
	ver = Check_ver(connection, device['hostname'])
	cdp = check_cdp(connection, device['hostname'])
	npe = Check_NPE(connection, device['hostname'])
	ntp = config_ntp(connection, device['hostname'], device['ntp_type'])

	disconnect_from_device(connection, device['hostname'])

	temp_str=device['hostname'] + '|' + pid + '|' + ver + '|' + npe + '|' + cdp + '|' + ntp

	print(temp_str)
	return temp_str

def main(*args):
	# This is a main function

	# Enable logs
	#enable_logging()

	# getting the timestamp string
	timestamp = get_current_date_and_time()

	# getting a device list from the file in a python format
	device_list = get_devices_from_file(DEVICE_FILE_PATH)

	# creating a empty list
	processes=list()

	result = []
	# Running workers to manage connections
	with mp.Pool(4) as pool:
		# Starting several processes...
		for device in device_list:
			processes.append(pool.apply_async(process_target, args=(device,timestamp, result)))
		# Waiting for results...
		for process in processes:
			result.append(process.get())
	
	with open(os.path.join(sys.path[0],'result.txt'), 'w') as the_file:
		the_file.write('\n'.join(result))
		the_file.close()		
	#print(result)

if __name__ == '__main__':
	# checking if we run independently
	_, *script_args = sys.argv
	
	# the execution starts here
	main(*script_args)
