""" top.py

Linux parser for the following command:
    * top -n 1 -b
"""

# Python
import re

# Metaparser
from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Schema, Any, Optional

# parser utils
from genie.libs.parser.utils.common import Common


# ===========================
# Schema for 'top -n 1 -b'
# ===========================
class TopSchema(MetaParser):
    """Schema for "top -n 1 -b" """

    schema = {
        "pid": {
            Any(): {
                "user": str,  # owner of process
                "pr": int,  # priority
                "ni": int,  # nice value
                "virt": int,  # amount of virtual memory used
                "res": int,  # amount of resident memory used
                "shr": int,  # amount of shared memory used
                "s": str,  # status
                "cpu": float,  # share of CPU time used
                "mem": float,  # share of physical memory used
                "time": str,  # Total CPU time used in hundreds of a second
                "command": str,  # The command line
            }
        }
    }


# ===========================
# Parser for 'top -n 1 -b'
# ===========================
class Top(TopSchema):

    '''Parser for "top -n 1 -b"'''

    cli_command = ["top -n 1 -b"]

    def cli(self, output=None):
        if output is None:
            command = self.cli_command[0]
            out = self.device.execute(command)
        else:
            out = output

        # Init vars
        parsed_dict = {}

        """ Sample output
        top - 13:03:02 up  3:53,  1 user,  load average: 0.00, 0.05, 0.07
        Tasks: 158 total,   1 running, 157 sleeping,   0 stopped,   0 zombie
        %Cpu(s):  0.0 us,  6.2 sy,  0.0 ni, 93.8 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
        MiB Mem :   3924.3 total,   2434.9 free,    287.7 used,   1201.7 buff/cache
        MiB Swap:    923.3 total,    923.3 free,      0.0 used.   3380.2 avail Mem
        
        PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
       2936 yuanl     20   0   11872   3764   3308 R   6.2   0.1   0:00.02 top
          1 root      20   0  101536  11020   8124 S   0.0   0.3   0:01.86 systemd
          2 root      20   0       0      0      0 S   0.0   0.0   0:00.00 kthreadd
          3 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 rcu_gp
          4 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 rcu_par_gp
          5 root       0 -20       0      0      0 I   0.0   0.0   0:00.00 slub_flushwq
        """
        p1 = re.compile(
            r"^(?P<pid>\d+)\s+(?P<user>\S+)\s+(?P<pr>\d+)"
            + r"\s+(?P<ni>-?\d+)\s+(?P<virt>\d+)\s+(?P<res>\d+)\s+(?P<shr>\d+)"
            + r"\s+(?P<s>\S)\s+(?P<cpu>\d+\.\d)\s+(?P<mem>\d+\.\d)\s+(?P<time>\d+:\d+\.\d+)"
            + r"\s+(?P<command>\S+)$"
        )

        for line in out.splitlines():
            line = line.strip()

            m = p1.match(line)
            if m:
                groups = m.groupdict()
                pid = groups["pid"]
                del groups["pid"]
                for keyname in ("pr", "ni", "virt", "res", "shr"):
                    groups[keyname] = int(groups[keyname])
                for keyname in ("cpu", "mem"):
                    groups[keyname] = float(groups[keyname])

                parsed_dict.setdefault("pid", {}).setdefault(pid, groups)

        return parsed_dict
