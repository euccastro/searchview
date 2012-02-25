"""
Usage: searchview.py [<filename>]

Launch a window that will subscribe to and respond to commands from the 0MQ
ipc://searchview.ipc.  A command has the format

    command_name [<argument> ...]

Supported commands are (in the order in which you should invoke them):

    vertices <x0> <y0> [[<x1> <y1>] ...]

        Provide coordinates for vertices, in a syntax supported by Python's
        float() (this includes integers).  The coordinate system doesn't
        matter, as long as it's consistent.  I'll try and map it to the window.

        In any further commands, you can refer to vertices as an index on the
        list you passed.  That is, the index of its x coordinate divided by 2.

        This is probably the first command you need to invoke, since most other
        commands refer to vertices in this list.

    edges <a0> <b0> [[<a1> <b1>] ...]

        Provide connectivity information for the graph.  Each edge is
        represented by two indices referring to its endpoints.  In further
        calls you'll refer to an edge by its index in this list, that is, the
        index of its `a` vertex divided by 2.

    start <vertex>

        Mark the vertex with index `vertex` as the starting position of your
        problem.

    goal <vertex>

        Mark the vertex with index `vertex` as the goal position of your
        problem.

    iteration_done

        Mark the end of an iteration of the loop.  This is the finest 
        granularity that the playback time controls will support.

    vertex_color <vertex> <color>

        Paint the vertex with index `vertex` with the given `color`.  `color`
        is a color name.  See/edit `colors` in the source code to check/edit
        available colors.

    edge_color <edge> <color>

        Paint the edge with index `edge` with the given `color`.   `color`
        is a color name.  See/edit `colors` in the source code to check/edit
        available colors.
"""

from __future__ import division

import os
import sys
from collections import defaultdict
from itertools import *

import pyglet
from pyglet.gl import *

import zmq

from util import obj
from la import vec2

colors = {'white': (1., 1., 1.),
          'grey': (.6, .6, .6),
          'red': (1., .0, .0),
          'green': (.0, 1., .0),
          'blue': (.0, .0, 1.),
          'cyan': (.0, 1., 1.),
          'magenta': (1., .0, 1.),
          'yellow': (1., 1., .0),
          'teal': (.4, .8, .6)}
def to255range(f):
    return int(round(f * 255))
for k, (r, g, b) in colors.items():
    colors[k] = tuple(map(to255range, [r, g, b]))
    if k != "white":
        colors["dark_"+k] = tuple(map(to255range, [r/2, g/2, b/2]))
colors['default'] = colors['grey']

def flatten_vec2s(vs):
    return list(chain.from_iterable(vs))

