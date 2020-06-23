# observation.py
# By Sebastian Raaphorst and Bryan Miller, 2020.

from typing import Mapping, Set
import numpy as np
import resources


class Observations:
    """
    The set of observations and the necessary information to formulate the mathematical ILP model
    to represent this as a scheduling problem.

    We schedule an observation every five minutes across a time range, during which an observation is valid at
    a certain resource or not.
    """

    def __init__(self):
        """
        Initialize to an empty set of observations.
        Right now, this is a mix of numpy and python as I think we need constructs from both.

        num_obs - the number of observations
        band - an array of band ('1', '2', '3', '4' as per Bryan's representation below) for observation i
        completed - the current completion fraction
        used_time - the time used so far
        allocation_time - the total time allocation
        obs_time - the length of the observation
        allocated - the time allocated for the observation
        valid_site_times - a list of map {timeslot_t -> Set(Site)} representing what sites the observation can be
                            observed at at
                            time t
        priority - the priority for time slice t
        timeslot - the currently executing time slot
        """
        self.num_obs = 0
        self.band = np.empty((0,), dtype=str)
        self.completed = np.empty((0,), dtype=float)
        self.used_time = np.empty((0,), dtype=float)
        self.allocated_time = np.empty((0,), dtype=float)
        self.obs_time = np.empty((0,), dtype=float)
        self.valid_site_times = []
        self.priority = np.empty((0,), dtype=float)
        self.timeslot = 0

        self.params = {'1': {'m1': 1.406, 'b1': 2.0, 'm2': 0.50, 'b2': 0.5, 'xb': 0.8, 'xb0': 0.0, 'xc0': 0.0},
                       '2': {'m1': 1.406, 'b1': 1.0, 'm2': 0.50, 'b2': 0.5, 'xb': 0.8, 'xb0': 0.0, 'xc0': 0.0},
                       '3': {'m1': 1.406, 'b1': 0.0, 'm2': 0.50, 'b2': 0.5, 'xb': 0.8, 'xb0': 0.0, 'xc0': 0.0},
                       '4': {'m1': 0.00, 'b1': 0.0, 'm2': 0.00, 'b2': 0.0, 'xb': 0.8, 'xb0': 0.0, 'xc0': 0.0},
                       }

        # Now spread the metric to avoid band overlaps
        # m2 = {'3': 0.5, '2': 3.0, '1':10.0} # use with b1*r where r=3
        m2 = {'3': 1.0, '2': 6.0, '1': 20.0}  # use with b1 + 5.
        xb = 0.8
        b1 = 0.2
        for band in ['3', '2', '1']:
            b2 = b1 + 5. - m2[band]
            m1 = (m2[band] * xb + b2) / xb ** 2
            self.params[band]['m1'] = m1
            self.params[band]['m2'] = m2[band]
            self.params[band]['b1'] = b1
            self.params[band]['b2'] = b2
            self.params[band]['xb'] = xb
            b1 += m2[band] * 1.0 + b2

    def add_obs(self, band: str, valid_times: Mapping[int, Set[resources.Site]], allocated_time: float,
                obs_time: float):
        assert (allocated_time != 0)
        self.band = np.append(self.band, band)
        self.valid_site_times.append(valid_times)
        self.used_time = np.append(self.used_time, 0)
        self.allocated_time = np.append(self.allocated_time, allocated_time)
        self.obs_time = np.append(self.obs_time, obs_time)
        self.num_obs += 1

    def print_obs(self, id: int, timeslot: int):
        return ("Observation %s: band=%s completion=%0.03f, priority=%0.03f, sites=%s" %
                ((' ' * (len(str(self.num_obs)) - len(str(id))) + str(id)),
                 self.band[id],
                 self.completed[id],
                 self.priority[id],
                 resources.timeslot_sites_string(self.valid_site_times[id], timeslot)))

    def tick(self, timeslot: int):
        self.timeslot = timeslot
        self.calculate_priority()
        print(self.priority)
        # Order so that the highest priority is at the top.
        ordered = list(zip(*list(reversed(sorted(list(zip(self.priority, range(len(self.priority)))))))))[1]
        print(ordered)
        for i in ordered:
            print(self.print_obs(i, timeslot))

    def calculate_completion(self):
        """
        Calculate the completion of the observations.
        This is a simplification that expects the observation to take up (at least) the entire allocated time.
        """
        time = (self.used_time + self.obs_time) / self.allocated_time
        self.completed = np.where(time > 1., 1., time)
        print(self.completed)

    def __len__(self):
        return self.num_obs

    def calculate_priority(self):
        """
        Compute the priority as a function of completeness fraction and band for the objective function.

        Parameters
            completion: array/list of program completion fractions
            band: integer array of bands for each program

        By Bryan Miller, 2020.
        """
        # Calculate the completion for all observations.
        self.calculate_completion()

        nn = len(self.completed)
        metric = np.zeros(nn)
        for ii in range(nn):
            sband = str(self.band[ii])

            # If Band 3, then the Band 3 min fraction is used for xb
            if self.band[ii] == 3:
                xb = 0.8
            else:
                xb = self.params[sband]['xb']

            # Determine the intercept for the second piece (b2) so that the functions are continuous
            b2 = self.params[sband]['b2'] + self.params[sband]['xb0'] + self.params[sband]['b1']

            # Finally, calculate piecewise the metric.
            if self.completed[ii] == 0.:
                metric[ii] = 0.0
            elif self.completed[ii] < xb:
                metric[ii] = self.params[sband]['m1'] * self.completed[ii] ** 2 + self.params[sband]['b1']
            elif self.completed[ii] < 1.0:
                metric[ii] = self.params[sband]['m2'] * self.completed[ii] + b2
            else:
                metric[ii] = self.params[sband]['m2'] * 1.0 + b2 + self.params[sband]['xc0']
        print(metric)
        self.priority = metric


if __name__ == '__main__':
    obs = Observations()
    obs.add_obs('3', {0: {resources.Site.GN}, 1: {resources.Site.GN, resources.Site.GS}}, 480, 300)
    obs.add_obs('1', {0: {resources.Site.GS}, 1: {resources.Site.GN}}, 300, 250)
    obs.add_obs('2', {0: {resources.Site.GS}, 1: {resources.Site.GN}}, 200, 150)
    obs.add_obs('2', {0: {resources.Site.GN}, 1: {resources.Site.GN}}, 300, 250)
    obs.add_obs('4', {0: {resources.Site.GN}, 1: {resources.Site.GN}}, 300, 200)

    obs.tick(0)
    print("Done")
