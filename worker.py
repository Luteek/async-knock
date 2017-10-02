import asyncio
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from subprocess import Popen, PIPE
import re
import logging

#logging.basicConfig(filename='log.log', level=logging.DEBUG, format='%(asctime)s -%(levelname)s -%(message)s')


class Worker:
    registry = CollectorRegistry()
    loop = asyncio.get_event_loop()
    THREAD_COUNT = 0
    host_config = [' ']
    task_add = []
    task_remove = [' ']

    metric_delay = Gauge('ping_pkt_latency_avg', 'h', ['ip', 'group'], registry=registry)
    metric_loss = Gauge('ping_pkt_lost', 'l', ['ip', 'group'], registry=registry)
    metric_delay_min = Gauge('ping_pkt_latency_min', 'l', ['ip', 'group'], registry=registry)
    metric_delay_max = Gauge('ping_pkt_latency_max', 'l', ['ip', 'group'], registry=registry)

    def __init__(self, gateway_host, job, max_thread, png_param, delay_ping, delay_parse):
        self.gateway_host = gateway_host
        self.job = job
        self.MAX_THREAD_COUNT = int(max_thread)
        self.png_normal = png_param[0]
        self.png_large = png_param[1]
        self.png_fast = png_param[2]
        self.png_killing = png_param[3]
        self.delay_ping = int(delay_ping)
        self.delay_parse = int(delay_parse)
        print('Delay ping %s' %self.delay_ping)

    def load_config(self):
        self.task_remove = [' ']
        self.task_add = []
        with open('tsk.txt', 'r') as file:
            data = [row.strip() for row in file]

        for old_task in self.host_config:
            must_be_remove = True
            for update_task in data:
                if old_task == update_task.split(';'):
                    must_be_remove = False
            if must_be_remove:
                self.task_remove.append(old_task)
                self.host_config.remove(old_task)

        for new_task in data:
            must_be_add = True
            for old in self.host_config:
                if old == new_task.split(';'):
                    must_be_add = False
            if must_be_add:
                self.task_add.append(new_task.split(';'))
                self.host_config.append(new_task.split(';'))
        print('LOAD_CONFIG:%s' % self.host_config)
        #logging.info(u'LOAD_CONFIG:%s' % self.host_config)

    @asyncio.coroutine
    def start_config(self):
        while True:
            self.load_config()
            for config in self.task_add:
                self.loop.create_task(self.ping_host(config[0], config[1], config[2]))
            yield from asyncio.sleep(self.delay_parse)

    # @asyncio.coroutine
    # def request_metrics(self):
    #     while True:
    #         try:
    #             push_to_gateway(self.gateway_host, job=self.job, registry=self.registry)
    #             logging.info(u'Push DONE')
    #         except:
    #             logging.error(u'Error connect to pushgate')
    #         yield from asyncio.sleep(60)

    @asyncio.coroutine
    def ping_host(self, ip, parameters, group):
        if parameters == 'large':
            parameters = self.png_large
        elif parameters == 'fast':
            parameters = self.png_fast
        elif parameters == 'killing':
            parameters = self.png_killing
        else:
            parameters = self.png_normal

        while True:
            data = None
            flag = False
            for line in self.task_remove:
                if ip == line[0]:
                    flag = True
            if not flag:
                # data = ping.ping_d(ip, parameters)
                """TEST"""
                if self.THREAD_COUNT < self.MAX_THREAD_COUNT:
                    self.THREAD_COUNT = self.THREAD_COUNT + 1

                    print('start ping ip %s' % ip)
                    #logging.info(u'start ping ip %s' % ip)
                    line = ('ping' + ' ' + ip + ' ' + parameters)
                    cmd = Popen(line.split(' '), stdout=PIPE)
                    yield from asyncio.sleep(0)

                    output = cmd.communicate()[0]
                    self.THREAD_COUNT = self.THREAD_COUNT - 1

                    try:
                        # find loss
                        result_loss = re.split(r'% packet loss', str(output))
                        result_loss = re.split(r'received, ', result_loss[0])
                        # find avr
                        result = re.split(r'mdev = ', str(output))
                        result = re.split(r' ms', result[1])
                        result = re.split(r'/', result[0])
                        result_loss[0] = result_loss[1]
                        # rtt avg
                        result_loss[1] = result[1]
                        # rtt min
                        result_loss.append(result[0])
                        # rtt max
                        result_loss.append(result[2])
                        data = result_loss
                    except:
                        print('Error parse ping response')
                """END TEST"""
                if data:
                    print('Result from "{0}": "{1}"'.format(ip, data))
                    #logging.info(u'Result from "{0}": "{1}"'.format(ip, data))
                    self.metric_delay_max.labels(ip, group).set(data[3])
                    self.metric_delay_min.labels(ip, group).set(data[2])
                    self.metric_delay.labels(ip, group).set(data[1])
                    self.metric_loss.labels(ip, group).set(data[0])
                    try:
                        push_to_gateway('graph.arhat.ua:9091', job='ping', registry=self.registry)
                        print('Push DONE')
                        #logging.info(u'Push DONE')
                    except:
                        print('Error connect to push gate')
                        #logging.info(u'Error connect to push gate')
                else:
                    self.metric_delay.labels(ip, group).set(0)
                    self.metric_loss.labels(ip, group).set(0)
                    self.metric_delay_max.labels(ip, group).set(0)
                    self.metric_delay_min.labels(ip, group).set(0)
                    print('some trable with ping')
                    #logging.info(u'some trable with ping')
            else:
                self.metric_delay.labels(ip, group).set(0)
                self.metric_loss.labels(ip, group).set(0)
                self.metric_delay_max.labels(ip, group).set(0)
                self.metric_delay_min.labels(ip, group).set(0)
                task = asyncio.Task.current_task()
                task.cancel()
                print('Cancel %s' % ip)
                #logging.info(u'Cancel %s' % ip)
            yield from asyncio.sleep(int(self.delay_ping))
