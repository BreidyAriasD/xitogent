import time
import tempfile
import sys
import subprocess
import string
import ssl
import shutil
import requests
import re
import psutil
import pkgutil
import pickle
import os.path
import os
import math
import json
import jc.parsers.netstat
import datetime
import collections
import atexit
from requests import ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError, TooManyRedirects

#add cert data for the requests package

cert_data = pkgutil.get_data('certifi', 'cacert.pem')

handle = tempfile.NamedTemporaryFile(delete=False)
handle.write(cert_data)
handle.flush()

os.environ['REQUESTS_CA_BUNDLE'] = handle.name

#######################################

CORE_URL = 'https://app.xitoring.com/'
AGENT_URL = 'https://app.xitoring.com/xitogent/xitogent'
'https://vim /etc/yum.repos.d/xitogent.repo'
CONFIG_FILE = '/etc/xitogent/xitogent.conf'
PID_FILE = '/var/run/xitogent.pid'

#variables are used for auto updating
VERSION = '1.0.4'
LAST_UPDATE_ATTEMPT = ''
SENDING_DATA_SECONDS = 60

echo "[Xitogent]"
echo "name=Xitoring Agent on your machine"
echo "baseurl=https://mirror.xitoring.com/centos"
echo "enabled=1"
echo "gpgcheck=1"
echo "gpgkey=https://mirror.xitoring.com/centos/RPM-GPG-KEY-Xitogent"


def reset_items():
    try:
        if os.path.exists('/var/tmp/xitogent'):
            os.system('rm -rf /var/tmp/xitogent')
        os.mkdir('/var/tmp/xitogent')
    except:
        pass


def set_item(key, value):
    try:
        file = open('/var/tmp/xitogent/' + key, 'wb')
        pickle.dump({key: value}, file)
        file.close()
    except:
        pass


def get_item(key):
    try:
        with open('/var/tmp/xitogent/' + key, 'rb') as f:
            temp = pickle.load(f)
            return temp[key]
    except:
        return 0


def modify_config_file(data, delete_mode=False):

    config = read_config_file()

    for i in data:
        if delete_mode and i in config:
            del config[i]
        else:
            config[i] = data[i]

    config_path = get_config_path()

    config_file = open(config_path, 'w')

    for i in config:
        config_file.write(i + '=' + config[i] + '\n')

    config_file.close()


def get_api_key():
    for index, value in enumerate(sys.argv):
        if re.search("--key=", value):
            value = value.replace('--key=', '')
            return value.strip()
    sys.exit('The API key(--key) is required.')


def is_add_device():
    if len(sys.argv) > 1 and sys.argv[1] == 'register':
        return True
    return False


def add_device():
    try:
        params = {
            'ips': Linux.fetch_ips(),
            'hostname': Linux.fetch_hostname(),
            'preferences': generate_preferences_params()
        }

        headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + get_api_key()}

        if is_dev():
            global CORE_URL
            CORE_URL = 'http://localhost/'

        response = requests.post(CORE_URL + "devices/add", json=params, headers=headers)

        response.raise_for_status()

        data = decode_json(response.text)

        if data is not None:
            modify_config_file(data)

        print('Server has been registered successfully')

        sys.exit(0)

    except HTTPError as e:

        now = datetime.datetime.now()

        status_code = e.response.status_code

        message = now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:' + str(status_code) + ' - '

        #Bad request
        if status_code == 400:
            errors = []
            result = decode_json(e.response.text)
            if result is None:
                errors.append(e.response.text)
            else:
                for i in result:
                    errors.append(result[i][0])
            sys.exit(message + ", ".join(errors))

        #Unauthorize
        if status_code == 401:
            sys.exit(message + 'The API key is invalid')

        #Access denied
        if status_code == 403:
            temp = decode_json(e.response.text)
            if temp is None:
                sys.exit(message + e.response.text)
            else:
                text = temp['message'] if 'message' in temp else ''
                sys.exit(message + text)

        #Invalid url
        if status_code == 404:
            sys.exit(message + 'Server add URL is invalid')

        sys.exit(message + 'Unexpected error happened')

    except ConnectTimeout:
        sys.exit('Connection to the host has been Timed out')
    except ReadTimeout:
        sys.exit('Timed out while receiving data from the host')
    except Timeout:
        sys.exit('Request to the host has been Timed out')
    except ConnectionError:
        sys.exit('Failed to establish a connection')
    except TooManyRedirects:
        sys.exit('Too many redirects')
    except requests.exceptions.InvalidURL:
        sys.exit('URL is improperly formed or cannot be parsed')


def decode_json(str):
    try:
        return json.loads(str)
    except:
        return None


def is_dev():
    data = read_config_file(checking_version=True)
    if 'dev' in data and int(data['dev']) == 1:
        return True
    return False


def generate_preferences_params():

    preferences = {}

    value = find_argument_value('--group=')

    if value != '':
        preferences['group'] = value

    value = find_argument_value('--subgroup=')

    if value != '':
        preferences['subgroup'] = value

    value = find_argument_value('--notification=')

    if value != '':
        preferences['notification'] = value

    preferences['auto_discovery'] = is_auto_option_included('discovery')
    preferences['auto_trigger'] = is_auto_option_included('trigger')
    preferences['auto_update'] = is_auto_option_included('update')

    preferences['module_ping'] = is_module_included('ping')
    preferences['module_http'] = is_module_included('http')
    preferences['module_dns'] = is_module_included('dns')
    preferences['module_ftp'] = is_module_included('ftp')
    preferences['module_smtp'] = is_module_included('smtp')
    preferences['module_imap'] = is_module_included('imap')
    preferences['module_pop3'] = is_module_included('pop3')

    return preferences


def is_auto_option_included(name):

    value = find_argument_value('--auto_{}='.format(name))

    value = value.lower()

    if value != '' and value in ['true', 'false']:
        return value

    return 'false'


def is_module_included(name):

    value = find_argument_value('--module_{}='.format(name))

    value = value.lower()

    if value != '' and value in ['true', 'false']:
        return value

    return 'false'


def find_argument_value(argument):
    for index, value in enumerate(sys.argv):
        if re.search(argument, value):
            value = value.replace(argument, '')
            return value.strip()

    return ''


def read_config_file(checking_version=False, delete_device=False):

    config_path = get_config_path()

    if not os.path.isfile(config_path):
        if checking_version or delete_device:
            return {}
        else:
            sys.exit('Config file not found at the default path')
    try:
        f = open(config_path, 'r')
    except IOError:
        if checking_version or delete_device:
            return {}
        else:
            sys.exit('Config file not found at the default path')

    data = {}

    for line in f:

        if line.find('=') == -1:
            continue

        temp = line.split('=')

        if len(temp) > 2:
            continue

        name, value = temp

        if value.endswith('\n'):
            value = value.rstrip('\n')

        name = name.strip()

        name = name.lower()

        data[name] = value.strip()

    return data


def get_config_path():
    for index, value in enumerate(sys.argv):
        next_index = index + 1
        if value == '-c' and len(sys.argv) > next_index:
            return sys.argv[next_index]

    return CONFIG_FILE


def read_config(delete_device=False):

    data = read_config_file(delete_device=delete_device)

    if 'password' not in data:
        data['password'] = ''

    if 'uid' not in data:
        if delete_device:
            data['uid'] = ''
        else:
            sys.exit('UID does not exist in the config file')

    if 'node_url' not in data:
        data['node_url'] = retrieve_node_url(data['uid'], data['password'])

    data['node_url'] = add_http_to_url(data['node_url'])

    return data


def retrieve_node_url(uid, password):

    device = get_device_info(uid, password)

    if 'node_url' in device and device['node_url'] != '':
        modify_config_file({'node_url': device['node_url']})
        return device['node_url']

    return ''


def add_http_to_url(url):

    if url == '':
        return url

    if is_dev():
        if not url.startswith('http://'):
            url = 'http://' + url
    elif not url.startswith('https://'):
        url = 'https://' + url

    if not url.endswith('/'):
        url = url + '/'

    return url


def get_device_info(uid, password):
    try:
        if is_dev():
            global CORE_URL
            CORE_URL = 'http://localhost/'

        headers = {'Accept': 'application/json', 'uid': uid, 'password': password}

        response = requests.get(CORE_URL + "devices/" + uid, headers=headers)

        response.raise_for_status()

        return json.loads(response.text)

    except (ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError, TooManyRedirects, json.decoder.JSONDecodeError) as e:
        #Unauthorized
        if e.__class__.__name__ == 'HTTPError' and e.response.status_code == 401:
            sys.exit('Unauthorized action caused by Invalid Password or UID')
        pass

    return {}


