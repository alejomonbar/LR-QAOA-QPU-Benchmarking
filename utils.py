import numpy as np
import networkx as nx
from docplex.mp.model import Model

def wmaxcut_docplex(G):
    # Weighted maxcut problem from networkx graph model as a QUBO problem
    mdl = Model('MaxCut')
    num_vertices = G.number_of_nodes()
    translate = {j:i for i, j in enumerate(sorted(G.nodes))}
    x = {i: mdl.binary_var(name=f"x_{i}") for i in range(num_vertices)}
    mdl.minimize(-mdl.sum(G[i][j]["weight"]*(x[translate[i]] * (1 - x[translate[j]]) + x[translate[j]] * (1 - x[translate[i]]))  for (i, j) in G.edges))
    return mdl