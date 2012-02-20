# First version: just add, remove and drag points and edges around.

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
end = vec2((w.width * 2) // 3, (w.height * 2) // 3)

vertices = [start, end]

start_poly = [vec2(x, y) for x, y in (-6, -10), (12, 0), (-6, 10)]
end_poly = [vec2(x, y) for x, y in (-6, -6), (6, -6), (6, 6), (-6, 6)]

edges = []

closest = None
origin = None
target = None

@w.event
def on_mouse_motion(x, y, *etc):
    ch.send(obj(type='motion', pos=vec2(x,y)))

@w.event
def on_mouse_press(x, y, button, *etc):
    ch.send(obj(type='press', pos=vec2(x, y), button=button))

@w.event
def on_mouse_drag(x, y, *etc):
    ch.send(obj(type='motion', pos=vec2(x, y)))

@w.event
def on_mouse_release(x, y, button, *etc):
    ch.send(obj(type='release', pos=vec2(x, y), button=button))

@w.event
def on_key_press(k, *etc):
    ch.send(obj(type='key', key=k))

@w.event
def on_draw():
    glClear(GL_COLOR_BUFFER_BIT)
    glColor3f(*colors['cyan'])
    for point, poly in (start, start_poly), (end, end_poly):
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
                        edges.append((origin, dest))
                        break
                    elif newevt.type == 'motion':
                        vcopy = vertices[:]
                        vcopy.remove(origin)
                        target = closest_vertex(newevt.pos, vcopy)
                origin = target = None

def closest_vertex(p, vertices=vertices):
    return min(vertices, key=(lambda v: squaredist(v, p)))

ch = stackless.channel()

colors = {'blue': (.0, .0, 1.),
          'yellow': (1., 1., .0),
          'green': (.0, 1., .0),
          'red': (1., .0, .0),
          'teal': (.4, .8, .6),
          'cyan': (.0, .7, .7)}

glClearColor(.5, .5, .5, 1.)
glPointSize(4)

stackless.tasklet(run)()
stackless.tasklet(pyglet.app.run)()
stackless.run()
