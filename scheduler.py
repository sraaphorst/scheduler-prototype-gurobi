# By Sebastian Raaphorst, 2020.

from observation import Observations
from gurobipy import *
import resources


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
        self.current_timeslot = 0.0
        self.observations = Observations()

    def tick(self, timeslot: int):
        """
        Perform one "tick" of the simulation, i.e. elapse the specified time block.
        We formulate and solve the ILP for the specified time, print the schedule, and then adjust the observations.
        If the last tick has passed, print the final results, i.e. the completion of each observation.

        :param timeslot: the active timeslot, from [0, timeslots).
        """

        self.observations.tick(timeslot)

        m = Model()

        # Create all the decision variables and the constraints.
        vs = {}

        # GN- and GS-specific variables:
        gn_vs = set()
        gs_vs = set()

        for id in range(self.observations.num_obs):
            # If this observation can be scheduled at GN at this timeslot, create a variable:
            # It will have 1 if it is scheduled, and 0 otherwise.

            # Keep track on the number of resources we can run observation id on at this timeslot to ensure
            # it only runs on one resource.
            resource_count = 0
            if resources.Site.GN in self.observations.valid_site_times[id][timeslot]:
                v = m.addVar(ub=1, vtype=GRB.BINARY, name="obs_%d_GN" % id)
                vs[(id, resources.Site.GN)] = v
                m.update()
                gn_vs.add(v)
                resource_count += 1
            if resources.Site.GS in self.observations.valid_site_times[id][timeslot]:
                v = m.addVar(ub=1, vtype=GRB.BINARY, name="obs_%d_GS" % id)
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
        print("**** %s ****" % self.observations.priority)
        m.setObjective(sum([self.observations.priority[id] * vs[(id, res)] for (id, res) in vs.keys()]), GRB.MAXIMIZE)

        # The model is complete: call update on it to indicate that this is the case.
        m.update()

        # Auto-tune parameter settings.
        m.tune()

        # Run the ILP.
        m.optimize()

        # Now we determine the schedule for this tick and adjust the observation completion times appropriately.
        print('\n\n*** MODEL ***')
        print(m)

        print('\n\n*** ATTR ***')
        m.printAttr('X')

        print('\n\n*** VARS ***')
        print(m.getVars())


"""
*** MAIN: DEFINE THE OBSERVATIONS AND KICK-OFF ***
"""
if __name__ == '__main__':
    # We schedule three time slots, each of 600 seconds.
    sched = Scheduler(3, 600)

    # Add the observations:

    # OBSERVATION 0:
    # Band 3
    # In time slot 0, can run at GN.
    # In time slot 1, can run at GN and GS.
    # Allocated time: 1000 s, obs time: 650 s
    sched.observations.add_obs('3', {0: {resources.Site.GN}, 1: {resources.Site.GN, resources.Site.GS}}, 1000, 650)

    # OBSERVATION 1:
    # Band 1
    # In time slot 0, can run at GS.
    # In time slot 1, can run at GN.
    # Allocated time: 3000 s, obs time: 2500 s
    sched.observations.add_obs('1', {0: {resources.Site.GS}, 1: {resources.Site.GN}}, 3000, 2500)

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

    sched.tick(0)
