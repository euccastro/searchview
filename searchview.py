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

class view:
    def __init__(self, window):
        window.push_handlers(self)
        self.history = [obj(vertex_colors=defaultdict(lambda k: 'default'),
                            edge_colors=defaultdict(lambda k: 'default'))]
        self.history_index = -1

    # Command handlers.
    def vertices(self, vertices):
        self._vertices = vertices
    def edges(self, edges):
        self._edges = edges
    def start(self, vertex):
        self.start = self._vertices[vertex]
    def goal(self, vertex):
        self.goal = self._vertices[vertex]
    def iteration_done(self):
        # XXX: update on-screen colors if we are at head.
        self.history.append(
                obj(vertex_colors=self.history[-1].vertex_colors.copy(),
                    edge_colors=self.history[-1].edge_colors.copy()))
    def vertex_color(self, vertex, color):
        self.history[-1].vertex_colors[vertex] = color
    def edge_color(self, edge, color):
        self.history[-1].edge_colors[edge] = color

    # Pyglet event handlers.
    def on_draw(self):


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
    window = pyglet.window.Window()
    view = searchview(window)
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

if __name__ == '__main__':
    run()
