import subprocess

CHRONYC_LINE_PATTERN = re.compile('^(?P<source>\S+).*\s+(?P<offset>[+-]\d+)(?P<unit>\w+)\s+')

class ChronyClient:
	
	def tracking(self):
		"""
		Return True if the chronyd is synchornized or False, otherweise.
		"""
		output = None
		output_line = None
		try:
			output = subprocess.run(['/usr/bin/chronyc', 'tracking'], capture_output=True)
			for line in output.decode().splitlines():
				if line.find('Leap status') >= 0:
					output_line = line.split(":")[1].strip()
					break

			if not output_line:
				return False
		except:
			return False

		return output_line.lower() != 'not synchronised'

	def is_alive(self):
		"""
		Wrapper around the `tracking` call. This should be used rather than the tracking().
		"""
		return self.tracking()

	def get_sourcestats(self):
		"""
		Return information about the drift rate and offset estimation process.
		The dictionary will hold the following keys:

		`name / ip address` - the name an ip address of the NTP server source
		`units` - the units of measurement for the timestamp drift
	 	`offset` - the offset difference measured in `units`	
		"""
		output = None
		try:
			output = subprocess.run(['/usr/bin/chronyc', 'sourcestats'], capture_output=True)
			if output.returncode != 0:
				raise RunTimeError(output.stderr.decode())
		except OSError:
			raise CallError('chronyc: get_sourcestats failed')

		for line in output.stdout.decode().splitlines():
			mch = CHRONYC_LINE_PATTERN.search(line)
			if mch is None:
				continue

			src = m.group('source')
			offset = float(m.group('offset'))
			unit = m.group('unit')

			return m.groupdict()

	def request(self):
		"""
		This function is used as the main entry point to call into the ChronyCollector to
		gather data for the source statistics. It is a wrapper around `get_sourcestats`.
		"""
		return self.get_sourcestats()
