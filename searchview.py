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

    def __init__(self, vertices, color_history):
        self.vertices = vertices
        self.history = color_history
        self.play_position = 0
        w = pyglet.window.Window(resizable=True)
        w.push_handlers(self)

    def on_resize(self, width, height):
        print "on_resize", width, height
        margin = .1  # at each border
        min_ = self.vertices[0].copy()
        max_ = self.vertices[0].copy()
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
        self.vertex_buffer = pyglet.graphics.vertex_list(
                length,
                ('v2f/static', flatten_vec2s(vertices)),
                ('c3B/stream', [128] * length * 3))
        self.history[-1].vertex_colors = self.vertex_buffer.colors 
        
    def edges(self, edges):
        # XXX: I'm structuring the data only to destructure it later.
        #      It is cleaner in some way, but if this is any performance
        #      concern at all, I may want to just use flat list throughout.
        flattened = flatten_vec2s(self._vertices[v]
                                  for v in chain.from_iterable(edges))
        length = len(edges) * 2
        self.edge_buffer = pyglet.graphics.vertex_list(
                length,
                ('v2f/static', flattened),
                ('c3B/stream', [128] * length * 3))
        self.history[-1].edge_colors = self.edge_buffer.colors
        self.create_window()
    def start(self, vertex):
        self.start = self._vertices[vertex]
    def goal(self, vertex):
        self.goal = self._vertices[vertex]
    def iteration_done(self):
        # XXX: update on-screen colors if we are at head.
        vcolors = copy_buffer(self.history[-1].vertex_colors)
            
        self.history.append(
                obj(vertex_colors=copy_buffer(self.history[-1].vertex_colors),
                    edge_colors=copy_buffer(self.history[-1].edge_colors),
                    dirty=True))
    def vertex_color(self, vertex, color):
        self.history[-1].vertex_colors[vertex*3:vertex*3+3] = colors[color]
    def edge_color(self, edge, color):
        self.history[-1].edge_colors[edge*6:edge*6+6] = colors[color] * 2

    # Pyglet event handlers.
    def on_draw(self):
        # XXX: dirty handlers.
        glPointSize(3)
        glClearColor(.2, .2, .2, 1.)
        glClear(GL_COLOR_BUFFER_BIT)
        current = self.history[self.play_position]
        current.vertices.draw(GL_POINTS)
        current.edges.draw(GL_LINES)

def parse_commands(command_lines):
    """
    Parse commands and return a tuple with the following elements:
        vertices
            A ctypes array of vertices in v2f format.
        edges
            A ctypes array of vertices in v2f format, ready to pass to
            GL_LINES.
        start
            The vertex corresponding to the starting position, as an index
            into the vertices array.
        goal
            The vertex corresponting to the ending position, as an index
            into the vertices array.
        color_history
            A list of `obj`s where each of them has the attributes:
                time
                    Time in seconds from start of search.
                vertex_colors
                    A ctypes array of colors in c3B format, corresponding to
                    the vertices.
                edge_colors
                    A ctypes array of colors in c3B format, corresponding to
                    the edges.
    """
    vertices = None
    edges = None
    start = None
    goal = None
    color_history = [obj()]
    for line in command_lines:
        print "line si", repr(line)
        if not line.strip():
            continue
        cmd, args = line.strip().split(None, 1)
        args = args.split()
        if cmd == 'vertices':
            vertices = (c_float * len(args))(*imap(float, args))
            assert even(len(args))
            len_colors = len(args) * 3 // 2
            color_history[0].vertex_colors = (c_ubyte * len_colors)(
                *repeat(colors['default'][0], len_colors))
        elif cmd == 'edges':
            assert vertices is not None
            assert len(args) % 2 == 0
            edges = (c_float * (len(args) * 2))(
                    *chain.from_iterable((vertices[int(i)*2], 
                                          vertices[int(i)*2 + 1])
                                         for i in args))
            assert even(len(edges))
            len_colors = len(edges) * 3 // 2
            color_history[0].edge_colors = (c_ubyte * len_colors)(
                    *repeat(colors['default'][0], len_colors))
        elif cmd == 'start':
            assert vertices is not None
            index = int(args[0])
            start = vertices[index * 2], vertices[index * 2 + 1]
        elif cmd == 'goal':
            assert vertices is not None
            index = int(args[0])
            goal = vertices[index * 2], vertices[index * 2 + 1]
        elif cmd == 'step':
            assert None not in [vertices, edges]
            timestamp = float(args[0])
            color_history.append(
                obj(time=timestamp,
                    vertex_colors=copy_array(color_history[-1].vertex_colors),
                    edge_colors=copy_array(color_history[-1].edge_colors)))
        elif cmd == 'vertex_color':
            index, color_name = args
            index = int(index)
            color_history[-1].vertex_colors[index*3:index*3+3] = \
                    colors[color_name]
        elif cmd == 'edge_color':
            index, color_name = args
            index = int(index)
            color_history[-1].edge_colors[index*6:index*6+6] = \
                    colors[color_name] * 2
    assert None not in [vertices, edges, start, goal]
    return vertices, edges, start, goal, color_history

def even(x):
    return not (x & 1)

def copy_array(a):
    ret = (c_ubyte * len(a))()
    memmove(ret, a, len(a))
    return ret

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

#def test():
#    v = view()
#    v.vertices([vec2(0,0), vec2(1, 0), vec2(0, 1), vec2(1,1)])
#    v.edges([(0, 1), (1, 3), (1, 2)])
#    v.edge_color(1, 'yellow')
#    pyglet.app.run()
#
def test2():
    cmds = """
vertices 100 100 200 100 200 200 100 200
edges 0 1 1 2 1 3
start 0
goal 2
step 0
vertex_color 0 yellow
step 1
vertex_color 1 yellow
edge_color 0 yellow
""".strip().split("\n")
    print parse_commands(cmds)

if __name__ == '__main__':
    test2()
