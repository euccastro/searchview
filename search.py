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
    def goal_node(self):
        return node(self.goal, None, 0, (self.start - self.goal).length())
    def expand(self, n, goal=None):
        goal = goal or self.goal
        for v in self.connections[n.state.id]:
            yield node(v, 
                       n, 
                       n.cost + (v - n.state).length(), 
                       (v - goal).length())
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
                    log_solution(ret, log)
                    print "total cost is", node.cost
                    print "length is", len(ret)
                    return ret
                log('vertex_color', node.state.id, visited_color)
                if node.parent:
                    log('edge_color', 
                        node.parent.state.id,
                        node.state.id, 
                        visited_color)
                if node.state.id not in visited: 
                    visited.add(node.state.id)
                    for neighbor in problem.expand(node):
                        if neighbor.state.id not in visited:
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
            print "Visited", len(visited), "nodes."
    return search

def log_solution(solution, log):
    log('vertex_color', solution[0], solution_color)
    for a, b in izip(solution[:-1], solution[1:]):
        log('vertex_color', b, solution_color)
        log('edge_color', a, b, solution_color)

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

class search_state:
    def __init__(self, start, goal, color):
        self.frontier = [(0, start)]
        self.goal = goal
        self.frontier_color = color
        self.visited_color = 'dark_' + color

def bidirectional_astar_search(problem, log):
    start = problem.start_node()
    goal = problem.goal_node()
    searches = [search_state(start, goal, 'red'),
                search_state(goal, start, 'blue')]
    best_path_cost = sys.maxint
    best_path = None
    start_time = time.time()
    visited = set()
    while searches[0].frontier and searches[1].frontier:
        for search, other in searches, reversed(searches):
            log('step', time.time() - start_time)
            estimate, node = heappop(search.frontier)
            log('vertex_color', node.state.id, search.visited_color)
            if node.parent:
                log('edge_color', 
                    node.parent.state.id,
                    node.state.id,
                    search.visited_color)
            if node.state.id in visited or estimate > best_path_cost:
                continue
            visited.add(node.state.id)
            for blah, other_node in other.frontier:
                if other_node.state.id == node.state.id:
                    log('vertex_color', node.state.id, 'yellow')
                    cost = node.cost + other_node.cost
                    if cost < best_path_cost:
                        #import pdb
                        #pdb.set_trace()
                        best_path = node, other_node
                        best_path_cost = cost
                        print "best path cost becomes", best_path_cost
                    break
            else:
                for child in problem.expand(node, search.goal.state):
                    estimate = child.cost + child.heuristic_estimate
                    if (estimate < best_path_cost
                        and child.state.id not in visited):
                        log('vertex_color', child.state.id, search.frontier_color)
                        log('edge_color',
                            node.state.id, 
                            child.state.id, 
                            search.frontier_color)
                        heappush(search.frontier, 
                                 (estimate, child))
    log('step', time.time() - start_time)
    if best_path is None:
        return None
    else:
        a, b = best_path
      
        ret = solution(a)[:-1] + list(reversed(solution(b)))
        if ret[0] != start.state.id:
            ret.reverse()
        log_solution(ret, log)
        print "total cost", a.cost + b.cost
        print "length is", len(ret)
        print "visited", len(visited), "nodes."
        return ret

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
