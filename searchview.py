"""
Launch a window that will read commands from standard input and display the
search history they represent.

Each command has the form:

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

    step <timestamp>

        Mark the start of a new 'step' in the search.  A step is the smallest
        granularity that the playback time controls will support.  Timestamp
        is in seconds from beginning of search.  It may be used to replay a
        search in a time frame proportional to that in which the search took
        place.

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

from itertools import *
import os
import stackless
import sys

import pyglet
from pyglet.window import key
from pyglet.gl import *
import yaml

from util import obj
import ui
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

class view(ui.window):

    def __init__(self, **kw):
        history = kw.pop('history')
        ui.window.__init__(self, **kw)
        vertices, edges, start, goal, color_history = \
                parse_commands(file(history))
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

    def world_extents(self):
        if not hasattr(self, '_world_extents'):
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
            self._world_extents = min_, max_
        return self._world_extents

    def layout_children(self):
        "Fit graph to screen, with some margin."

        ui.window.layout_children(self)

        window_rect = self.absolute_rect = self.find_absolute_rect()
        
        min_, max_ = self.world_extents()

        range_ = max_ - min_

        margin = .1  # at each border

        ww = window_rect.width * (1 - margin * 2)
        wh = window_rect.height * (1 - margin * 2)

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
                vec2(window_rect.width, window_rect.height) 
                / pixels_per_world_unit)

        wleft, wbottom = (world_center - screen_size_in_world_units / 2)
        wwidth, wheight = screen_size_in_world_units
        self.world_rect = ui.rect(wleft, wbottom, wwidth, wheight)

    def on_key_press(self, k, *etc):
        def update_buffers():
            current = self.history[self.play_position]
            copy_buffer(self.vertex_buffer.colors, current.vertex_colors)
            copy_buffer(self.edge_buffer.colors, current.edge_colors)
        if k == key.LEFT and self.play_position > 0:
            self.play_position -= 1
            update_buffers()
        elif k == key.RIGHT and self.play_position < len(self.history) - 1:
            self.play_position += 1
            update_buffers()

    def draw(self):
        glPushAttrib(GL_VIEWPORT_BIT)
        glViewport(self.absolute_rect.left,
                   self.absolute_rect.bottom, 
                   self.absolute_rect.width, 
                   self.absolute_rect.height)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(self.world_rect.left, 
                self.world_rect.right, 
                self.world_rect.bottom, 
                self.world_rect.top, 
                -1.0, 
                1.0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        self.vertex_buffer.draw(GL_POINTS)
        self.edge_buffer.draw(GL_LINES)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glPopAttrib()
        glMatrixMode(GL_MODELVIEW)


class control(ui.window):

    def __init__(self, **kw):
        controllees = ui.pop_if_in(kw, 'controllees')
        ui.window.__init__(self, **kw)
        self.controllees_def = controllees
        copy_children(self, 'control.yaml')
        self.slider = self.find_window('timeslider')
        self.slider.set_position(0)
        self.slider.set_callback(self.on_slide)

    def on_slide(self, position):
        self.slider.set_position(position)

    def layout_children(self):
        ui.window.layout_children(self)
        if not hasattr(self, 'controllees'):
            if self.controllees_def:
                self.controllees = map(ui.desktop.find_window,
                                       self.controllees_def.strip().split())
            else:
                self.controllees = self.find_views()

    def find_views(self):
        def rec_find(w):
            if isinstance(w, view):
                yield w
            for child in w.children:
                for v in rec_find(child):
                    yield v
        return list(rec_find(ui.desktop))

def copy_children(self, filename):
    for child in ui.window_from_dicttree(yaml.load(file(filename))).children:
        self.children.append(child)

class slider(ui.window):
    def __init__(self, **kw):
        ui.window.__init__(self, **kw)
        copy_children(self, 'slider.yaml')
        self.handle = self.find_window('handle')
        self.dragging = None
        self.callback = None
    def on_mouse_enter(self, *etc):
        self.handle.hilite()
    def on_mouse_leave(self, *etc):
        self.handle.lolite()
    def on_mouse_drag(self, x, y, dx, dy, *etc):
        if not self.callback:
            return
        if not self.dragging:
            self.handle.hilite()
            self.dragging = x, self.handle.position
            ui.start_drag(self)
        orig_x, orig_pos = self.dragging
        pos = orig_pos + (x - orig_x) / self.handle.range
        self.callback(max(0, min(1, pos)))
        return True
    def set_callback(self, callback):
        self.callback = callback
    def set_position(self, position):
        self.handle.set_position(max(0, min(1, position)))
    def on_end_drag(self, x, y):
        self.dragging = None
        # XXX: I should really check if the mouse cursor is still on me, but
        #      current ui.py is such a mess..
        ui.desktop.rec_mouse_motion(x, y, 0, 0)

class slider_background(ui.window):
    def draw(self):
        glColor3ub(*colors['teal'])
        glBegin(GL_LINE_LOOP)
        glVertex2i(0, 0)
        glVertex2i(self.rect.width, 0)
        glVertex2i(self.rect.width, self.rect.height)
        glVertex2i(0, self.rect.height)
        glEnd()

class slider_handle(ui.window):

    def __init__(self, **kw):
        ui.window.__init__(self, **kw)
        self.position = 0
        self.lolite()

    def hilite(self):
        self.color = colors['white']

    def lolite(self):
        self.color = colors['teal']

    def set_position(self, position):
        self.position = position
        if hasattr(self, 'range'):  # XXX: :'(
            self.rect.left = int(position * self.range)

    def _layout(self, rect, blah, parent):
        mywidth = rect.width // 50
        self.range = rect.width - mywidth
        return (ui.rect(int(self.position * self.range),
                        0,
                        mywidth,
                        rect.height),
                rect)
                
    def draw(self):
        glColor3ub(*self.color)
        glBegin(GL_QUADS)
        glVertex2i(0, 0)
        glVertex2i(self.rect.width, 0)
        glVertex2i(self.rect.width, self.rect.height)
        glVertex2i(0, self.rect.height)
        glEnd()

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
    # XXX: assuming c_ubyte array.  Learn how to figure out actual type.
    ret = (c_ubyte * len(a))()
    copy_buffer(ret, a)
    return ret

def copy_buffer(dst, src):
    memmove(dst, src, sizeof(dst))

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
    run(cmds)

def run(filename):
    """
    Display the search history described in `lines`.

        `lines` is an iterable that yields lines.  For example, a list
        of lines, or a file object that is open for reading.
    """
    w = pyglet.window.Window(resizable=True)
    ui.init(w)
    glPointSize(3)
    glClearColor(.2, .2, .2, 1.)
    ui.desktop.add_child(ui.window_from_dicttree(yaml.load(file(filename))))
    stackless.tasklet(pyglet.app.run)()
    stackless.run()

if __name__ == '__main__':
    if len(sys.argv) == 2:
        run(sys.argv[1])
    else:
        print "Usage: %s <layout_description>" % sys.argv[0]
