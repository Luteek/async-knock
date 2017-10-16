import asyncio
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from subprocess import Popen, PIPE
import re
import logging


class Worker:
    logging.basicConfig(filename='log.log', level=logging.DEBUG, format='%(asctime)s -%(levelname)s -%(message)s')
    registry = CollectorRegistry()
    """Основной луп"""
    loop = asyncio.get_event_loop()
    THREAD_COUNT = 0
    host_config = [' ']
    task_add = []
    task_remove = [' ']

    """ 
    объявление метрик типа Guage для Prometheus
    включает в себя набор лейблов    
    """
    metric_delay = Gauge('ping_pkt_latency_avg', 'h', ['ip', 'group', 'name'], registry=registry)
    metric_loss = Gauge('ping_pkt_lost', 'l', ['ip', 'group', 'name'], registry=registry)
    metric_received_pkt = Gauge('ping_match_received', 'packet received', ['ip', 'group', 'name', 'transmitted'], registry=registry)
    metric_delay_min = Gauge('ping_pkt_latency_min', 'l', ['ip', 'group', 'name'], registry=registry)
    metric_delay_max = Gauge('ping_pkt_latency_max', 'l', ['ip', 'group', 'name'], registry=registry)

    def __init__(self, gateway_host, job, max_thread, png_param, delay_ping, delay_collect, delay_parse):
        """
        Инициализация переменных при создании объекта
        :param gateway_host:    - адрес сервера прометеуса 
        :param job:             - job метрики
        :param max_thread:      - задает максимальное кол-во потоков
        :param png_param:       - параметры пинга
        :param delay_ping:      - время задержки задачи пинга
        :param delay_parse:     - время задержки задачи парса файла с хостам
        """
        self.gateway_host = gateway_host
        self.job = job
        self.SEMAPHORE = asyncio.Semaphore(int(max_thread))

        self.DELAY_COLLECT = int(delay_collect)

        self.png_normal = png_param[0]
        self.png_fast = png_param[1]
        self.png_large = png_param[2]
        self.png_killing = png_param[3]

        self.delay_ping = int(delay_ping)
        self.delay_parse = int(delay_parse)


    def load_config(self):
        """
        Парсит файл с задачами распределяя новые или удаленные задачи 
        в соответствующие массивы self.task_remove\self.task_add
        !!!!большой костыль в жопе, надо оптимизировать!!!!
        :return: - ничего не возвращает
        """
        self.task_remove = [' ']
        self.task_add = []
        data = []
        with open('tsk.txt', 'r') as file:
            for row in file.readlines():
                if len(row) > 2:
                    data.append(row.strip().split())

        for old_task in self.host_config:
            must_be_remove = True
            for update_task in data:
                if old_task == update_task:
                    must_be_remove = False
            if must_be_remove:
                self.task_remove.append(old_task)
                self.host_config.remove(old_task)

        for new_task in data:
            must_be_add = True
            for old in self.host_config:
                if old == new_task:
                    must_be_add = False
            if must_be_add:
                self.task_add.append(new_task)
                self.host_config.append(new_task)
        print('LOAD_CONFIG:%s' % self.host_config)
        logging.info(u'LOAD_CONFIG:%s' % self.host_config)

    @asyncio.coroutine
    def start_config(self):
        """
        Стартовая функция в event_loop. 
        Через заданный промежуток времени запускает функцию парчинга файла задач load_config()
        Добавляет задачи в основной луп с помощью массива новых задач task_add[]
        :return: - ничего не возвращает
        """
        while True:
            self.load_config()
            for config in self.task_add:
                try:
                    self.loop.create_task(self.ping_host(config[0], config[1], config[2], config[3]))
                except:
                    """ При возникновении несостыковки строки конфигурации шлет нас подальше,
                    не добавляя новую задачу
                    """
                    print('Wrong config line %s'%config)
                    logging.error(u'Wrong config line %s'%config)
            yield from asyncio.sleep(self.delay_parse)

    @asyncio.coroutine
    def ping_host(self, ip, parameters, group, name):
        """
        Гвоздь программы. 
        :param ip: - айпи хоста для пинга
        :param parameters:  - параметры пинга
        :param group: - определяет группу для лейбла метрики
        :param name:  - определяет имя для лейбла метрики
        :return: - ничего не возвращает
        
        Выполняет поставленную задачу пинга, если пул потоков свободен, 
        в противном случае отдает управление , засыпает на 0 сек.
        
        При выполнения пинга, внезависимости от результата засыпает на заданное время.
        
        Если обнаруживает себя в массиве task_remove - удаляет себя из стека задач.
        """

        if parameters == 'large':
            parameters = self.png_large
        elif parameters == 'fast':
            parameters = self.png_fast
        elif parameters == 'killing':
            parameters = self.png_killing
        else:
            parameters = self.png_normal

        while True:
            data = dict(
                pkt_transmitted=pkt_out[0],
                pkt_received=pkt_out[1],
                pkt_loss=pkt_out[2],
                rtt_min=ltn_out[0],
                rtt_avg=ltn_out[1],
                rtt_max=ltn_out[2], )

            flag = False
            for line in self.task_remove:
                if ip == line[0] and parameters == line[1] and group == line[2]:
                    flag = True

            if not flag:
                for i in range(self.delay_ping):
                    with(yield from self.SEMAPHORE):
                        print('start ping ip %s' % ip)
                        """Если пул свободен, начинаем выполнение и отдаем управление в главный луп"""
                        #logging.info(u'start ping ip %s' % ip)
                        line = ('sudo ping' + ' ' + ip + ' ' + parameters)
                        cmd = Popen(line.split(' '), stdout=PIPE)
                        yield from asyncio.sleep(0)

                        output = cmd.communicate()[0]
                        output = str(output)
                        try:
                            packet_regex = re.compile(r'(\d+) packets transmitted, (\d+) (?:packets )?received, (\d+\.?\d*)% packet loss')
                            latency_regex = re.compile(r'(\d+.\d+)/(\d+.\d+)/(\d+.\d+)/(\d+.\d+)')
                            packet_match = packet_regex.search(output)
                            latency_match = latency_regex.search(output)

                            pkt_out = packet_match.groups()
                            ltn_out = latency_match.groups()
                            data_new = dict(
                                pkt_transmitted=pkt_out[0],
                                pkt_received=pkt_out[1],
                                pkt_loss=pkt_out[2],
                                rtt_min=ltn_out[0],
                                rtt_avg=ltn_out[1],
                                rtt_max=ltn_out[2], )
                            data = self.inc_dict(data, data_new)
                        except:
                           print('Error parse ping response')

                data = self.middle_result(self.delay_ping)

                if data:
                    self.metric_delay_max.labels(ip, group, name).set(data['rtt_max'])
                    self.metric_delay_min.labels(ip, group, name).set(data['rtt_min'])
                    self.metric_delay.labels(ip, group, name).set(data['rtt_avg'])
                    self.metric_loss.labels(ip, group, name).set(data['pkt_loss'])

                    self.metric_received_pkt.labels(ip, group, name, data['pkt_transmitted']).set(data['pkt_received'])
                    try:
                        push_to_gateway('graph.arhat.ua:9091', job='ping', registry=self.registry)
                        print('Push %s done' % ip)
                    except:
                        print('Error connect to push gate')
                        logging.error(u'Error connect to pushgate')
                else:
                    self.metric_delay.labels(ip, group, name).set(0)
                    self.metric_loss.labels(ip, group, name).set(0)
                    self.metric_delay_max.labels(ip, group, name).set(0)
                    self.metric_delay_min.labels(ip, group, name).set(0)
                    self.metric_received_pkt.labels(ip, group, name, 0).set(0)

                    print('some trable with ping')
                    logging.warning(u'Some trable with ping %s' % ip)
                    """Когда задача выполнена засыпаем на заданное время и отдаем управление в главный луп"""
                yield from asyncio.sleep(int(self.DELAY_COLLECT))
            else:
                self.metric_delay.labels(ip, group, name).set(0)
                self.metric_loss.labels(ip, group, name).set(0)
                self.metric_delay_max.labels(ip, group, name).set(0)
                self.metric_delay_min.labels(ip, group, name).set(0)
                self.metric_received_pkt.labels(ip, group, name, 0).set(0)

                task = asyncio.Task.current_task()
                task.cancel()
                print('Cancel %s' % ip)
                logging.warning(u'Cancel %s' % ip)
                yield from asyncio.sleep(0)

    def inc_dict(self, data, data_new):
        for param in data:
            data[param] += data_new[param]
        return data

    def middle_result(self, data, num_range):
        for param in data:
            data[param] = data[param]/num_range
        return data