def auto_update():
    global LAST_UPDATE_ATTEMPT
    LAST_UPDATE_ATTEMPT = time.time()
    if not download_new_xitogent():
        return None
    if validate_new_xitogent():
        replace_new_xitogent()
    else:
        run_command('rm -rf /etc/xitogent/test')


def download_new_xitogent():
    try:
        if os.path.exists('/etc/xitogent/test') and not run_command('rm -rf /etc/xitogent/test'):
            message = 'Failed to remove the test directory'
            report_failed_update(message)
            if is_force_update():
                sys.exit(message)
            return False

        try:
            os.mkdir('/etc/xitogent/test')
        except OSError as e:
            message = 'Failed to create the test directory'
            report_failed_update(message + '(' + str(e) + ')')
            if is_force_update():
                sys.exit(message)
            return False

        r = requests.get(AGENT_URL, allow_redirects=True)

        r.raise_for_status()

        try:
            open('/etc/xitogent/test/xitogent', 'wb').write(r.content)
        except OSError as e:
            message = 'Failed to move new xitogent into test directory'
            report_failed_update(message + '(' + str(e) + ')')
            if is_force_update():
                sys.exit(message)
            return False

        try:
            os.chmod('/etc/xitogent/test/xitogent', 0o755)
        except OSError as e:
            message = 'Failed to change mode of new xitogent file'
            report_failed_update(message + '(' + str(e) + ')')
            if is_force_update():
                sys.exit(message)
            return False

        return True

    except HTTPError as e:
        report_failed_update(str(e))
        status_code = e.response.status_code
        if status_code == 404 and is_force_update():
            sys.exit('Xitogent url is invalid')
        if is_force_update():
            sys.exit('Downloading new Xitogent failed')
    except requests.exceptions.SSLError as e:
        report_failed_update(str(e))
        if is_force_update():
            sys.exit('SSL handshake failed.')
    except requests.exceptions.Timeout as e:
        report_failed_update(str(e))
        if is_force_update():
            sys.exit('Request to the xitogent url has been Timed out')
    except (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema) as e:
        report_failed_update(str(e))
        if is_force_update():
            sys.exit('Xitogent url is improperly formed or cannot be parsed')
    except TooManyRedirects as e:
        report_failed_update(str(e))
        if is_force_update():
            sys.exit('Too many redirects')
    except Exception as e:
        report_failed_update(str(e))
        if is_force_update():
            sys.exit('Downloading new Xitogent failed')

    return False


