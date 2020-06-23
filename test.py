from gurobipy import *

m = Model()

p = m.addVar(name="pennies", vtype=GRB.INTEGER)
n = m.addVar(name="nickels", vtype=GRB.INTEGER)
d = m.addVar(name="dimes", vtype=GRB.INTEGER)
q = m.addVar(name="quarters", vtype=GRB.INTEGER)
s = m.addVar(name="dollars", vtype=GRB.INTEGER)

m.setObjective(0.01 * p + 0.05 * n + 0.1 * d + 0.25 * q + s, GRB.MAXIMIZE)
cu = m.addConstr(0.06 * p + 3.8 * n + 2.1 * d + 5.2 * q + 7.2 * s <= 1000, name="copper")
ni = m.addConstr(1.2 * n + 0.2 * d + 0.5 * q + 0.2 * s <= 50, name="nickel")
zi = m.addConstr(2.4 * p + 0.5 * s <= 50, name="zinc")
mn = m.addConstr(0.3 * s <= 50, name="manganese")
pc = m.addConstr(p >= 10)

m.update()
m.tune()
m.optimize()

print('\n\n*** MODEL ***')
print(m)

print('\n\n*** ATTR ***')
m.printAttr('X')

print('\n\n*** VARS ***')
print(m.getVars())

print('\n\n*** CONSTRAINTS ***')
print(m.getConstrs())

print(m.getJSONSolution())
