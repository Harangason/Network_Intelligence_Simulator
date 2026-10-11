"""Read-only stack sampling in the disposable diagnostic container only."""
import faulthandler
import os

_sample_file = open('/tmp/nis-stack-samples-' + str(os.getpid()) + '.log', 'a')
faulthandler.dump_traceback_later(15, repeat=True, file=_sample_file)
