# Acceptance test for CMD-AGV0 (written by baseline; the executor may not edit it).
from pathlib import Path
assert (Path(__file__).parent / 'ping.txt').read_text() == 'pong\n', 'ping.txt must be exactly pong + newline'
print('ok')
