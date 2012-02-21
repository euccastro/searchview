"""
Graph editor.

To start with, you get a screen with only two vertices, the `start` vertex
(marked with a right-facing triangle -- think of a 'Play' button) and the `end`
vertex (marked with a tall rectangle -- think an end-of-proof/tombstone/Halmos mark).

In general, actions affect the element closest to the mouse pointer. 

Right click to add vertices, drag with left mouse button to move them, and drag with middle mouse button to create an edge connecting two vertices.

Press Delete to delete the vertex closest to mouse cursor.  Press Backspace to delete the edge the midpoint of which is closest to the mouse cursor.
"""

#XXX: make an actual App class!

from __future__ import division

from heapq import heappush, heappop
import pickle
import sys

import stackless

import pyglet
from pyglet.window import mouse, key
from pyglet.gl import *

from la import vec2
from util import obj


w = pyglet.window.Window()


def squaredist(v1, v2):
    dx = v1.x - v2.x
    dy = v1.y - v2.y
    return dx * dx + dy * dy

class edge:
    def __init__(self, endpoint1, endpoint2):
        self.endpoints = endpoint1, endpoint2


start_poly = [vec2(x, y) for x, y in (-5, -8), (8, 0), (-5, 8)]
goal_poly = [vec2(x, y) for x, y in (-4, -8), (4, -8), (4, 8), (-4, 8)]


# App state.

def app_state(start, goal):
    return obj(start=start,
               goal=goal,
               vertices=[start, goal],
               edges=[],
               mouse_pos=None,
               closest=None,
               origin=None,
               target=None,
               optimal_path=None,
               bidi_path=None,
               bidi_meeting_point=None,
               search_obsolete=False)

@w.event
def on_mouse_motion(x, y, *etc):
    aps.mouse_pos = vec2(x, y)
    ch.send(obj(type='motion', pos=vec2(x,y)))

@w.event
def on_mouse_press(x, y, button, *etc):
    ch.send(obj(type='press', pos=vec2(x, y), button=button))

@w.event
def on_mouse_drag(x, y, *etc):
    aps.mouse_pos = vec2(x, y)
    ch.send(obj(type='motion', pos=vec2(x, y)))

@w.event
def on_mouse_release(x, y, button, *etc):
    ch.send(obj(type='release', pos=vec2(x, y), button=button))

@w.event
def on_key_press(k, *etc):
    ch.send(obj(type='key', key=k))

@w.event
def on_draw():

    if aps.search_obsolete:
        update_search()
        aps.search_obsolete = False

    glClear(GL_COLOR_BUFFER_BIT)
    glColor3f(*colors['cyan'])
    for point, poly in (aps.start, start_poly), (aps.goal, goal_poly):
        glBegin(GL_LINE_LOOP)
        for vertex in poly:
            glVertex2f(*point+vertex)
        glEnd()
    glBegin(GL_LINES)
    for v1, v2 in aps.edges:
        glVertex2f(*v1)
        glVertex2f(*v2)
    if aps.origin and aps.target:
        glColor3f(*colors['teal'])
        glVertex2f(*aps.origin)
        glVertex2f(*aps.target)
    glEnd()

    for path, color, offset in [(aps.bidi_path, 'purple', -1),
                                (aps.optimal_path, 'green', +1)]:
        if path is not None:
            glColor3f(*colors[color])
            glBegin(GL_LINE_STRIP)
            for v in path:
                glVertex2f(v.x + offset, v.y + offset)
            glEnd()

    glBegin(GL_POINTS)
    for v in aps.vertices:
        if v is aps.target:
            color = 'red'
        elif v is aps.origin:
            color = 'green'
        elif v is aps.closest:
            color = 'yellow'
        elif v is aps.bidi_meeting_point:
            color = 'purple'
        else:
            color = 'blue'
        glColor3f(*colors[color])
        glVertex2f(*v)
    glEnd()

def run():
    while True:
        evt = ch.receive()
        if evt.type == 'motion':
            aps.closest = closest_vertex(evt.pos)
        elif evt.type == 'press':
            if evt.button == mouse.RIGHT:
                aps.vertices.append(evt.pos)
            elif evt.button == mouse.LEFT:
                aps.closest = closest_vertex(evt.pos)
                init_pos = aps.closest.copy()
                while True:
                    newevt = ch.receive()
                    if newevt.type == 'motion':
                        aps.closest.become(init_pos + newevt.pos - evt.pos)
                    elif newevt.type == 'release':
                        aps.search_obsolete = True
                        break
            elif evt.button == mouse.MIDDLE:
                aps.origin = closest_vertex(evt.pos)
                while True:
                    newevt = ch.receive()
                    # Press any button to cancel.
                    if newevt.type == 'press':
                        break
                    elif (newevt.type == 'release' 
                          and newevt.button == mouse.MIDDLE):
                        vcopy = aps.vertices[:]
                        vcopy.remove(aps.origin)
                        dest = closest_vertex(newevt.pos, vcopy)
                        add_edge(aps.origin, dest)
                        break
                    elif newevt.type == 'motion':
                        vcopy = aps.vertices[:]
                        vcopy.remove(aps.origin)
                        aps.target = closest_vertex(newevt.pos, vcopy)
                aps.origin = aps.target = None
        elif evt.type == 'key':
            if evt.key == key.DELETE:
                if aps.closest not in [aps.start, aps.goal, None]:
                    aps.vertices.remove(aps.closest)
                    for a, b in aps.edges[:]:
                        if a is aps.closest or b is aps.closest:
                            remove_edge(a, b)
                    aps.closest = None
            elif evt.key == key.BACKSPACE:
                if aps.mouse_pos is not None:
                    d = dict([((a+b)/2, (a, b)) for a, b in aps.edges])
                    closest_midpoint = closest_vertex(aps.mouse_pos, d.keys())
                    remove_edge(*d[closest_midpoint])
            elif evt.key == key.RETURN:
                save_network("save.net")

