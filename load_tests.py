import time
import random

from connvitals import utils

from connvitals.multitrace import TraceBatch
from connvitals.traceroute import Tracer


seed = 9273
count = 10


def run_trace(host, host_id, hops, sleep_time):
	with Tracer(host, host_id, hops) as tracer:
		while True:
			result = tracer.trace()
			time.sleep(sleep_time / 1000)


def random_ip():
	first = random.randint(1, 223)
	while first in (10, 127, 172, 192, 198):
		first = random.randint(1, 223)
	return '{}.{}.{}.{}'.format(first, random.randint(0,255), random.randint(0, 255), random.randint(0,255))


def generate_hosts():
	#random.seed(seed)
	return {ipaddr: utils.getaddr(ipaddr) for ipaddr in (random_ip() for _ in range(count))}


def multitrace():
	batch = TraceBatch()
	batch.trace(generate_hosts(), loop_count=1, hops=6, callback=lambda *args, **kwargs: batch.close())


multitrace()