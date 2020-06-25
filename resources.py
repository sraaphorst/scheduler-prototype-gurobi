# resources.py
# By Sebastian Raaphorst, 2020.

# The resources available for scheduling, in groups that do not clash.
from enum import Enum
from typing import Mapping, Set


class Site(Enum):
    GN = 1
    GS = 2


def timeslot_sites_string(sites: Mapping[int, Set[Site]], timeslot: int) -> str:
    return sites_string(sites[timeslot])


def sites_string(sites: Set[Site]) -> str:
    return ' '.join([site.name for site in sites])

# If an observation O can be run on both sites n = GN and s = GS, we need the constraint:
# O_int + O_ist <= 0

# For all the observations O_i, O_j, O_k, etc. that can run on site n (alternatively s), to ensure each site is only
# being used for one observation at a time, we need constraints:
# O_int + O_jnt + O_knt + ... <= 1
