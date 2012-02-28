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

    def __init__(self, vertices, edges, start, goal, color_history):
        self.vertices = vertices
        self.start = start
        self.goal = goal
        self.history = color_history
        self.play_position = 0
        self.vertex_buffer = pyglet.graphics.vertex_list(
                len(vertices) // 2, 'v2f/static', 'c3B/stream')
        self.edge_buffer = pyglet.graphics.vertex_list(
                len(edges) // 2, 'v2f/static', 'c3B/stream')
        copy_buffer(self.vertex_buffer.vertices, self.vertices)
        copy_buffer(self.vertex_buffer.colors, self.history[0].vertex_colors)
        copy_buffer(self.edge_buffer.vertices, edges)
        copy_buffer(self.edge_buffer.colors, self.history[0].edge_colors)
        w = pyglet.window.Window(resizable=True)
        w.push_handlers(self)
        glPointSize(3)
        glClearColor(.2, .2, .2, 1.)

    # Pyglet event handlers.

    def on_resize(self, width, height):

        "Fit graph to screen, with some margin."
        
        margin = .1  # at each border

        x = self.vertices[0]
        y = self.vertices[1]
        min_ = vec2(x, y)
        max_ = vec2(x, y)
        for x in islice(self.vertices, 0, None, 2):
            if x < min_.x:
                min_.x = x
            if x > max_.x:
                max_.x = x
        for y in islice(self.vertices, 1, None, 2):
            if y < min_.y:
                min_.y = y
            if y > max_.y:
                max_.y = y

        range_ = max_ - min_

        ww = width * (1 - margin * 2)
        wh = height * (1 - margin * 2)

        # Aspect is larger if something is wider in relation to its height.
        world_aspect = range_.x / range_.y
        screen_aspect = ww / wh
        
        if world_aspect < screen_aspect:
            # We are limited by vertical height (most common case).
            pixels_per_world_unit = wh / range_.y
        else:
            pixels_per_world_unit = ww / range_.x

        world_center = vec2((min_.x + max_.x) / 2, (min_.y + max_.y) / 2)

        screen_size_in_world_units = (
                vec2(width, height) / pixels_per_world_unit)
        left, bottom = world_center - screen_size_in_world_units / 2
        right, top = world_center + screen_size_in_world_units / 2

        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(left, right, bottom, top, -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        return pyglet.event.EVENT_HANDLED

    def on_draw(self):
        glClear(GL_COLOR_BUFFER_BIT)
        self.vertex_buffer.draw(GL_POINTS)
        self.edge_buffer.draw(GL_LINES)

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
                    vertex_colors=clone_array(color_history[-1].vertex_colors),
                    edge_colors=clone_array(color_history[-1].edge_colors)))
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

def clone_array(a):
    ret = (c_ubyte * len(a))()
    copy_buffer(ret, a)
    return ret

def copy_buffer(dst, src):
    memmove(dst, src, sizeof(dst))

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
    v = view(*parse_commands(cmds))
    pyglet.app.run()

if __name__ == '__main__':
    test2()
