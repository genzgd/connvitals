import asyncio
import socket
import time

from connvitals import icmptypes
from connvitals import utils


loop = asyncio.get_event_loop()
BASE_PORT = 33434


def get_id_and_hop(packet):
	return (packet[50] << 8) + packet[51], packet[53] - 8


def set_ttl(sender, ttl):
	sender.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)


def is_trace_response(packet):
	return packet[20] in {11, 3}


def get_intended_destination(packet):
	return ".".join(str(byte) for byte in packet[44:48])


class TraceBatch:
	def __init__(self, hops=30, loop_time=0.05, loop_count=-1):
		self.completed = 0
		self.trackers = {}
		self.callback = None
		self.open = False
		self.hops = hops
		self.loop_count = loop_count
		self.loop_time = loop_time
		self.sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=17)
		self.receiver = socket.socket(family=socket.AF_INET, type=socket.SOCK_RAW, proto=socket.IPPROTO_ICMP)
		self.receiver.setblocking(False)

	def close(self):
		self.sender.close()
		self.receiver.close()

	def trace(self, hosts, callback = None):
		self.trackers = {host_id + BASE_PORT: TraceTracker(host_id + BASE_PORT, host, self) for host_id, host in enumerate(hosts.values())}
		self.callback = callback
		self.open = True
		asyncio.ensure_future(self.listen(), loop=loop)
		loop.run_forever()

	def _start_trace(self):
		self.completed = 0
		for tracker in self.trackers.values():
			tracker.send()

	@asyncio.coroutine
	def listen(self):
		self._start_trace()
		while self.open:
			packet, address = yield from sock_recvfrom(self.receiver, 1024)
			if self.open:
				if is_trace_response(packet):
					destination = get_intended_destination(packet)
					host_id, hop = get_id_and_hop(packet)
					tracker = self.trackers.get(host_id)
					if tracker and destination == tracker.host.addr:
						if hop == tracker.current_hop:
							tracker.receive(address)
							print("Tracked packet, host_id: {}, hop: {}".format(host_id, hop))
						else:
							print("Tracked packet, host_id: {}, expected hop {}, got hop {}".format(host_id, tracker.current_hop, hop))
					else:
						print("Unrecognized {} packet, host_id {}, hop: {}".format(icmptypes.get_type(packet), host_id, hop))
				else:
					print("Nontrace packet: {}", icmptypes.get_type(packet))

	def send(self, tracker):
		if tracker.current_hop > self.hops:
			self.complete(tracker)
			return False

		set_ttl(self.sender, tracker.current_hop)
		try:
			# Adding some data allows us to hack the hop number into the length field of the UDP packet
			self.sender.sendto(b'x' * tracker.current_hop, (tracker.host[0], tracker.host_id))
		except OSError as e:
			tracker.error()
		return True

	def complete(self, tracker):
		tracker.loops += 1
		if self.loop_count == -1 or (0 < self.loop_count <= tracker.loops):
			self._complete_tracker()
		else:
			tracker.reset()
			loop.call_later(self.loop_time, tracker.send)

	def _complete_tracker(self):
		self.completed += 1
		if self.completed >= len(self.trackers):
			loop.stop()
			self.open = False
			if self.callback:
				self.callback([(tracker.host.addr, utils.Trace(tracker.results)) for tracker in self.trackers.values()])


class TraceTracker:
	def __init__(self, host_id, host, batch):
		self.host_id = host_id
		self.host = host
		self.batch = batch
		self.reset()
		self.loops = 0

	def reset(self):
		self.results = []
		self.last_sent_timestamp = 0
		self.current_hop = 0
		self.timeout_handle = None

	def send(self):
		self.current_hop += 1
		if self.batch.send(self):
			self.last_sent_timestamp = time.time()
			self.timeout_handle = loop.call_later(0.05, self.error)

	def error(self):
		self.results.append(utils.TraceStep("*", -1))
		self.send()

	def receive(self, address):
		self.timeout_handle.cancel()
		rtt = time.time() - self.last_sent_timestamp
		self.results.append(utils.TraceStep(address[0], rtt * 1000))
		if address[0] == self.host.addr:
			self.batch.complete(self)
		else:
			self.send()


# From suggestion in this thread:  https://bugs.python.org/issue26395
@asyncio.coroutine
def sock_recvfrom(nonblocking_sock, *pos, **kw):
	while True:
		try:
			return nonblocking_sock.recvfrom(*pos, **kw)
		except BlockingIOError:
			future = asyncio.Future(loop=loop)
			loop.add_reader(nonblocking_sock.fileno(), future.set_result, None)
			try:
				yield from future
			finally:
				loop.remove_reader(nonblocking_sock.fileno())
