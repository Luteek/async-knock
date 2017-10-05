import configparser
import worker

CONFIG_FILE = "config.ini"

"""Удалит при запуске прокраммы старые логи"""
with open('log.log', 'w'):
    pass

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

prom = config['PROMETHEUS']
host = prom['host']
jobName = prom['jobName']

thread = config['THREAD']
max_thread = thread['max_thread']
delay_ping = thread['delay_ping']
delay_parse = thread['delay_parse']

pngparam = config['PING_PARAM']
png_norm = pngparam['normal']
png_fast = pngparam['fast']

work = worker.Worker(host, jobName, max_thread, [png_norm,  png_fast], delay_ping, delay_parse)
work.loop.run_until_complete(work.start_config())

