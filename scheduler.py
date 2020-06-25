# By Sebastian Raaphorst, 2020.

from observation import Observations
import resources

from typing import List, Tuple
from gurobipy import *


class Scheduler:
    """
    The simulation prototype scheduler.
    This formulates the problem, runs the simulation, and then adjusts the completion rate of the observations.
    """

    def __init__(self, timeslots: int, timeslot_length: float = 300):
        """
        Initializes the simulation and sets the current time block to 0 and the observations to empty.

        :param timeslots: the number of time blocks of time block length
        :param timeslot_length: the length of each time block, in s
        """
        self.timeslots = timeslots
        self.timeslot_length = timeslot_length
        self.observations = Observations()

    def schedule(self) -> List[List[str]]:
        """
        Perform the scheduling.
        :return: the schedule, which is a list of list of Schedule_ID, indexed by time slot.
        """
        timeslot = 0
        scheduling = []
        while timeslot < self.timeslots:
            current_schedule = self.tick(timeslot)
            scheduling.append(current_schedule)
            print("\n\n*** TIMESLOT %s ***" % timeslot)
            print("*** Schedule for timeslot %d: %s" % (timeslot, current_schedule))
            print("*** Remaining times:")
            for id in range(self.observations.num_obs):
                print("Obs %d, used_time=%d, obs_time=%d, done=%s" % (id,
                                                                      int(self.observations.used_time[id]),
                                                                      int(self.observations.obs_time[id]),
                                                                      self.observations.is_done(id)))
            print("*** ENDING TIMESLOT %s ***\n\n\n" % timeslot)
            timeslot += 1
        return scheduling

    @staticmethod
    def to_schedule_id(id: int, site: resources.Site) -> str:
        """
        Convert an ID and a site to a scheduler ID.
        :param id: the ID of the observation
        :param site: the Site resource
        :return: the scheduler's ID for the id at the site
        """
        return "obs_%d_%s" % (id, site.name)

    @staticmethod
    def from_schedule_id(scheduler_id: str) -> Tuple[int, resources.Site]:
        """
        Given a scheduler ID, extract the observation and the site.
        :param scheduler_id: the scheduler ID
        :return: A tuple comprising the ID and the Site resource
        """
        fields = scheduler_id.split('_')
        return int(fields[1]), resources.Site[fields[2]]

    def do_work(self, scheduler_id: str):
        """
        Register work done on an observation.
        :param scheduler_id: the schedule ID of the observation
        """
        # We have used up one of the time slots.
        self.observations.used_time[Scheduler.from_schedule_id(scheduler_id)[0]] += self.timeslot_length

    def tick(self, timeslot: int):
        """
        Perform one "tick" of the simulation, i.e. elapse the specified time block.
        We formulate and solve the ILP for the specified time, print the schedule, and then adjust the observations.
        If the last tick has passed, print the final results, i.e. the completion of each observation.

        :param timeslot: the active timeslot, from [0, timeslots).
        """

        print("*** BEGINNING TIMESLOT %s ***" % timeslot)

        self.observations.tick(timeslot)

        m = Model()
        m.setParam("OutputFlag", False)

        # Create all the decision variables and the constraints.
        vs = {}

        # GN- and GS-specific variables:
        gn_vs = set()
        gs_vs = set()

        # Create variables for incomplete observations.
        for id in [id for id in range(self.observations.num_obs)
                   if not self.observations.is_done(id)]:

            # If this observation can be scheduled at GN at this timeslot, create a variable:
            # It will have 1 if it is scheduled, and 0 otherwise.

            # Keep track on the number of resources we can run observation id on at this timeslot to ensure
            # it only runs on one resource.
            resource_count = 0
            if resources.Site.GN in self.observations.valid_site_times[id][timeslot]:
                v = m.addVar(ub=1, vtype=GRB.BINARY, name=Scheduler.to_schedule_id(id, resources.Site.GN))
                vs[(id, resources.Site.GN)] = v
                m.update()
                gn_vs.add(v)
                resource_count += 1
            if resources.Site.GS in self.observations.valid_site_times[id][timeslot]:
                v = m.addVar(ub=1, vtype=GRB.BINARY, name=Scheduler.to_schedule_id(id, resources.Site.GS))
                vs[(id, resources.Site.GS)] = v
                m.update()
                gs_vs.add(v)
                resource_count += 1

            # If this observation can be run at both resources, make sure that it is only run at one of the two
            # resources.
            if resource_count == 2:
                m.addConstr(vs[(id, resources.Site.GN)] + vs[(id, resources.Site.GS)] <= 1, "c_not_both_%d" % id)

        # Of all the observations that can start at GN at this timeslice, only one at a time is allowed.
        m.addConstr(sum(gn_vs) <= 1, "c_gn")

        # Of all the observations that can start at GN at this timeslice, only one at a time is allowed.
        m.addConstr(sum(gs_vs) <= 1, "c_gn")

        # Create the objective function on which we wish to maximize.
        # print("**** %s ****" % self.observations.priority)
        m.setObjective(sum([self.observations.priority[id] * vs[(id, res)] for (id, res) in vs.keys()]), GRB.MAXIMIZE)

        # The model is complete: call update on it to indicate that this is the case.
        m.update()

        # Auto-tune parameter settings.
        m.tune()

        # Run the ILP.
        m.optimize()

        # Now we determine the schedule for this tick and adjust the observation completion times appropriately.
        # print('\n\n*** ATTR ***')
        # m.printAttr('X')

        s_ids = m.getVars()

        # Extract the variables that correspond to observations, if any:
        current_scheduling = [s_id.VarName for s_id in s_ids if s_id.X == 1]
        for c in current_scheduling:
            self.do_work(c)
        return current_scheduling


