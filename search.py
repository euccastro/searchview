from __future__ import division

from collections import defaultdict
import gc
from heapq import heappush, heappop
from itertools import *
import sys
import time

import prettygraph


solution_color = 'green'
visited_color = 'dark_red'
frontier_color = 'red'

class problem_2d:
    def __init__(self, vertices, edges, start, goal):
        vert_dict = {v.id: v
                     for v in vertices}
        self.connections = defaultdict(list)
        for e1, e2 in edges:
            self.connections[e1].append(vert_dict[e2])
            self.connections[e2].append(vert_dict[e1])
        self.start = vert_dict[start]
        self.goal = vert_dict[goal]
    def start_node(self):
        return node(self.start, None, 0, (self.start - self.goal).length())
    def expand(self, n):
        for v in self.connections[n.state.id]:
            yield node(v, 
                       n, 
                       n.cost + (v - n.state).length(), 
                       (v - self.goal).length())
    def is_goal(self, state):
        return state.id == self.goal.id
    def heuristic_cost(self, node):
        return (node.state - self.goal).length()

class node:
    def __init__(self, state, parent, cost, heuristic_estimate):
        self.state = state
        self.parent = parent
        self.cost = cost
        self.heuristic_estimate = heuristic_estimate

def solution(node):
    ret = []
    while node:
        ret.append(node.state.id)
        node = node.parent
    ret.reverse()
    return ret

def graph_search(add_to_frontier, choose_from_frontier):
    def search(problem, log):
        visited = set()
        frontier = []
        add_to_frontier(frontier, problem.start_node())
        start_time = time.time()
        try:
            while frontier:
                log('step', time.time() - start_time)
                node = choose_from_frontier(frontier)
                if problem.is_goal(node.state):
                    ret = solution(node)
                    log('vertex_color', ret[0], solution_color)
                    for a, b in izip(ret[:-1], ret[1:]):
                        log('vertex_color', b, solution_color)
                        log('edge_color', a, b, solution_color)
                    print "total cost is", node.cost, "length is", len(ret)
                    return ret
                log('vertex_color', node.state.id, visited_color)
                if node.parent:
                    log('edge_color', 
                        node.parent.state.id,
                        node.state.id, 
                        visited_color)
                if node.state not in visited: 
                    visited.add(node.state)
                    for neighbor in problem.expand(node):
                        if neighbor.state not in visited:
                            log('vertex_color', 
                                neighbor.state.id, 
                                frontier_color)
                            log('edge_color',
                                node.state.id,
                                neighbor.state.id,
                                frontier_color)
                            add_to_frontier(frontier, neighbor)
        finally:
            log('step', time.time() - start_time)
    return search

def recursive_depth_limited_search(problem, node, log, depth, color):
    """
    I'm not bothering to distinguish failed searches from those
    that were cut off, since I know that a solution will eventually
    be found in my graph.
    """
    if depth == 0:
        return None
    if problem.is_goal(node.state):
        ret = solution(node)
        log('vertex_color', ret[0], solution_color)
        for a, b in izip(ret[:-1], ret[1:]):
            log('vertex_color', b, solution_color)
            log('edge_color', a, b, solution_color)
        print "total cost is", node.cost, "length is", len(ret)
        return ret
    log("vertex_color", node.state.id, color)
    if node.parent:
        log("edge_color", node.parent.state.id, node.state.id, color)
    for child in problem.expand(node):
        ret = recursive_depth_limited_search(problem, node, log, depth-1, color)
        if ret:
            return ret


def iterative_deepening_df_search(problem, log):
    for depth in xrange(1, 150):
        print "trying depth", depth
        ret = recursive_depth_limited_search(
                problem, 
                problem.start_node(), 
                log,
                depth,
                'red' if depth%2 else 'blue')
        if ret is not None:
            return ret

def path_length(node):
    ret = 0
    while node:
        ret += 1
        node = node.parent
    return ret

breadth_first_search = graph_search(list.append, (lambda l: l.pop(0)))
depth_first_search = graph_search(list.append, list.pop)
def pop_by_priority(frontier):
    priority, node = heappop(frontier)
    return node
def push_by_cost(frontier, node):
    heappush(frontier, (node.cost, node))
uniform_cost_search = graph_search(push_by_cost, pop_by_priority)
def push_by_heuristic(frontier, node):
    heappush(frontier, (node.heuristic_estimate, node))
best_first_search = graph_search(push_by_heuristic, pop_by_priority)
def astar_push(frontier, node):
    heappush(frontier, (node.cost + node.heuristic_estimate, node))
astar_search = graph_search(astar_push, pop_by_priority)

def log_search(search, graph_filename, start, goal, log_filename):
    gc.disable()
    vertices, edges = prettygraph.load_graph(graph_filename)
    problem = problem_2d(vertices, edges, start, goal)
    with file(log_filename, 'w') as log_file:
        def log(*args):
            log_file.write(' '.join(map(str, args))+'\n')
        log('start', start)
        log('goal', goal)
        globals()[search+'_search'](problem, log)

if __name__ == '__main__':
    try:
        search, graph_filename, start, end, log_filename = sys.argv[1:]
    except ValueError:
        print ("Usage: %s <search_algorithm> <graph_filename> "
               "<start> <end> <log_filename>"
               % sys.argv[0])
        sys.exit(1)
    log_search(search, graph_filename, start, end, log_filename)