def validate_new_xitogent():

    p = subprocess.Popen('/etc/xitogent/test/xitogent update-test', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    stdout, stderr = p.communicate()

    # error
    if p.returncode != 0:
        stderr = stderr.decode("utf-8")
        report_failed_update(stderr)
        return False

    output = stdout.decode("utf-8")

    # success
    if re.search("HTTP status:200", output):
        return True

    report_failed_update(output)

    return False


def report_failed_update(error_message):
    try:

        config_data = read_config()

        headers = {'Accept': 'application/json', 'uid': config_data['uid'], 'password': config_data['password']}

        if is_dev():
            global CORE_URL
            CORE_URL = 'http://localhost/'

        params = {'subject': 'update_failed', 'body': error_message}

        requests.post(CORE_URL + "send_report", json=params, headers=headers)

    except (ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError, TooManyRedirects):
        pass


def is_new_xitogent_test():
    for index, value in enumerate(sys.argv):
        if value == 'update-test':
            return True

    return False


def test_new_xitogent():
    send_data(read_config())
    sys.exit(0)


def replace_new_xitogent():

    try:
        source = '/etc/xitogent/test/'
        dest = '/usr/bin/'
        fileName = 'xitogent'
        shutil.move(os.path.join(source, fileName), os.path.join(dest, fileName))
    except Exception:
        if is_force_update():
            sys.exit('Failed to move Xitogent file from test directory to current directory')
        pass

    if not run_command('rm -rf /etc/xitogent/test'):
        if is_force_update():
            print('Failed to remove the test directory')
        pass

    if is_centos6():
        cmd = 'service xitogent restart'
    else:
        cmd = 'systemctl restart xitogent'

    if not run_command(cmd):
        if is_force_update():
            sys.exit('Failed to start new Xitogent')
        pass

    if is_force_update():
        print('Xitogent has been updated from v{} to {} successfully'.format(VERSION, find_new_version()))


def find_new_version():

    p = subprocess.Popen('xitogent version', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    stdout, stderr = p.communicate()

    # error
    if p.returncode != 0:
        return ''

    stdout = stdout.decode("utf-8")

    found = re.search(r"v(\d+(\.\d+)?(\.\d+)?)", stdout)

    if found:
        return stdout[found.start():found.end()]

    return ''


def is_force_update():
    if len(sys.argv) > 1 and sys.argv[1] == 'update':
        return True
    return False


def force_update():
    download_new_xitogent()
    replace_new_xitogent()


def run_command(cmd):

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    stdout, stderr = p.communicate()

    # error
    if p.returncode != 0:
        return False

    return True


def is_centos6():

    os = Linux.get_os()

    os = os.lower()

    is_centos = re.search("centos", os)

    temp = re.findall(r'\d+(?:\.\d+)*', os)

    version = temp[0].split('.')

    if is_centos and int(version[0]) <= 6:
        return True

    return False


def is_start_mode():
    if len(sys.argv) > 1 and sys.argv[1] == 'start':
        return True
    return False


def start():

    if is_running():
        sys.exit('Already running')

    reset_items()

    if is_start_as_daemon():
        daemonize()
    else:
        save_pid()

    config_data = read_config()

    set_item('uptime', int(time.time()))

    while True:
        if not is_device_paused():
            send_data(config_data)
        else:
            print('Xitogent is paused')
            inquire_pause_status()
        time.sleep(SENDING_DATA_SECONDS)


def increment_variable(name):

    old_value = get_item(name)

    if old_value:
        set_item(name, int(old_value) + 1)
    else:
        set_item(name, 1)


def is_process_running(pid):

    for proc in psutil.process_iter():

        try:
            if proc.pid == int(pid):
                return True
        except psutil.NoSuchProcess:
            pass

    return False


def save_pid():
    pid = str(os.getpid())
    file = open(PID_FILE, 'w+')
    file.write("%s\n" % pid)
    file.close()


def is_running():
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE) as file:
                pid = file.read().strip()
                if is_process_running(pid):
                    return True
        except Exception as e:
            pass

    return False


def is_start_as_daemon():
    if '-d' in sys.argv or '--daemon' in sys.argv:
        return True
    return False


def daemonize():

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit("fork #1 failed")

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit("fork #2 failed")

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')

    try:
        se = open(os.devnull, 'a+', 0)
    except ValueError:
        # Python 3 can't have unbuffered text I/O
        se = open(os.devnull, 'a+', 1)

    try:
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
    except Exception:
        pass

    # write pidfile
    try:
        atexit.register(del_pid_file)
        pid = str(os.getpid())
        file = open(PID_FILE, 'w+')
        file.write("%s\n" % pid)
        file.close()
    except Exception:
        pass


def del_pid_file():
    if os.path.isfile(PID_FILE):
        os.remove(PID_FILE)


def is_device_paused():

    config_data = read_config()

    if 'pause_until' not in config_data:
        return False

    if config_data['pause_until'] != '' and int(config_data['pause_until']) >= time.time():
        return True

    return False


def inquire_pause_status():
    try:

        config_data = read_config()

        global CORE_URL

        if is_dev():
            CORE_URL = 'http://localhost/'

        headers = {'Accept': 'application/json', 'uid': config_data['uid'], 'password': config_data['password']}

        response = requests.get("{core_url}devices/{uid}/check-pause".format(core_url=CORE_URL, uid=config_data['uid']), headers=headers)

        response.raise_for_status()

        response = json.loads(response.text)

        if not response['is_paused']:
            modify_config_file({'pause_until': ''}, delete_mode=True)

    except (ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError, TooManyRedirects, json.decoder.JSONDecodeError) as e:
        pass


def send_data(config_data):

    global SENDING_DATA_SECONDS

    if config_data['node_url'] == '':
        print('\nFinding the nearest node to your server...\n')
        node_url = retrieve_node_url(config_data['uid'], config_data['password'])
        config_data['node_url'] = add_http_to_url(node_url)
        SENDING_DATA_SECONDS = 5
        return None
    else:
        SENDING_DATA_SECONDS = 60

    url = config_data['node_url'] + "devices/" + config_data['uid'] + "/statistics/add"

    try:

        params = {'data': Linux.fetch_data(), 'version': VERSION}

        if not has_quiet_flag() and has_verbose_flag():
            print(params)

        headers = {'Accept': 'application/json', 'uid': config_data['uid'], 'password': config_data['password']}

        response = requests.post(url, json=params, headers=headers)

        now = datetime.datetime.now()

        #success
        if response.status_code == 200:

            if not has_quiet_flag():
                print('\n' + now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:200\n')

            response = decode_json(response.text)

            if response is not None:
                needs_update = 'update' in response and response['update']
                if needs_update and can_be_updated():
                    auto_update()

            increment_variable('sent_sequences')

            return None

        message = now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:' + str(response.status_code) + ' - '

        #Bad request
        if response.status_code == 400:

            errors = []
            result = decode_json(response.text)

            if result is not None:
                if 'pause_until' in result:
                    modify_config_file({'pause_until': str(result['pause_until'])})
                    del result['pause_until']

                for i in result:
                    if isinstance(result[i], list):
                        errors.append(result[i][0])
                    else:
                        errors.append(result[i])

            if not has_quiet_flag():
                if has_verbose_flag():
                    print("\n" + message + ", ".join(errors))
                else:
                    print('\n' + now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:400\n')

            increment_variable('failed_sequences')

            return None

        #Unauthorized
        if response.status_code == 401:

            if not has_quiet_flag():
                if has_verbose_flag():
                    print('\n' + message + 'Unauthorized action caused by Invalid Password or UID' + '\n')
                else:
                    print('\n' + now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:401\n')

            increment_variable('failed_sequences')

            return None

        #url not found or uid is invalid
        if response.status_code == 404:
            try:
                result = json.loads(response.text)
                if not has_quiet_flag():
                    if has_verbose_flag():
                        print('\n' + message + str(result['message']) + '\n')
                    else:
                        print('\n' + now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:404\n')
            except Exception:
                if not has_quiet_flag():
                    if has_verbose_flag():
                        print('\n' + message + 'URL not found' + '\n')
                    else:
                        print('\n' + now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:404\n')
            increment_variable('failed_sequences')
            return None

        if not has_quiet_flag():
            if has_verbose_flag():
                print('\n' + message + str(response.text))
            else:
                print('\n' + now.strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:500\n')

        increment_variable('failed_sequences')

    except HTTPError as e:
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nHTTP Exception for ' + url + '\n')
            else:
                status_code = e.response.status_code
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:' + status_code + '\n')
        increment_variable('failed_sequences')
    except ConnectTimeout:
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nTimed out while connecting to the host\n')
            else:
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - Connection timeout\n')
        increment_variable('failed_sequences')
    except ReadTimeout:
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nTimed out while receiving data from the host\n')
            else:
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - Read timeout\n')
        increment_variable('failed_sequences')
    except Timeout:
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nTimed out while requesting to the host\n')
            else:
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - Timeout\n')
        increment_variable('failed_sequences')
    except ConnectionError:
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nFailed to establish a connection\n')
            else:
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - Connection error\n')
        node_url = retrieve_node_url(config_data['uid'], config_data['password'])
        if node_url:
            config_data['node_url'] = add_http_to_url(node_url)
        increment_variable('failed_sequences')
    except TooManyRedirects:
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nToo many redirects\n')
            else:
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - Too many redirects\n')
        increment_variable('failed_sequences')
    except (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema):
        if not has_quiet_flag():
            if has_verbose_flag():
                print('\nURL is improperly formed or cannot be parsed\n')
            else:
                print('\n' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ' - HTTP status:404\n')
        node_url = retrieve_node_url(config_data['uid'], config_data['password'])
        config_data['node_url'] = add_http_to_url(node_url)
        increment_variable('failed_sequences')


def can_be_updated():

    try:
        global LAST_UPDATE_ATTEMPT

        if LAST_UPDATE_ATTEMPT == '':
            return True

        DAY_IN_SECONDS = 86400

        diff = time.time() - LAST_UPDATE_ATTEMPT

        if diff > DAY_IN_SECONDS:
            return True

    except Exception:
        pass

    return False


def is_uninstall():
    if len(sys.argv) > 1 and sys.argv[1] == 'uninstall':
        return True
    return False


def uninstall():

    try:

        uninstall_xitogent = prompt("Are you sure you want to uninstall Xitogent?[y/N]:")

        if uninstall_xitogent.lower() != 'y':
            sys.exit(0)

        delete_from_database = prompt("Delete the server from database?[y/N]:")

        if delete_from_database.lower() != 'y':
            delete_xitogent()
            sys.exit(0)

        delete_device()

        delete_xitogent()

        sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        print('\n')
        sys.exit(0)


def delete_device():
    try:
        config_data = read_config(delete_device=True)

        if is_dev():
            global CORE_URL
            CORE_URL = 'http://localhost/'

        url = CORE_URL + "devices/" + config_data['uid'] + "/uninstall"
        headers = {'Accept': 'application/json', 'uid': config_data['uid'], 'password': config_data['password']}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print('This server has been deleted from the database successfully')
    except (ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError, TooManyRedirects):
        print('Cannot delete this server from the database.')


def prompt(string):

    #python2
    if sys.version_info[0] == 2:
        return raw_input(string)

    #python3
    if sys.version_info[0] == 3:
        return input(string)

    return None


def delete_xitogent():

    if is_centos6():
        service_path = '/etc/init.d/xitogent'
        stop_xitogent_cmd = 'service xitogent stop'
    else:
        service_path = '/etc/systemd/system/xitogent.service'
        stop_xitogent_cmd = 'systemctl stop xitogent'

    if not run_command(stop_xitogent_cmd):
        sys.exit('Failed to stop service')

    if not run_command('rm -rf ' + service_path):
        sys.exit('Failed to delete ' + service_path + ' file')

    if not run_command('rm -rf /etc/xitogent'):
        sys.exit('Failed to delete /etc/xitogent directory')

    if not run_command('rm -rf /usr/bin/xitogent'):
        sys.exit('Failed to delete /usr/bin/xitogent directory')

    print('Xitogent uninstalled successfully')


def is_initial_test():
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        return True
    return False


def get_device_status():

    hostname = Linux.fetch_hostname()

    if type(hostname) == dict:
        print('Testing hostname ' + '... failed')
    else:
        print('Testing hostname ' + '... OK')

    os = Linux.get_os()

    if type(os) == dict:
        print('Testing os ' + '... failed')
    else:
        print('Testing os ' + '... OK')

    uptime = Linux.fetch_uptime()

    if type(uptime) == dict:
        print('Testing uptime ' + '... failed')
    else:
        print('Testing uptime ' + '... OK')

    timezone = Linux.get_timezone()

    if type(timezone) == dict:
        print('Testing timezone ' + '... failed')
    else:
        print('Testing timezone ' + '... OK')

    cpu_model_name = Linux.get_cpu_model_name()

    if type(cpu_model_name) == dict:
        print('Testing cpu model name ' + '... failed')
    else:
        print('Testing cpu model name ' + '... OK')

    cpu_count = Linux.get_cpu_count()

    if type(cpu_count) == dict:
        print('Testing cpu count ' + '... failed')
    else:
        print('Testing cpu count ' + '... OK')

    ips = Linux.fetch_ips()

    if type(ips) == dict:
        print('Testing ips ' + '... failed')
    else:
        print('Testing ips ' + '... OK')

    cpu_usage = Linux.fetch_cpu_usage()

    if 'status' in cpu_usage:
        print('Testing cpu usage ' + '... failed')
    else:
        print('Testing cpu usage ' + '... OK')

    load_average = Linux.fetch_cpu_load_average()

    if 'status' in load_average:
        print('Testing load average ' + '... failed')
    else:
        print('Testing load average ' + '... OK')

    disk_usage = Linux.fetch_disk_usage()

    if 'status' in disk_usage:
        print('Testing disk usage ' + '... failed')
    else:
        print('Testing disk usage ' + '... OK')

    disk_io = Linux.fetch_disk_io()

    if 'status' in disk_io:
        print('Testing disk io ' + '... failed')
    else:
        print('Testing disk io ' + '... OK')

    memory_usage = Linux.fetch_memory_usage()

    if 'status' in memory_usage:
        print('Testing memory usage ' + '... failed')
    else:
        print('Testing memory usage ' + '... OK')

    network = Linux.fetch_network()

    if 'status' in network:
        print('Testing network ' + '... failed')
    else:
        print('Testing network ' + '... OK')

    detected_softwares = Linux.find_detected_softwares()

    if type(detected_softwares) == dict:
        print('Testing detected softwares ' + '... failed')
    else:
        print('Testing detected softwares ' + '... OK')

    top_five_memory_processes = Linux.find_top_five_memory_consumer_processes()

    if type(top_five_memory_processes) == dict:
        print('Testing top 5 memory processes ' + '... failed')
    else:
        print('Testing top 5 memory processes ' + '... OK')

    top_five_cpu_processes = Linux.find_top_five_cpu_consumer_processes()

    if type(top_five_cpu_processes) == dict:
        print('Testing top 5 cpu processes ' + '... failed')
    else:
        print('Testing top 5 cpu processes ' + '... OK')

    sys.exit(0)


def is_show_commands_mode():
    if len(sys.argv) == 1 \
            or (
            not is_add_device()
            and not is_start_mode()
            and not is_uninstall()
            and not is_force_update()
            and not is_version_mode()
            and not is_initial_test()
            and not is_new_xitogent_test()
            and not is_pause_mode()
            and not is_unpause_mode()
            and not is_status_mode()
            and not is_stop_mode()
            and not is_restart_mode()
    ):
        return True
    return False


def show_commands():
    print('%-15s' '%s' % ('Xitogent v' + VERSION, '('+ CORE_URL + ')'))
    print("", '')
    print('%-15s' '%s' % ('register', 'Add a server'))
    print('%-15s' '%s' % ('', 'options:'))
    print('%-15s' '%-16s %s' % ('', '--key', 'Your unique account key for adding new server - found on your control panel '))
    print('%-15s' '%-16s %s' % ('', '--group', 'Server\'s group name as string'))
    print('%-15s' '%-16s %s' % ('', '--subgroup', 'Server\'s subgroup name as string'))
    print('%-15s' '%-16s %s' % ('', '--notification', 'default notification role name as string'))
    print('%-15s' '%-16s %s' % ('', '--auto_discovery', 'Always looking for any new detected service'))
    print('%-15s' '%-16s %s' % ('', '--auto_trigger', 'Create new trigger'))
    print('%-15s' '%-16s %s' % ('', '--auto_update', 'Enable auto update for Xitogent'))
    print('%-15s' '%-16s %s' % ('', '--module_ping', 'Create ping module automatically'))
    print('%-15s' '%-16s %s' % ('', '--module_http', 'Create http module automatically'))
    print('%-15s' '%-16s %s' % ('', '--module_dns', 'Create dns module automatically'))
    print('%-15s' '%-16s %s' % ('', '--module_ftp', 'Create ftp module automatically'))
    print('%-15s' '%-16s %s' % ('', '--module_smtp', 'Create smtp module automatically'))
    print('%-15s' '%-16s %s' % ('', '--module_imap', 'Create imap module automatically'))
    print('%-15s' '%-16s %s' % ('', '--module_pop3', 'Create pop3 module automatically'))
    print('%-15s' '%s' % ('start', 'Start Xitogent (sending data)'))
    print('%-15s' '%s' % ('', 'options:'))
    print('%-15s' '%-16s %s' % ('', '--daemon', 'Start as daemon'))
    print('%-15s' '%-16s %s' % ('', '--verbose', 'Verbose mode. Causes Xitogent to print debugging messages about its progress.\n This is helpful in debugging connection, authentication, and configuration problems'))
    print('%-15s' '%-16s %s' % ('', '--quiet', 'Silent mode'))
    print('%-15s' '%s' % ('stop', 'Stop Xitogent'))
    print('%-15s' '%s' % ('restart', 'Restart Xitogent'))
    print('%-15s' '%s' % ('uninstall', 'Uninstall Xitogent and remove server on your control panel'))
    print('%-15s' '%s' % ('update', 'Force update Xitogent'))
    print('%-15s' '%s' % ('pause', 'Pause Xitogent'))
    print('%-15s' '%s' % ('', 'options:'))
    print('%-15s' '%s' % ('', 'm (minute) _ h (hour) _ d (day) _ w (week)'))
    print('%-15s' '%s' % ('', 'Usage: xitogent pause 3d'))
    print('%-15s' '%s' % ('unpause', 'Unpause Xitogent'))
    print('%-15s' '%s' % ('help', 'Show Xitogent\' s commands'))
    print('%-15s' '%s' % ('version', 'Show Xitogent\' s version'))
    print('%-15s' '%s' % ('status', 'Show Xitogent\' s status'))
    sys.exit(0)


def is_version_mode():
    if len(sys.argv) > 1 and sys.argv[1] == '--version' or sys.argv[1] == 'version' or sys.argv[1] == '-v':
        return True
    return False


def show_xitogent_version():
    if is_dev():
        print('Xitogent v' + VERSION + ' (' + 'http://localhost/' + ')' )
    else:
        global CORE_URL
        print('Xitogent v' + VERSION + ' (' + CORE_URL + ')' )
    sys.exit(0)


def is_pause_mode():
    if len(sys.argv) > 1 and sys.argv[1] == 'pause':
        return True
    return False


def pause():

    try:

        pause_until = fetch_pause_until()

        config_data = read_config()

        global CORE_URL

        if is_dev():
            CORE_URL = 'http://localhost/'

        headers = {'Accept': 'application/json', 'uid': config_data['uid'], 'password': config_data['password']}

        response = requests.get("{core_url}devices/{uid}/pause".format(core_url=CORE_URL, uid=config_data['uid']), params={'pause_until': pause_until}, headers=headers)

        response.raise_for_status()

        modify_config_file({'pause_until': str(pause_until)})

        print('Xitogent paused succeefully.')

    except (ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError, TooManyRedirects) as e:
        sys.exit('Cannot pause Xitogent.')


def fetch_pause_until():

    time_string = ''

    MINUTE_IN_SECONDS = 60
    HOUR_IN_SECONDS = 60 * MINUTE_IN_SECONDS
    DAY_IN_SECONDS = 24 * HOUR_IN_SECONDS
    WEEK_IN_SECONDS = 7 * DAY_IN_SECONDS
    YEAR_IN_SECONDS = 365 * DAY_IN_SECONDS

    for index, value in enumerate(sys.argv):
        next_index = index+1
        if re.search("pause", value) and next_index < len(sys.argv):
            time_string = sys.argv[next_index]

    if time_string == '':
        return int(time.time() + (16 * YEAR_IN_SECONDS))

    RELATIVE_TIME_REGEX = re.compile('^((\d+)[wW])?((\d+)[dD])?((\d+)[hH])?((\d+)[mM])?$')

    relative_time_found = RELATIVE_TIME_REGEX.match(time_string)

    if not relative_time_found:
        sys.exit('Time must be in the format 2w4d6h45m')

    seconds = 0

    time_string = time_string.strip()

    durations = list(map(int, re.split('[wWdDhHmM]', time_string)[:-1]))

    types = list(re.split('\d+', time_string))

    if types[0] == '':
        del types[0]

    for index, duration in enumerate(durations):

        type = types[index]

        type = type.lower()

        if type == 'w':
            seconds += duration * WEEK_IN_SECONDS
        elif type == 'd':
            seconds += duration * DAY_IN_SECONDS
        elif type == 'h':
            seconds += duration * HOUR_IN_SECONDS
        else:
            seconds += duration * MINUTE_IN_SECONDS

    return int(time.time() + seconds)


def is_unpause_mode():
    if len(sys.argv) > 1 and sys.argv[1] == 'unpause':
        return True
    return False


def unpause():
    try:

        config_data = read_config()

        global CORE_URL

        if is_dev():
            CORE_URL = 'http://localhost/'

        headers = {'Accept': 'application/json', 'uid': config_data['uid'], 'password': config_data['password']}

        response = requests.get("{core_url}devices/{uid}/unpause".format(core_url=CORE_URL, uid=config_data['uid']),
                                headers=headers)

        response.raise_for_status()

        modify_config_file({'pause_until': ''}, delete_mode=True)

        print('Xitogent unpaused successfully.')

    except (ConnectTimeout, HTTPError, ReadTimeout, Timeout, ConnectionError, TooManyRedirects) as e:
        sys.exit('Cannot unpause Xitogent.')


def is_stop_mode():
    if len(sys.argv) > 1 and sys.argv[1] == 'stop':
        return True
    return False


def stop():

    if not is_running():
        if is_stop_mode():
            print('Already stopped.')
        return None

    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE) as file:

                pid = file.read().strip()

                os.kill(int(pid), 15)

                run_command('rm -rf {}'.format(PID_FILE))

                if is_stop_mode():
                    print('Xitogent stopped successfully.')

        except Exception:
            if is_stop_mode():
                print('Stopping Xitogent failed.')
    else:

        if is_centos6():
            cmd = 'service xitogent stop'
        else:
            cmd = 'systemctl stop xitogent'

        if not run_command(cmd):
            if is_stop_mode():
                print('Stopping Xitogent service failed.')
            return None

        if is_stop_mode():
            print('Xitogent stopped successfully.')


def is_restart_mode():
    if len(sys.argv) > 1 and sys.argv[1] == 'restart':
        return True
    return False


def restart():
    stop()
    start()


def is_status_mode():
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        return True
    return False


def show_xitogent_status():

    uptime = get_item('uptime')

    if is_running() and uptime:
        uptime = "{:0>8}".format(str(datetime.timedelta(seconds=int(time.time()) - int(uptime))))
    else:
        uptime = 0

    if is_device_paused():
        status = 'paused'
    elif is_running():
        status = 'running'
    else:
        status = 'stopped'

    sent_sequences = get_item('sent_sequences')

    if not is_running() or not sent_sequences:
        sent_sequences = 0

    failed_sequences = get_item('failed_sequences')

    if not is_running() or not failed_sequences:
        failed_sequences = 0

    print('%-30s' '%s' % ('Status', status))
    print('%-30s' '%s' % ('Uptime', uptime))
    print('%-30s' '%s' % ('Sent sequences', sent_sequences))
    print('%-30s' '%s' % ('Failed sequences', failed_sequences))


def convert_human_read_to_byte(size):
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    match = re.match(r"(\d+(?:\.\d+)?)+([a-z]+)", size, re.I)
    if not match:
        return 0
    size = match.groups()
    num, unit = float(size[0]), size[1]
    unit = unit.upper()
    idx = size_name.index(unit)
    factor = 1024 ** idx
    return int(num * factor)


def has_verbose_flag():
    if '--verbose' in sys.argv:
        return True
    return False


def has_quiet_flag():
    if '--quiet' in sys.argv:
        return True
    return False

last_bw = {'time': '', 'value': ''}
last_disk_io = {'time': '', 'value': ''}


class Linux:

    @classmethod
    def fetch_system_info(cls):
        return {
            'hostname': cls.fetch_hostname(),
            'os': cls.get_os(),
            'uptime': cls.fetch_uptime(),
            'timezone': cls.get_timezone(),
            'cpu': {'model_name': cls.get_cpu_model_name(), 'total': cls.get_cpu_count()},
            'type': 'linux',
        }

    @staticmethod
    def fetch_hostname():

        p = subprocess.Popen('hostname', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return ''

        output = stdout.split(b"\n")

        return output[0].decode("utf-8")

    @staticmethod
    def get_os():
        try:
            if os.path.isfile('/etc/os-release'):
                with open("/etc/os-release", "r") as etclsbrel:
                    for line in etclsbrel:
                        m = re.compile(r"(?:PRETTY_NAME=\s*)\s*(.*)", re.I).search(line)
                        if m:
                            return m.group(1).replace('"', '')

            if (os.path.isfile('/etc/redhat-release')):
                with open("/etc/redhat-release", "r") as etclsbrel:
                    for line in etclsbrel:
                        return line.replace("\n", "")

        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return ''

    @staticmethod
    def get_timezone():

        p = subprocess.Popen('date "+%Z%z"', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return ''

        output = stdout.split(b"\n")

        return output[0].decode("utf-8")

    @staticmethod
    def get_cpu_model_name():
        try:
            with open('/proc/cpuinfo') as f:
      debug2: channel 0: window 998342 sent adjust 50234
          for line in f:
                    if line.strip() and line.rstrip('\n').startswith('model name'):
                        return line.rstrip('\n').split(':')[1]
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return ''

    @staticmethod
    def get_cpu_count():

        p = subprocess.Popen('grep --count ^processor /proc/cpuinfo', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return 0

        output = stdout.split(b"\n")

        return output[0].decode("utf-8")

    @classmethod
    def fetch_uptime(cls):
        try:
            # python 2.6
            if sys.version_info[0] == 2 and sys.version_info[1] == 6:
                f = open('/proc/stat', 'r')
                for line in f:
                    if line.startswith(b'btime'):
                        boot_time = float(line.strip().split()[1])
                        return cls.convert_uptime_to_human_readable(boot_time)

            return cls.convert_uptime_to_human_readable(psutil.boot_time())

        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            return ''

    @staticmethod
    def convert_uptime_to_human_readable(boot_time):

        seconds = time.time() - boot_time

        days = int(math.floor(seconds / 86400))

        seconds = seconds - (days * 86400)

        hours = int(math.floor(seconds / 3600))

        seconds = seconds - (hours * 3600)

        minutes = int(math.floor(seconds / 60))

        seconds = int(seconds - (minutes * 60))

        result = []

        if days > 0:
            result.append(str(days) + " days")

        if hours > 0:
            result.append(str(hours) + " hours")

        if minutes > 0:
            result.append(str(minutes) + " minutes")

        if seconds > 0:
            result.append(str(seconds) + " seconds")

        return ", ".join(result)

    @staticmethod
    def fetch_ips():

        p = subprocess.Popen('hostname -I', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return []

        ips = stdout.split()

        ips = [ip.decode("utf-8") for ip in ips]

        return ips

    @staticmethod
    def fetch_cpu_usage():

        try:
            result = {}

            sum = 0

            for i, usage_percent in enumerate(psutil.cpu_percent(interval=1, percpu=True)):
                usage_percent = "{0:.2f}".format(usage_percent)
                usage_percent = float(usage_percent)
                result['cpu' + str(i + 1)] = usage_percent
                sum += float(usage_percent)

            if len(result) > 0:
                result['average'] = sum / len(result)
                result['average'] = "{0:.2f}".format(result['average'])
                result['average'] = float(result['average'])
            else:
                result['average'] = 0

            return result
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @staticmethod
    def fetch_cpu_load_average():
        try:
            load_1_minute, load_5_minutes, load_15_minutes = map("{0:.2f}".format, os.getloadavg())
            return {'1min': float(load_1_minute), '5min': float(load_5_minutes), '15min': float(load_15_minutes)}
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @staticmethod
    def fetch_disk_usage():
        try:
            disks = {}

            for x in psutil.disk_partitions():
                disks[x.mountpoint] = {
                    "total": psutil.disk_usage(x.mountpoint).total,
                    "used": psutil.disk_usage(x.mountpoint).used,
                }

            return disks
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @classmethod
    def fetch_disk_io(cls):
        try:
            global last_disk_io

            if last_disk_io['value'] == '':
                disk_io_t1 = psutil.disk_io_counters(perdisk=True)
                time.sleep(1)
                disk_io_t2 = psutil.disk_io_counters(perdisk=True)
                last_disk_io = {'value': disk_io_t2, 'time': time.time()}
                return cls.calculate_disk_io_change(disk_io_t1, disk_io_t2)

            current_disk_io = psutil.disk_io_counters(perdisk=True)

            changed_disk_io = cls.calculate_disk_io_change(last_disk_io['value'], current_disk_io, last_disk_io['time'])

            last_disk_io = {'value': current_disk_io, 'time': time.time()}

            return changed_disk_io

        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @classmethod
    def calculate_disk_io_change(cls, disk_io_t1, disk_io_t2, last_value_time=0):

        read_bytes_t1 = 0
        write_bytes_t1 = 0
        partitions_t1 = {}

        for name in disk_io_t1:
            if cls.is_local_partition(name):
                continue
            read_bytes_t1 += disk_io_t1[name].read_bytes
            write_bytes_t1 += disk_io_t1[name].write_bytes
            partitions_t1[name] = {
                'read_bytes': disk_io_t1[name].read_bytes,
                'write_bytes': disk_io_t1[name].write_bytes
            }

        read_bytes_t2 = 0
        write_bytes_t2 = 0
        disks = {}

        for name in disk_io_t2:

            if cls.is_local_partition(name):
                continue

            read_bytes_t2 += disk_io_t2[name].read_bytes
            write_bytes_t2 += disk_io_t2[name].write_bytes

            disk_read_bytes_t1 = partitions_t1[name]['read_bytes'] if name in partitions_t1 else 0

            changed_disk_read_bytes = disk_io_t2[name].read_bytes - disk_read_bytes_t1

            if changed_disk_read_bytes < 0:
                changed_disk_read_bytes = abs(changed_disk_read_bytes)

            if last_value_time != 0:
                changed_disk_read_bytes = changed_disk_read_bytes / (time.time() - last_value_time)

            disk_write_bytes_t1 = partitions_t1[name]['write_bytes'] if name in partitions_t1 else 0

            changed_disk_write_bytes = disk_io_t2[name].write_bytes - disk_write_bytes_t1

            if changed_disk_write_bytes < 0:
                changed_disk_write_bytes = abs(changed_disk_write_bytes)

            if last_value_time != 0:
                changed_disk_write_bytes = changed_disk_write_bytes / (time.time() - last_value_time)

            disks[name] = {
                'read': int(changed_disk_read_bytes),
                'write': int(changed_disk_write_bytes)
            }

        changed_read_bytes = read_bytes_t2 - read_bytes_t1

        if changed_read_bytes < 0:
            changed_read_bytes = abs(changed_read_bytes)

        if last_value_time != 0:
            changed_read_bytes = changed_read_bytes / (time.time() - last_value_time)

        changed_write_bytes = write_bytes_t2 - write_bytes_t1

        if changed_write_bytes < 0:
            changed_write_bytes = abs(changed_write_bytes)

        if last_value_time != 0:
            changed_write_bytes = changed_write_bytes / (time.time() - last_value_time)

        return {
            'read': int(changed_read_bytes),
            'write': int(changed_write_bytes),
            'partitions': disks
        }

    @staticmethod
    def is_local_partition(name):

        name = name.strip()

        name = name.lower()

        if name.startswith('loop') or name.startswith('ram'):
            return True

        return False

    @staticmethod
    def fetch_memory_usage():
        try:
            memory_stats = psutil.virtual_memory()
            return {
                'free': memory_stats.free,
                'used': memory_stats.used,
                'total': memory_stats.total,
                'cache': memory_stats.cached,
                'buffers': memory_stats.buffers,
            }
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @classmethod
    def fetch_network(cls):
        try:
            global last_bw

            if last_bw['value'] == '':
                interfaces_t1 = cls.fetch_current_bw()
                time.sleep(1)
                interfaces_t2 = cls.fetch_current_bw()
                last_bw = {'value': interfaces_t2, 'time': time.time()}
                return cls.calculate_bw_change(interfaces_t1, interfaces_t2)

            current_bw = cls.fetch_current_bw()

            changed_bw = cls.calculate_bw_change(last_bw['value'], current_bw, last_bw['time'])

            last_bw = {'value': current_bw, 'time': time.time()}

            return changed_bw

        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @classmethod
    def fetch_current_bw(cls):

        # python 2.6
        if sys.version_info[0] == 2 and sys.version_info[1] == 6:
            return cls.filter_interfaces(cls.bw_2_6())

        return cls.filter_interfaces(psutil.net_io_counters(pernic=True))

    @staticmethod
    def filter_interfaces(interfaces):
        for name in interfaces.copy():
            if name.startswith('veth') or name.startswith('br') or name == 'lo':
                del interfaces[name]

        return interfaces

    @staticmethod
    def calculate_bw_change(interfaces_t1, interfaces_t2, last_value_time=0):

        result = {}

        for name in interfaces_t2:

            if name == 'lo':
                continue

            bytes_sent_t2 = interfaces_t2[name].bytes_sent if name in interfaces_t2 else 0

            bytes_sent_t1 = interfaces_t1[name].bytes_sent if name in interfaces_t1 else 0

            sent = (bytes_sent_t2 - bytes_sent_t1) * 8

            if sent < 0:
                sent = abs(sent)

            if last_value_time != 0:
                sent = sent / (time.time() - last_value_time)

            bytes_received_t2 = interfaces_t2[name].bytes_recv if name in interfaces_t2 else 0

            bytes_received_t1 = interfaces_t1[name].bytes_recv if name in interfaces_t1 else 0

            received = (bytes_received_t2 - bytes_received_t1) * 8

            if received < 0:
                received = abs(received)

            if last_value_time != 0:
                received = received / (time.time() - last_value_time)

            result[name] = {'sent': int(sent), 'received': int(received)}

        return result

    @staticmethod
    def bw_2_6():
        try:
            with open("/proc/net/dev", 'r') as f:
                lines = f.readlines()

            retdict = {}

            for line in lines[2:]:

                colon = line.rfind(':')

                assert colon > 0, repr(line)

                name = line[:colon].strip()

                fields = line[colon + 1:].strip().split()

                # in
                (bytes_recv,
                 packets_recv,
                 errin,
                 dropin,
                 fifoin,  # unused
                 framein,  # unused
                 compressedin,  # unused
                 multicastin,  # unused
                 # out
                 bytes_sent,
                 packets_sent,
                 errout,
                 dropout,
                 fifoout,  # unused
                 collisionsout,  # unused
                 carrierout,  # unused
                 compressedout) = map(int, fields)

                retdict[name] = (bytes_sent, bytes_recv, packets_sent, packets_recv,
                                 errin, errout, dropin, dropout)

            rawdict = {}

            Interface = collections.namedtuple('snetio', ['bytes_sent', 'bytes_recv',
                                                          'packets_sent', 'packets_recv',
                                                          'errin', 'errout',
                                                          'dropin', 'dropout'])

            for nic, fields in retdict.items():
                rawdict[nic] = Interface(*fields)

            return rawdict
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return {}

    @staticmethod
    def find_detected_softwares():

        try:
            softwares = [
                "nginx",
                "apache2",
                "sshd",
                "tomcat",
                "mariadb",
                "php-fpm",
                "mysqld",
                "httpd",
                "vsftpd",
                "mysql",
                "named",
                "csf",
                "memcached",
                "posgresql",
                "mongod",
                "postfix",
                "redis",
                "keydb",
                "varnish",
                "lighttpd",
                "lsws",
                "haproxy",
                "couchdb",
                "arangodb3",
                "ufw",
                "iptables",
                "firewalld",
                "dnsmasq"
            ]

            p1 = subprocess.Popen("ps aux", stdout=subprocess.PIPE, shell=True)
            p2 = subprocess.Popen(
                "egrep '" + "(" + "|".join(softwares) + ")" + "'",
                stdin=p1.stdout,
                stdout=subprocess.PIPE,
                shell=True
            )

            temp = p2.communicate()[0]

            lines = temp.split(b"\n")

            detected_softwares = []

            for software in softwares:
                for line in lines:
                    line = line.decode("utf-8")
                    if re.search(software, line) and not re.search( "\(" + "\|".join(softwares) + "\)", line):
                        detected_softwares.append(software)
                        break

            return detected_softwares
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return []

    @staticmethod
    def find_top_five_memory_consumer_processes():

        try:
            p1 = subprocess.Popen(['ps', '-eo', 'pmem,pid,cmd', '--no-headers'], stdout=subprocess.PIPE)

            p2 = subprocess.Popen(['sort', '-k', '1', '-rn'], stdin=p1.stdout, stdout=subprocess.PIPE)

            p3 = subprocess.Popen(['head', '-5'], stdin=p2.stdout, stdout=subprocess.PIPE)

            temp = p3.communicate()[0]

            output = temp.split(b"\n")

            processes = []

            for row in output:

                if not row:
                    continue

                row = row.decode("utf-8")

                temp = row.split()

                if len(temp) > 3:
                    cmd = " ".join(temp[2:(len(temp))])
                else:  # command has no option or argument
                    cmd = temp[2]

                processes.append(
                    {
                        'memory_usage': temp[0],
                        'pid': temp[1],
                        'cmd': cmd,
                    }
                )

            return processes
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return []

    @staticmethod
    def find_top_five_cpu_consumer_processes():

        try:
            p1 = subprocess.Popen(['ps', '-eo', 'pcpu,pid,cmd', '--no-headers'], stdout=subprocess.PIPE)

            p2 = subprocess.Popen(['sort', '-k', '1', '-rn'], stdin=p1.stdout, stdout=subprocess.PIPE)

            p3 = subprocess.Popen(['head', '-5'], stdin=p2.stdout, stdout=subprocess.PIPE)

            temp = p3.communicate()[0]

            output = temp.split(b"\n")

            processes = []

            for row in output:

                if not row:
                    continue

                row = row.decode("utf-8")

                temp = row.split()

                if len(temp) > 3:
                    cmd = " ".join(temp[2:(len(temp))])
                else:  # command has no option or argument
                    cmd = temp[2]

                processes.append(
                    {
                        'cpu_usage': temp[0],
                        'pid': temp[1],
                        'cmd': cmd,
                    }
                )

            return processes
        except Exception as e:
            if is_initial_test():
                return {'status': 'failed', 'message': e}
            pass

        return []

    @staticmethod
    def fetch_docker_disk_usage():

        p = subprocess.Popen('docker system df --format="{{json .}}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return []

        lines = stdout.split(b"\n")

        disk_usages = []

        try:
            for line in lines:

                if not line:
                    continue

                temp = json.loads(line)

                temp = dict((k.lower(), v) for k, v in temp.items())

                size = temp['size'] if 'size' in temp else ''

                size = convert_human_read_to_byte(size)

                type = temp['type'] if 'type' in temp else ''

                type = type.lower()

                type = type.replace(' ', '_')

                if size > 0:
                    disk_usages.append(
                        {
                            'type': type,
                            'active_count': int(temp['active']) if 'active' in temp else '',
                            'total_count': int(temp['totalcount']) if 'totalcount' in temp else '',
                            'size': size,
                        }
                    )
        except Exception:
            pass

        return disk_usages

    @classmethod
    def fetch_docker_images_containers_and_volumes(cls):

        p = subprocess.Popen('docker system df -v --format="{{json .}}"', stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return []

        try:
            lines = stdout.split(b"\n")

            for line in lines:

                if not line:
                    continue

                temp = json.loads(line)

                temp = dict((k.lower(), v) for k, v in temp.items())

                images = []

                if "images" in temp:
                    images = cls.extract_docker_images(temp["images"])

                containers = []

                if "containers" in temp:
                    containers = cls.extract_docker_containers(temp["containers"])

                volumes = []

                if "volumes" in temp:
                    volumes = cls.extract_docker_volumes(temp["volumes"])

                return {"images": images, "containers": containers, "volumes": volumes}

        except Exception:
            return []

    @staticmethod
    def extract_docker_images(data):

        images = []

        try:
            for image in data:
                image = dict((k.lower(), v) for k, v in image.items())

                size = image['size'] if 'size' in image else ''

                size = convert_human_read_to_byte(size)

                shared_size = image['sharedsize'] if 'sharedsize' in image else ''

                shared_size = convert_human_read_to_byte(shared_size)

                unique_size = image['uniquesize'] if 'uniquesize' in image else ''

                unique_size = convert_human_read_to_byte(unique_size)

                id = image['id'] if 'id' in image else ''

                id = id.replace('sha256:', '')

                images.append({
                    'repository': image['repository'] if 'repository' in image else '',
                    'tag': image['tag'] if 'tag' in image else '',
                    'id': id[0: 12],
                    'created_since': image['createdsince'] if 'createdsince' in image else '',
                    'size': size,
                    'shared_size': shared_size,
                    'unique_size': unique_size,
                    'containers': int(image['containers']) if 'containers' in image else '',
                })

        except Exception:
            pass

        return images

    @classmethod
    def extract_docker_containers(cls, data):

        containers = []

        try:
            statistics = cls.fetch_docker_containers_statistics()

            for container in data:

                container = dict((k.lower(), v) for k, v in container.items())

                size = container['size'] if 'size' in container else ''

                size = convert_human_read_to_byte(size)

                id = container['id'] if 'id' in container else ''

                id = id[0:12]

                temp = {
                    'id': id,
                    'image': container['image'] if 'image' in container else '',
                    'command': container['command'] if 'command' in container else '',
                    'running_for': container['runningfor'] if 'runningfor' in container else '',
                    'status': container['status'] if 'status' in container else '',
                    'ports': container['ports'] if 'ports' in container else '',
                    'name': container['names'] if 'names' in container else '',
                    'size': size,
                }

                if id in statistics:

                    temp.update(statistics[id])

                    if 'cpu_percent' in temp:
                        temp['cpu_percent'] = float(temp['cpu_percent'].replace('%', ''))

                    if 'memory_percent' in temp:
                        temp['memory_percent'] = float(temp['memory_percent'].replace('%', ''))

                    if 'memory_usage' in temp:
                        del temp['memory_usage']
                else:
                    temp['cpu_percent'] = 0
                    temp['memory_percent'] = 0

                containers.append(temp)

        except Exception:
            pass

        return containers

    @staticmethod
    def fetch_docker_containers_statistics():

        p = subprocess.Popen('docker stats --no-stream --format="{{json .}}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return {}

        statistics = {}

        try:
            lines = stdout.split(b"\n")

            for line in lines:

                if not line:
                    continue

                temp = json.loads(line)

                temp = dict((k.lower(), v) for k, v in temp.items())

                id = temp['id'] if 'id' in temp else ''

                statistics[id] = {'cpu_percent': temp['cpuperc'], 'memory_percent': temp['memperc'],
                                  'memory_usage': temp['memusage']}
        except Exception:
            pass

        return statistics

    @staticmethod
    def extract_docker_volumes(data):

        volumes = []

        try:
            for volume in data:
                volume = dict((k.lower(), v) for k, v in volume.items())

                size = volume['size'] if 'size' in volume else ''

                size = convert_human_read_to_byte(size)

                volumes.append({
                    'driver': volume['driver'] if 'driver' in volume else '',
                    'name': volume['name'] if 'name' in volume else '',
                    'links': int(volume['links']) if 'links' in volume else '',
                    'size': size,
                })
        except Exception:
            pass

        return volumes

    @staticmethod
    def fetch_docker_networks():

        p = subprocess.Popen('docker network ls --format="{{json .}}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            if is_initial_test():
                return {'status': 'failed', 'message': stderr}
            return []

        networks = []

        try:
            lines = stdout.split(b"\n")

            for line in lines:

                if not line:
                    continue

                network = json.loads(line)

                network = dict((k.lower(), v) for k, v in network.items())

                networks.append(
                    {
                        'id': network['id'] if 'id' in network else '',
                        'name': network['name'] if 'name' in network else '',
                        'driver': network['driver'] if 'driver' in network else '',
                        'scope': network['scope'] if 'scope' in network else '',
                    }
                )
        except Exception:
            pass

        return networks

    @classmethod
    def fetch_listening_ports(cls):

        p = subprocess.Popen('netstat -lpe', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            return []

        ports = []

        try:
            lines = stdout.split(b"\n")

            unix_header_text = ''

            for line in lines:

                line = line.decode('utf-8')

                is_tcp_port = line.startswith("tcp")
                is_udp_port = line.startswith("udp")
                is_unix_port = line.startswith("unix")

                if not line or (not is_tcp_port and not is_udp_port and not is_unix_port):
                    if 'RefCnt' in line:
                        unix_header_text = line
                    continue

                if is_tcp_port or is_udp_port:
                    port = cls.parse_tcp_or_udp_port(line)
                else:
                    port = cls.parse_unix_port(unix_header_text, line)
                    if port['path'] in (p['path'] for p in ports if 'path' in p):
                        continue

                ports.append(port)

        except Exception:
            pass

        return ports

    @staticmethod
    def parse_tcp_or_udp_port(line):

        keys = [
            'proto',
            'recv_q',
            'send_q',
            'local_address',
            'foreign_address',
            'state',
            'user',
            'inode',
            'pid_program_name'
        ]

        entry = line.split(maxsplit=len(keys) - 1)

        # check for long program name
        matching_index = [index for index, s in enumerate(entry) if '/' in s]
        if len(matching_index) > 0:
            matching_index = matching_index[0]
            entry.insert(matching_index, " ".join(entry[matching_index:]))
            del entry[matching_index+1:]

        #state is empty
        if len(entry) == len(keys) - 1:
            entry.insert(5, None)

        port = dict(zip(keys, entry))

        temp = {}

        for name in port:

            try:
                port[name] = port[name].strip()
                if name == 'recv_q' or name == 'send_q' or name == 'inode':
                    port[name] = int(port[name])
            except Exception:
                pass

            if name == 'proto':
                if '6' in port['proto']:
                    temp['network_protocol'] = 'ipv6'
                else:
                    temp['network_protocol'] = 'ipv4'

            elif name == 'pid_program_name':

                if port[name] == '-':
                    port[name] = None
                    temp['pid'] = 0
                    temp['program_name'] = ''

                if port[name]:
                    if '/' in port[name]:
                        pid = port[name].split('/', maxsplit=1)[0]
                        name = port[name].split('/', maxsplit=1)[1]
                        temp['pid'] = int(pid)
                        temp['program_name'] = name
                    else:
                        temp['pid'] = 0
                        temp['program_name'] = ''

            elif name == 'local_address':
                if port[name]:
                    ladd = port[name].rsplit(':', maxsplit=1)[0]
                    lport = port[name].rsplit(':', maxsplit=1)[1]
                    temp['local_address'] = ladd
                    temp['local_port'] = lport

            elif name == 'foreign_address':
                if port[name]:
                    fadd = port[name].rsplit(':', maxsplit=1)[0]
                    fport = port[name].rsplit(':', maxsplit=1)[1]
                    temp['foreign_address'] = fadd
                    temp['foreign_port'] = fport

        port.update(temp)

        if 'state' in port:
            del port['state']

        if 'pid_program_name' in port:
            del port['pid_program_name']

        return port

    @staticmethod
    def parse_unix_port(header_text, line):

        headers = [
            'proto',
            'refcnt',
            'flags',
            'type',
            'state',
            'i_node',
            'program_name',
            'path'
        ]

        header_text = header_text.lower()
        header_text = header_text.replace('pid/program name', 'program_name')
        header_text = header_text.replace('i-node', 'i_node')
        header_text = header_text.replace('-', '_')

        # get the column # of first letter of "state"
        state_col = header_text.find('state')

        # get the program name column area
        pn_start = header_text.find('program_name')
        pn_end = header_text.find('path') - 1

        # remove [ and ] from each line
        entry = line.replace('[ ]', '---')
        entry = entry.replace('[', ' ').replace(']', ' ')

        # find program_name column area and substitute spaces with \u2063 there
        old_pn = entry[pn_start:pn_end]
        new_pn = old_pn.replace(' ', '\u2063')
        entry = entry.replace(old_pn, new_pn)

        entry_list = entry.split(maxsplit=len(headers) - 1)
        # check column # to see if state column is populated
        if entry[state_col] in string.whitespace:
            entry_list.insert(4, None)

        port = dict(zip(headers, entry_list))

        temp = {}

        for name in port:

            try:
                port[name] = port[name].strip()
                if name == 'refcnt' or name == 'i_node':
                    port[name] = int(port[name])
            except Exception:
                pass

            if name == 'flags':
                if port[name] == '---':
                    port[name] = None

            elif name == 'program_name':

                if port[name] == '-':
                    port[name] = None
                    temp['pid'] = 0
                    temp['program_name'] = ''

                if port[name]:

                    # fix program_name field to turn \u2063 back to spaces
                    old_d_pn = port[name]
                    new_d_pn = old_d_pn.replace('\u2063', ' ')
                    port[name] = new_d_pn

                    port[name] = port[name].strip()

                    if '/' in port[name]:
                        pid = port[name].split('/', maxsplit=1)[0]
                        name = port[name].split('/', maxsplit=1)[1]
                        temp['pid'] = int(pid)
                        temp['program_name'] = name
                    else:
                        temp['pid'] = 0
                        temp['program_name'] = ''

        port.update(temp)

        if 'state' in port:
            del port['state']

        return port

    @staticmethod
    def fetch_kernel_routes():

        p = subprocess.Popen('netstat -r', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            return []

        routes = []

        try:
            data = jc.parsers.netstat.parse(stdout.decode("utf-8"))

            for route in data:

                iface = route['iface'] if 'iface' in route else ''

                if iface.startswith('veth') or iface.startswith('br') or iface == 'lo':
                    continue

                routes.append({
                    'destination': route['destination'] if 'destination' in route else '',
                    'gateway': route['gateway'] if 'gateway' in route else '',
                    'genmask': route['genmask'] if 'genmask' in route else '',
                    'flags': route['route_flags'] if 'route_flags' in route else '',
                    'mss': route['mss'] if 'mss' in route else '',
                    'window': route['window'] if 'window' in route else '',
                    'irtt': route['irtt'] if 'irtt' in route else '',
                    'iface': iface,
                })
        except Exception:
            pass

        return routes

    @staticmethod
    def fetch_network_interfaces():

        p = subprocess.Popen('netstat -i', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        stdout, stderr = p.communicate()

        # error
        if p.returncode != 0:
            return []

        interfaces = []

        try:
            data = jc.parsers.netstat.parse(stdout.decode("utf-8"))

            for interface in data:

                iface = interface['iface'] if 'iface' in interface else ''

                if iface.startswith('veth') or iface.startswith('br') or iface == 'lo':
                    continue

                interfaces.append({
                    'iface': iface,
                    'mtu': interface['mtu'] if 'mtu' in interface else '',
                    'rx_ok': interface['rx_ok'] if 'rx_ok' in interface else '',
                    'rx_err': interface['rx_err'] if 'rx_err' in interface else '',
                    'rx_drp': interface['rx_drp'] if 'rx_drp' in interface else '',
                    'rx_ovr': interface['rx_ovr'] if 'rx_ovr' in interface else '',
                    'tx_ok': interface['tx_ok'] if 'tx_ok' in interface else '',
                    'tx_err': interface['tx_err'] if 'tx_err' in interface else '',
                    'tx_drp': interface['tx_drp'] if 'tx_drp' in interface else '',
                    'tx_ovr': interface['tx_ovr'] if 'tx_ovr' in interface else '',
                    'flg': interface['flg'] if 'flg' in interface else '',
                })
        except Exception:
            pass

        return interfaces

    @classmethod
    def fetch_data(cls):

        docker_data = cls.fetch_docker_images_containers_and_volumes()

        return {
            'description': cls.fetch_system_info(),
            'statistics': {
                'cpu_load_average': cls.fetch_cpu_load_average(),
                'cpu_usage': cls.fetch_cpu_usage(),
                'memory_usage': cls.fetch_memory_usage(),
                'disk_usage': cls.fetch_disk_usage(),
                'disk_io': cls.fetch_disk_io(),
                'network': cls.fetch_network(),
            },
            'ips': cls.fetch_ips(),
            'softwares': cls.find_detected_softwares(),
            'processes': {
                'cpu_consumer': cls.find_top_five_cpu_consumer_processes(),
                'memory_consumer': cls.find_top_five_memory_consumer_processes(),
            },
            'docker': {
                'disk_usage': Linux.fetch_docker_disk_usage(),
                'images': docker_data['images'] if 'images' in docker_data else [],
                'containers': docker_data['containers'] if 'containers' in docker_data else [],
                'volumes': docker_data['volumes'] if 'volumes' in docker_data else [],
                'networks': Linux.fetch_docker_networks(),
            },
            'netstat': {
                'ports': Linux.fetch_listening_ports(),
                'kernel_routes': Linux.fetch_kernel_routes(),
                'network_interfaces': Linux.fetch_network_interfaces(),
            }
        }

if is_show_commands_mode():
    show_commands()

if is_version_mode():
    show_xitogent_version()

if is_initial_test():
    get_device_status()

if is_add_device():
    add_device()

if is_start_mode():
    start()

if is_force_update():
    force_update()

if is_new_xitogent_test():
    test_new_xitogent()

if is_uninstall():
    uninstall()

if is_pause_mode():
    pause()

if is_unpause_mode():
    unpause()

if is_status_mode():
    show_xitogent_status()

if is_stop_mode():
    stop()

if is_restart_mode():
    restart()
