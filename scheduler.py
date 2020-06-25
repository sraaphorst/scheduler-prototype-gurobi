# By Sebastian Raaphorst, 2020.

from observation import Observations
import resources

from typing import Tuple
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
        self.observations = Observations(timeslot_length)

    def schedule(self) -> bool:
        timeslot = 0
        scheduling = []
        while timeslot < self.timeslots:
            current_schedule = self.tick(timeslot)
            scheduling.append((timeslot, [Scheduler.from_schedule_id(c) for c in current_schedule]))
            print("*** Schedule for timeslot %d: %s" % (timeslot, current_schedule))
            print("Remaining times:")
            for id in range(self.observations.num_obs):
                print("Obs %d, used_time=%f, obs_time=%f" % (id, self.observations.used_time[id], self.observations.obs_time[id]))
            print()
            timeslot += 1
        return True

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
        :param id: the schedule ID of the observation
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

        print("*** TIMESLOT %s ***" % timeslot)

        self.observations.tick(timeslot)

        m = Model()
        #m.setParam("OutputFlag", False)

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
        #print("**** %s ****" % self.observations.priority)
        m.setObjective(sum([self.observations.priority[id] * vs[(id, res)] for (id, res) in vs.keys()]), GRB.MAXIMIZE)

        # The model is complete: call update on it to indicate that this is the case.
        m.update()

        # Auto-tune parameter settings.
        m.tune()

        # Run the ILP.
        m.optimize()

        # Now we determine the schedule for this tick and adjust the observation completion times appropriately.
        print('\n\n*** ATTR ***')
        m.printAttr('X')

        s_ids = m.getVars()

        # Extract the variables that correspond to observations, if any:
        current_scheduling = [s_id.VarName for s_id in s_ids if s_id.X == 1]
        for c in current_scheduling:
            self.do_work(c)
        return current_scheduling
        #
        # try:
        #     ids = [int(var.VarName.split('_')[1:3]) for var in m.getVars()]
        # except ValueError as err:
        #     print('Internal illegal state: not a variable.\n"%s":'  % err)
        #     exit(1)
        #
        # for id in ids:
        #     self.observations.do_work(id)
        #     if self.observations.is_done(id):
        #         print("*** Observation %s has been completed." % id)
        #     else:
        #         print("*** Working on observation %s..." % id)
        # else:
        #     print("*** Nothing could be scheduled.")

"""
*** MAIN: DEFINE THE OBSERVATIONS AND KICK-OFF ***
"""
if __name__ == '__main__':

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

    sched.schedule()

    print("*** RESULTS ***")
    for id in range(sched.observations.num_obs):
        print("Obs %d done: %s" % (id, sched.observations.is_done(id)))