def save_network(filename):
    sv = dict((id(v), (v.x, v.y)) for v in aps.vertices)
    se = [(id(a), id(b)) for a, b in aps.edges]
    pickle.dump(dict(start=id(aps.start),
                     goal=id(aps.goal),
                     vertices=sv,
                     edges=se),
                file(filename, 'w'))

def load_network(filename):
    raise NotImplementedError


def add_edge(a, b):
    aps.search_obsolete = True
    aps.edges.append((a, b))

def remove_edge(a, b):
    aps.search_obsolete = True
    aps.edges.remove((a, b))

def update_search():
    aps.optimal_path = astar()
    aps.bidi_path, aps.bidi_meeting_point = bidirectional_astar()
    if (aps.optimal_path and aps.bidi_path
        and len(aps.bidi_path) > len(aps.optimal_path)):
        print "FOUND A SOLUTION!"
        try:
            save_network("counterexample.net")
        except:
            print "Some error while trying to save this counterexample."
            print "You may want to take a screenshot at least!."

def closest_vertex(p, vertices=None):
    if vertices is None:
        vertices = aps.vertices
    return min(vertices, key=(lambda v: squaredist(v, p)))

ch = stackless.channel()

colors = {'blue': (.0, .0, 1.),
          'yellow': (1., 1., .0),
          'green': (.0, 1., .0),
          'red': (1., .0, .0),
          'teal': (.4, .8, .6),
          'cyan': (.0, .7, .7),
          'purple': (1., .0, 1.)}

def astar():
    visited = set()
    frontier = [(0, 0, [aps.start])]
    while frontier:
        heuristic, cost, path = heappop(frontier)
        last = path[-1]
        if last is aps.goal:
            return path
        if last in visited:
            continue
        visited.add(last)
        for a, b in aps.edges:
            if b is last:
                a, b = b, a
            if a is last and b not in visited:
                new_cost = cost + (a-b).length()
                estimate_to_goal = (aps.goal-b).length()
                heappush(frontier, 
                         (new_cost+estimate_to_goal, 
                          new_cost, 
                          path + [b]))

class search_state:
    def __init__(self, start, goal):
        self.visited = set()
        # Estimated cost, cost so far, chain, contact.
        #
        # I pick a list for contact to make it mutable and easy to check 
        # for (non)emptiness.
        self.frontier = [(0, 0, [start], [])]
        self.goal = goal
        
def bidirectional_astar():
    """
    This version returns a (path, contact_point) pair.
    """
    searches = [search_state(aps.start, aps.goal),
                search_state(aps.goal, aps.start)]
    while all(s.frontier for s in searches):
        for search, other in searches, reversed(searches):
            heuristic, cost, path, contact = heappop(search.frontier)
            last = path[-1]
            if last in search.visited:
                continue
            search.visited.add(last)
            if contact:
                sol_path = path[:-1] + list(reversed(contact[0]))
                if search.goal is aps.start:
                    sol_path.reverse()
                return sol_path, last
            for h, c, other_path, other_contact in other.frontier:
                if other_path[-1] == last:
                    other_contact.append(path)
            for a, b in aps.edges:
                if b is last:
                    a, b = b, a
                if a is last and b not in search.visited:
                    new_cost = cost + (a-b).length()
                    estimate_to_goal = (search.goal-b).length()
                    heappush(search.frontier, 
                             (new_cost+estimate_to_goal, 
                              new_cost, 
                              path + [b],
                              []))
    return None, None

                         
glClearColor(.5, .5, .5, 1.)
glPointSize(4)

usage = "Usage: %s [<path_of_saved_network>]"

if len(sys.argv) == 1:
    aps = app_state(start=vec2(w.width // 3, w.height // 3),
                    goal=vec2((w.width * 2) // 3, (w.height * 2) // 3))
elif len(sys.argv) == 2:
    try:
        aps = load_network(sys.argv[1])
    except:
        print usage
        raise
else:
    print usage
    sys.exit(1)

stackless.tasklet(run)()
stackless.tasklet(pyglet.app.run)()
stackless.run()
