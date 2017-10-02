import configparser
import worker

CONFIG_FILE = "config.ini"

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
png_large = pngparam['large']
png_fast = pngparam['fast']
png_killing = pngparam['killing']

work = worker.Worker(host, jobName, max_thread, [png_norm, png_large, png_fast, png_killing], 30, 60)
work.loop.run_until_complete(work.start_config())

