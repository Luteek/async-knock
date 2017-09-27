from subprocess import Popen, PIPE
import re


def ping_d(ip, parameters):
    line = ('ping' + ' ' + ip + ' ' + parameters)
    cmd = Popen(line.split(' '), stdout=PIPE)
    output = cmd.communicate()[0]

    try:
        #find loss
        result_loss = re.split(r'% packet loss', str(output))
        result_loss = re.split(r'received, ', result_loss[0])
        #find avr
        result = re.split(r'mdev = ', str(output))
        result = re.split(r' ms', result[1])
        result = re.split(r'/', result[0])
        result_loss[0] = result_loss[1]
		#rtt avg
        result_loss[1] = result[1]
		# rtt min
        result_loss.append(result[0])
		#rtt max
        result_loss.append(result[2])
        return (result_loss)
    except:
        return False
