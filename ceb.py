"""
Graph editor.

To start with, you get a screen with only two vertices, the `start` vertex
(marked with a right-facing triangle -- think of a 'Play' button) and the `end`
vertex (marked with a tall rectangle -- think an end-of-proof/tombstone/Halmos mark).

In general, actions affect the element closest to the mouse pointer. 

Right click to add vertices, drag with left mouse button to move them, and drag with middle mouse button to create an edge connecting two vertices.

Press Delete to delete the vertex closest to mouse cursor.  Press Backspace to delete the edge the midpoint of which is closest to the mouse cursor.
"""

from __future__ import division

from heapq import heappush, heappop

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

start = vec2(w.width // 3, w.height // 3)
goal = vec2((w.width * 2) // 3, (w.height * 2) // 3)

vertices = [start, goal]

start_poly = [vec2(x, y) for x, y in (-5, -8), (8, 0), (-5, 8)]
goal_poly = [vec2(x, y) for x, y in (-4, -8), (4, -8), (4, 8), (-4, 8)]

edges = []

mouse_pos = None
closest = None
origin = None
target = None
optimal_path = None
search_obsolete = False

@w.event
def on_mouse_motion(x, y, *etc):
    global mouse_pos
    mouse_pos = vec2(x, y)
    ch.send(obj(type='motion', pos=vec2(x,y)))

@w.event
def on_mouse_press(x, y, button, *etc):
    ch.send(obj(type='press', pos=vec2(x, y), button=button))

@w.event
def on_mouse_drag(x, y, *etc):
    global mouse_pos
    mouse_pos = vec2(x, y)
    ch.send(obj(type='motion', pos=vec2(x, y)))

@w.event
def on_mouse_release(x, y, button, *etc):
    ch.send(obj(type='release', pos=vec2(x, y), button=button))

@w.event
def on_key_press(k, *etc):
    ch.send(obj(type='key', key=k))

@w.event
def on_draw():

    global search_obsolete
    if search_obsolete:
        update_search()
        search_obsolete = False

    glClear(GL_COLOR_BUFFER_BIT)
    glColor3f(*colors['cyan'])
    for point, poly in (start, start_poly), (goal, goal_poly):
        glBegin(GL_LINE_LOOP)
        for vertex in poly:
            glVertex2f(*point+vertex)
        glEnd()
    glBegin(GL_LINES)
    for v1, v2 in edges:
        glVertex2f(*v1)
        glVertex2f(*v2)
    if origin and target:
        glColor3f(*colors['teal'])
        glVertex2f(*origin)
        glVertex2f(*target)
    glEnd()
    if optimal_path is not None:
        glColor3f(*colors['green'])
        glBegin(GL_LINE_STRIP)
        for v in optimal_path:
            glVertex2f(*v)
        glEnd()
    glBegin(GL_POINTS)
    for v in vertices:
        if v is target:
            color = 'red'
        elif v is origin:
            color = 'green'
        elif v is closest:
            color = 'yellow'
        else:
            color = 'blue'
        glColor3f(*colors[color])
        glVertex2f(*v)
    glEnd()

def run():
    global closest
    global origin
    global target
    global search_obsolete
    while True:
        evt = ch.receive()
        if evt.type == 'motion':
            closest = closest_vertex(evt.pos)
        elif evt.type == 'press':
            if evt.button == mouse.RIGHT:
                vertices.append(evt.pos)
            elif evt.button == mouse.LEFT:
                closest = closest_vertex(evt.pos)
                init_pos = closest.copy()
                while True:
                    newevt = ch.receive()
                    if newevt.type == 'motion':
                        closest.become(init_pos + newevt.pos - evt.pos)
                    elif newevt.type == 'release':
                        search_obsolete = True
                        break
            elif evt.button == mouse.MIDDLE:
                origin = closest_vertex(evt.pos)
                while True:
                    newevt = ch.receive()
                    # Press any button to cancel.
                    if newevt.type == 'press':
                        break
                    elif (newevt.type == 'release' 
                          and newevt.button == mouse.MIDDLE):
                        vcopy = vertices[:]
                        vcopy.remove(origin)
                        dest = closest_vertex(newevt.pos, vcopy)
                        add_edge(origin, dest)
                        break
                    elif newevt.type == 'motion':
                        vcopy = vertices[:]
                        vcopy.remove(origin)
                        target = closest_vertex(newevt.pos, vcopy)
                origin = target = None
        elif evt.type == 'key':
            if evt.key == key.DELETE:
                if closest not in [start, goal, None]:
                    vertices.remove(closest)
                    for a, b in edges[:]:
                        if a is closest or b is closest:
                            remove_edge(a, b)
                    closest = None
            elif evt.key == key.BACKSPACE:
                if mouse_pos is not None:
                    d = dict([((a+b)/2, (a, b)) for a, b in edges])
                    closest_midpoint = closest_vertex(mouse_pos, d.keys())
                    remove_edge(*d[closest_midpoint])

def add_edge(a, b):
    global search_obsolete
    search_obsolete = True
    edges.append((a, b))

def remove_edge(a, b):
    global search_obsolete
    search_obsolete = True
    edges.remove((a, b))

def update_search():
    global optimal_path
    optimal_path = astar()

def closest_vertex(p, vertices=vertices):
    return min(vertices, key=(lambda v: squaredist(v, p)))

ch = stackless.channel()

colors = {'blue': (.0, .0, 1.),
          'yellow': (1., 1., .0),
          'green': (.0, 1., .0),
          'red': (1., .0, .0),
          'teal': (.4, .8, .6),
          'cyan': (.0, .7, .7)}

def astar():
    visited = set()
    frontier = [(0, 0, [start])]
    while frontier:
        heuristic, cost, path = heappop(frontier)
        last = path[-1]
        if last is goal:
            return path
        if last in visited:
            continue
        visited.add(last)
        for a, b in edges:
            if b is last:
                a, b = b, a
            if a is last and b not in visited:
                new_cost = cost + (a-b).length()
                estimate_to_goal = (goal-b).length()
                heappush(frontier, 
                         (new_cost+estimate_to_goal, 
                          new_cost, 
                          path + [b]))

glClearColor(.5, .5, .5, 1.)
glPointSize(4)

stackless.tasklet(run)()
stackless.tasklet(pyglet.app.run)()
stackless.run()