def run_simulation1():
    # We schedule three time slots, each of 600 seconds.
    sched = Scheduler(2, 600)

    # Add the observations:

    # OBSERVATION 0:
    # Band 3
    # In time slot 0, can run at GN.
    # In time slot 1, can run at GN and GS.
    # Allocated time: 1000 s, obs time: 650 s
    sched.observations.add_obs('3', {0: {resources.Site.GN}, 1: {resources.Site.GN, resources.Site.GS}}, 600, 650)

    # OBSERVATION 1:
    # Band 1
    # In time slot 0, can run at GS.
    # In time slot 1, can run at GN.
    # Allocated time: 3000 s, obs time: 2500 s
    sched.observations.add_obs('1', {0: {resources.Site.GS}, 1: {resources.Site.GN}}, 3000, 500)

    # OBSERVATION 2:
    # Band 3
    # In time slot 0, can run at GS.
    # In time slot 1, can run at GN.
    # Allocated time: 9600 s, obs time 9000
    sched.observations.add_obs('2', {0: {resources.Site.GS}, 1: {resources.Site.GN}}, 9600, 9000)

    # OBSERVATION 3:
    # Band 2
    # In time slot 0, can run at GN and GS.
    # In time slot 1, can run at GN.
    # Allocated time: 7200 s, obs time 6000
    sched.observations.add_obs('2', {0: {resources.Site.GN, resources.Site.GS}, 1: {resources.Site.GN}}, 6000, 7200)

    # OBSERVATION 4:
    # Band 4
    # In time slot 0, can run at GN and GS.
    # In time slot 1, can run at GN.
    # Allocated time: 6000 s, obs time 4000
    sched.observations.add_obs('4', {0: {resources.Site.GN, resources.Site.GS}, 1: {resources.Site.GN}}, 6000, 4000)

    # OBSERVATION 5:
    # Band 1
    # In time slot 0, can run at GN.
    # In time slot 1, can run at GN.
    # Allocated time: 12000 s, obs time 9000
    # If we change time 0 to run only with GS, will clash with Observation 1, and Observation 3 (a band 2 program) will
    #    be scheduled instead.
    sched.observations.add_obs('1', {0: {resources.Site.GN}, 1: {resources.Site.GN}}, 12000, 9000)

    # OBSERVATION 6:
    # Band 2
    # In time slot 0, can run at GN and GS.
    # In time slot 1, can run at GS.
    # Allocated time: 66000 s, obs time 60000
    sched.observations.add_obs('2', {0: {resources.Site.GN, resources.Site.GN}, 1: {resources.Site.GS}}, 66000, 60000)

    return sched, sched.schedule()


def run_simulation2():
    sched = Scheduler(10, 600)

    # Shorthand
    NS = {resources.Site.GN, resources.Site.GS}
    N = {resources.Site.GN}
    S = {resources.Site.GS}
    E = set()

    # OBS_ID                  BAND  TIME_SLICE_RESOURCES                                         OBS_TIME ALLOC_TIME
    # 0
    sched.observations.add_obs('1', {0: S,  1: E, 2: S,  3: NS, 4: NS, 5: E,  6: N,  7: NS, 8: NS}, 1200,      1200)
    # 1
    sched.observations.add_obs('3', {0: NS, 1: N, 2: NS, 3: E,  4: N,  5: E,  6: NS, 7: S,  8: NS},  500,       500)
    # 2
    sched.observations.add_obs('2', {0: N,  1: E, 2: N,  3: E,  4: NS,  5: S, 6: NS, 7: NS, 8: NS},  700,       700)
    # 3
    sched.observations.add_obs('1', {0: S,  1: S, 2: NS, 3: NS, 4: S,   5: N, 6: NS, 7: E,  8: NS},  600,       600)
    # 4
    sched.observations.add_obs('2', {0: S,  1: N, 2: S,  3: E,  4: NS,  5: N, 6: S,  7: N,  8: NS}, 1800,      1800)
    # 5
    sched.observations.add_obs('3', {0: N,  1: E, 2: NS, 3: E,  4: E,   5: E, 6: N,  7: E,  8: NS}, 1200,      1200)

    return sched, sched.schedule()


"""
*** MAIN: DEFINE THE OBSERVATIONS AND KICK-OFF ***
"""
if __name__ == '__main__':

    sched, final_sched = run_simulation2()

    print("*** SCHEDULE ***")
    for s in range(len(final_sched)):
        print("Time slot %d: %s" % (s, final_sched[s]))
    for id in range(sched.observations.num_obs):
        print("Obs %d done: %s" % (id, sched.observations.is_done(id)))
