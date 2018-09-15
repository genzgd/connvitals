import multiprocessing.pool

from connvitals import traceroute
from connvitals import config
from connvitals.utils import getaddr

config.init()
BASE_PORT = 33434


def trace(host, id):
	with traceroute.Tracer(host, id, 30) as tracer:
		result = tracer.trace()
		print(result)


with multiprocessing.pool.ThreadPool(len(config.CONFIG.HOSTS)) as pool:
	waitables = [pool.apply_async(trace, (getaddr(host), id + BASE_PORT)) for id, host in enumerate(config.CONFIG.HOSTS)]
	for waitable in waitables:
		waitable.wait()
	pool.close()
	pool.join()