class view:

    def __init__(self):
        self.history = [obj(vertex_colors=defaultdict(lambda k: 'default'),
                            edge_colors=defaultdict(lambda k: 'default'))]
        self.play_position = -1
        self.color_buffers_dirty = True

    def create_window(self):
        w = pyglet.window.Window(resizable=True)
        w.push_handlers(self)

    def on_resize(self, width, height):
        print "on_resize", width, height
        margin = .1  # at each border
        min_ = self._vertices[0].copy()
        max_ = self._vertices[0].copy()
        for v in self._vertices:
            if v.x < min_.x:
                min_.x = v.x
            elif v.x > max_.x:
                max_.x = v.x
            if v.y < min_.y:
                min_.y = v.y
            elif v.y > max_.y:
                max_.y = v.y
        range_ = max_ - min_

        ww = width * (1 - margin * 2)
        wh = height * (1 - margin * 2)

        ratio = vec2(range_.x / ww, range_.y / wh)
        
        if ratio.x < ratio.y:
            # We are limited by vertical height (most common case).
            view_height = range_.y * (1 + margin * 2)
            pixels_per_world_unit = height / view_height
        else:
            view_width = range_.x * (1 + margin * 2)
            pixels_per_world_unit = width / view_width

        world_center = vec2(range_.x / 2, range_.y / 2)

        screen_size_in_world_units = (
                vec2(width, height) / pixels_per_world_unit)
        left, bottom = world_center - screen_size_in_world_units / 2
        right, top = world_center + screen_size_in_world_units / 2
        print "left", left, "bottom", bottom, "right", right, "top", top
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(left, right, bottom, top, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        return pyglet.event.EVENT_HANDLED

    # Command handlers.
    def vertices(self, vertices):
        self._vertices = vertices
        length = len(vertices) 
        print "flattened", flatten_vec2s(vertices)
        self.history[-1].vertices = pyglet.graphics.vertex_list(
                length,
                ('v2f/static', flatten_vec2s(vertices)),
                ('c3b/stream', [128] * length * 3))

    def edges(self, edges):
        # XXX: I'm structuring the data only to destructure it later.
        #      It is cleaner in some way, but if this is any performance
        #      concern at all, I may want to just use flat list throughout.
        flattened = flatten_vec2s(self._vertices[v]
                                  for v in chain.from_iterable(edges))
        length = len(edges) * 2
        self.history[-1].edges = pyglet.graphics.vertex_list(
                length,
                ('v2f/static', flattened),
                ('c3b/stream', [128] * length * 3))
        self.create_window()
    def start(self, vertex):
        self.start = self._vertices[vertex]
    def goal(self, vertex):
        self.goal = self._vertices[vertex]
    def iteration_done(self):
        # XXX: update on-screen colors if we are at head.
        self.history.append(
                obj(vertex_colors=self.history[-1].vertex_colors.copy(),
                    edge_colors=self.history[-1].edge_colors.copy()),
                    dirty=True)
    def vertex_color(self, vertex, color):
        self.history[-1].vertex_colors[vertex*3:vertex*3+3] = colors[color]
    def edge_color(self, edge, color):
        self.history[-1].edge_colors[edge*6:edge*6+6] = colors[color] * 2

    # Pyglet event handlers.
    def on_draw(self):
        # XXX: dirty handlers.
        glPointSize(3)
        glClearColor(.5, .5, .5, 1.)
        glColor3f(1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        current = self.history[self.play_position]
        current.vertices.draw(GL_POINTS)
        current.edges.draw(GL_LINES)

class interpreter:

    def __init__(self, view):
        self.view = view

    def vertices(self, *lst):
        self.view.vertices(vec2(x, y)
                           for x, y in izip(islice(lst, 0, None, 2),
                                            islice(lst, 1, None, 2)))
    def edges(self, *lst):
        self.view.edges((int(a), int(b))
                         for a, b in izip(islice(lst, 0, None, 2),
                                          islice(lst, 1, None, 2)))
    def start(self, vertex):
        self.view.start(int(vertex))

    def goal(self, vertex):
        self.view.end(int(vertex))

    def iteration_done(self):
        self.view.iteration_done()

    def vertex_color(self, vertex, color):
        self.view.vertex_color(int(vertex), color)

    def edge_color(self, edge, color):
        self.view.edge_color(int(edge), color)


def run():
    socket = zmq.socket(zmq.PULL)
    # XXX: full screen for demo.
    view = searchview()
    it = interpreter(view)
    # XXX: do something about collisions from more than one running 
    #      client/server pair.
    socket.setsockopt(zmq.SUBSCRIBE, '')
    socket.bind('ipc:///tmp/searchview.ipc')
    def handle_commands(*blah):
        while True:
            try:
                cmd_line = socket.recv(zmq.NOBLOCK)
                cmd, args = cmd_line.split(1)
                getattr(it, cmd)(*args.split())
            except zmq.ZMQError:
                return
    pyglet.clock.schedule_interval(1/30, handle_commands)
    pyglet.app.run()

def test():
    v = view()
    v.vertices([vec2(0,0), vec2(1, 0), vec2(0, 1), vec2(1,1)])
    v.edges([(0, 1), (1, 3), (1, 2)])
    pyglet.app.run()

if __name__ == '__main__':
    test()
