from connvitals import config
from connvitals.multitrace import TraceBatch

config.init()
batch = TraceBatch()


def process_results(results):
	for result in results:
		for step in result:
			print(step)
	batch.close()


batch.trace(config.CONFIG.HOSTS, process_results)

