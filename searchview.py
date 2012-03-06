"""
XXX: THIS DOCSTRING IS OBSOLETE.

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
ichain = chain.from_iterable
import os
import stackless
import sys
import time

import pyglet
from pyglet.window import key, mouse
from pyglet.gl import *
import yaml

from util import obj
import ui
from la import vec2

colors = {'white': (1., 1., 1.),
          'grey': (.5, .5, .5),
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

class bsp_tree:

    max_verts_per_cell = 10

    class node:
        def __init__(self, direction, center, less, more):
            """
            `direction` == 0 for nodes split by a vertical line (i.e. according
            to x).
            `direction` == 1 for nodes split by a horizontal line (i.e.
            according to y).
            `center` is x coordinate if direction == 0, else y coordinate.
            `less` and `more` are nodes representing the points at either side
            of my `center`.
            """
            self.direction = direction
            self.center = center
            self.less = less
            self.more = more
        def query(self, *args):
            return (self.less
                    if args[self.direction] < self.center
                    else self.more).query(*args)

    class leaf:
        def __init__(self, vertices):
            self.vertices = vertices
        def query(self, x, y):
            return self.vertices
            
    def __init__(self, vertices):
        self.root = self.build(vertices)

    def query(self, x, y):
        return self.root.query(x, y)

    @staticmethod
    def extents(vertices):
        min_ = vec2(*vertices[0][1:])
        max_ = vec2(*vertices[0][1:])
        for id_, x, y in vertices:
            if x < min_.x:
                min_.x = x
            if x > max_.x:
                max_.x = x
            if y < min_.y:
                min_.y = y
            if y > max_.y:
                max_.y = y
        size = max_ - min_
        return ui.rect(min_.x, min_.y, size.x, size.y)

    def build(self, vertices):
        if len(vertices) <= self.max_verts_per_cell:
            return self.leaf(vertices)
        else:
            rect = self.extents(vertices)
            index = int(rect.width < rect.height)
            less = []
            more = []
            center = rect.center[index]
            for v in vertices:
                coord = v[index + 1]  # v is (id_, x, y)
                (less if coord < center else more).append(v)
            assert less and more
            return self.node(index, center, self.build(less), self.build(more))

class view(ui.window):

    def __init__(self, **kw):
        graph = kw.pop('graph')
        history = kw.pop('history')
        ui.window.__init__(self, **kw)
        vertices, edges, start, goal, color_history = parse(file(graph),
                                                            file(history))
        self.vertices = vertices
        self.start = start
        self.goal = goal
        self.history = color_history
        self.play_position = 0
        self.vertex_buffer = pyglet.graphics.vertex_list(
                len(vertices.buffer) // 2, 'v2f/static', 'c3B/stream')
        self.edge_buffer = pyglet.graphics.vertex_list(
                len(edges) // 2, 'v2f/static', 'c3B/stream')
        copy_buffer(self.vertex_buffer.vertices, self.vertices.buffer)
        copy_buffer(self.vertex_buffer.colors, self.history[0].vertex_colors)
        copy_buffer(self.edge_buffer.vertices, edges)
        copy_buffer(self.edge_buffer.colors, self.history[0].edge_colors)
        self.dragging = None
        self.drag_end = None
        self.closest_vertex = None
        min_, max_ = self.world_extents()
        rect = ui.rect(min_.x, min_.y, max_.x - min_.x, max_.y - min_.y)
        self.bsp_tree = bsp_tree(self.vertices.flat_list)

    def on_mouse_motion(self, x, y, *etc):
        # XXX: factor this out.
        ratio = self.get_zoom_ratio()
        projx = x * ratio + self.zoom_rect.left
        projy = y * ratio + self.zoom_rect.bottom
        closest = min(self.bsp_tree.query(projx, projy),
                      key=(lambda (id_, x, y): (x-projx)**2 + (y-projy)**2))
        if closest != self.closest_vertex:
            self.remove_closest_display()
            self.closest_vertex = closest
            self.show_tooltip(*closest)

    def on_mouse_leave(self, *etc):
        self.remove_closest_display()

    def world_to_window(self, x, y):
        ratio = self.get_zoom_ratio()
        return ((x - self.zoom_rect.left) / ratio,
                (y - self.zoom_rect.bottom) / ratio)

    def window_to_world(self, x, y):
        ratio = self.get_zoom_ratio()
        return (x * ratio + self.zoom_rect.left,
                y * ratio + self.zoom_rect.bottom)

    def show_tooltip(self, id_, x, y):
        height = self.rect.height // 30
        try:
            label = ui.label(layout=ui.fill_layout(), 
                             text=repr(id_)[1:-1],
                             color=(1., 1., 1., 1.))
        except UnicodeDecodeError:
            print "Bad string", repr(id_)
            return
        lw, lh = label.content_size(height)
        margin = .2
        bg_width = lw * (1 + 2 * margin)
        bg_height = lh * (1 + 2 * margin)
        x, y = self.world_to_window(x, y)
        x = max(0, min(self.rect.width - bg_width, x))
        y = max(0, min(self.rect.height - bg_height, y))
        bg_rect = ui.rect(x, y, bg_width, bg_height)
        background = ui.plain_color(id='tooltip',
                                    rect=bg_rect,
                                    color=(.0, .0, .0, .5))
        background.children.append(label)
        background.layout_children()
        self.children.append(background)

    def remove_closest_display(self):
        tooltip = self.find_window('tooltip')
        if tooltip:
            self.children.remove(tooltip)
        self.closest_vertex = self.tooltip = None

    def on_mouse_drag(self, x, y, dx, dy, btn, *etc):
        if not self.dragging:
            self.scrolling = (btn == mouse.LEFT) and self.zoom_rect
            self.zooming = (btn == mouse.RIGHT)
            self.dragging = x, y
            ui.start_drag(self)
        if self.scrolling:
            ratio = self.get_zoom_ratio()
            orig_x, orig_y = self.dragging
            new_x = max(self.world_rect.left,
                        min(self.world_rect.right - self.rect.width * ratio,
                            self.scrolling.left - (x - orig_x) * ratio))
            new_y = max(self.world_rect.bottom,
                        min(self.world_rect.top - self.rect.height * ratio,
                            self.scrolling.bottom - (y - orig_y) * ratio))
            self.zoom_rect = ui.rect(new_x, 
                                     new_y, 
                                     self.zoom_rect.width,
                                     self.zoom_rect.height)
        if self.zooming:
            self.drag_end = x, y
        return True

    def on_end_drag(self, x, y):
        if self.zooming:
            x1, y1 = self.dragging
            x2, y2 = self.drag_end
            self.set_zoom(ui.rect(min(x1, x2), 
                                  min(y1, y2),
                                  abs(x1-x2), 
                                  abs(y1-y2)))
        self.dragging = self.drag_end = None
        self.scrolling = self.zooming = False
    def on_mouse_press(self, x, y, button, mods):
        if button == mouse.MIDDLE:
            self.reset_zoom()
    def set_zoom(self, req_rect):
        if not req_rect.width or not req_rect.height:
            # Bogus dragging.
            return
        current_aspect = self.zoom_rect.width / self.zoom_rect.height
        requested_aspect = req_rect.width / req_rect.height
        # Make sure all the requested area is in the screen, and no more than
        # necessary for that.
        if requested_aspect < current_aspect:
            # Screen is wider than desired frame.
            new_width = current_aspect * req_rect.height
            assert new_width > req_rect.width
            r = ui.rect(req_rect.center.x - new_width / 2,
                        req_rect.bottom,
                        new_width,
                        req_rect.height)
        else:
            # Screen is taller than desired frame.
            new_height = req_rect.width / current_aspect
            assert new_height > req_rect.height
            r = ui.rect(req_rect.left,
                        req_rect.center.y - new_height / 2,
                        req_rect.width,
                        new_height)
        ratio = self.get_zoom_ratio()
        self.zoom_rect = ui.rect(self.zoom_rect.left + r.left * ratio, 
                                 self.zoom_rect.bottom + r.bottom * ratio, 
                                 r.width * ratio,
                                 r.height * ratio)

    def get_zoom_ratio(self):
        wratio = self.zoom_rect.width / self.rect.width
        hratio = self.zoom_rect.height / self.rect.height
        # These should be mostly the same, barring some small rounding error.
        assert abs(wratio/hratio - 1) < 0.001
        return (wratio + hratio) / 2

    def reset_zoom(self):
        self.zoom_rect = self.world_rect

    def world_extents(self):
        if not hasattr(self, '_world_extents'):
            id_, x, y = self.vertices.flat_list[0]
            min_ = vec2(x, y)
            max_ = vec2(x, y)
            for id_, x, y in self.vertices.flat_list:
                if x < min_.x:
                    min_.x = x
                if x > max_.x:
                    max_.x = x
                if y < min_.y:
                    min_.y = y
                if y > max_.y:
                    max_.y = y
            self._world_extents = min_, max_
        return self._world_extents

    def layout_children(self):
        "Fit graph to screen, with some margin."

        self.remove_closest_display()

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
        self.world_rect = self.zoom_rect = ui.rect(
                wleft, wbottom, wwidth, wheight)

    def go_to_position(self, i):
        if i != self.play_position:
            self.play_position = i
            current = self.history[i]
            assert len(self.vertex_buffer.colors) == len(current.vertex_colors)
            copy_buffer(self.vertex_buffer.colors, current.vertex_colors)
            assert len(self.edge_buffer.colors) == len(current.edge_colors)
            copy_buffer(self.edge_buffer.colors, current.edge_colors)

    def go_to_time(self, t):
        start, end = 0, len(self.history) - 1
        while start < end:
            middle = (start + end) // 2
            if self.history[middle].time < t:
                start = middle + 1
            else:
                end = middle
        self.go_to_position(start)

    def draw(self):
        if not hasattr(self, 'absolute_rect'):
            # XXX get rid of this ugliness...
            return
        glPushAttrib(GL_VIEWPORT_BIT)
        glViewport(self.absolute_rect.left,
                   self.absolute_rect.bottom, 
                   self.absolute_rect.width, 
                   self.absolute_rect.height)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(self.zoom_rect.left, 
                self.zoom_rect.right, 
                self.zoom_rect.bottom, 
                self.zoom_rect.top, 
                -1.0, 
                1.0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        self.edge_buffer.draw(GL_LINES)
        self.vertex_buffer.draw(GL_POINTS)
        if self.closest_vertex is not None:
            glColor3f(1., 1., 1.)
            glBegin(GL_POINTS)
            glVertex2f(*self.closest_vertex[1:])
            glEnd()
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glPopAttrib()
        glMatrixMode(GL_MODELVIEW)
        if self.dragging and self.drag_end:
            x0, y0 = self.dragging
            x1, y1 = self.drag_end
            glColor3ub(*colors['teal'])
            glBegin(GL_LINE_LOOP)
            glVertex2i(x0, y0)
            glVertex2i(x1, y0)
            glVertex2i(x1, y1)
            glVertex2i(x0, y1)
            glEnd()

class control(ui.window):

    def __init__(self, **kw):
        controllees = ui.pop_if_in(kw, 'controllees')
        ui.window.__init__(self, **kw)
        self.controllees_def = controllees
        copy_children(self, 'control.yaml')
        self.slider = self.find_window('timeslider')
        self.slider.set_position(0)
        self.slider.set_callback(self.set_position)
        self.find_window('realtime_button').callback = self.set_realtime
        self.find_window('play_button').callback = self.on_click_play
        total_edit = self.find_window('total_edit')
        total_edit.validate_text = self.validate_total_edit_text
        self.play_time = 5
        self.hide_while_playing = ['total_label',
                                   'total_edit', 
                                   'realtime_button']

    def validate_total_edit_text(self, text):
        try:
            t = float(text)
        except ValueError:
            return False
        if t > 0:
            self.play_time = t
            return True
        else:
            return False

    def on_click_play(self):
        for each in self.hide_while_playing:
            self.find_window(each).visible = False
        play_button = self.find_window('play_button')
        play_button.set_caption('Stop')
        play_button.callback = self.stop
        pyglet.clock.set_fps_limit(60)
        self.start_time = time.time()
        pyglet.clock.schedule(self.play)

    def play(self, dt):
        now = time.time() - self.start_time
        position = now / self.play_time
        if position > 1.0:
            position = 1.0
            self.stop()
        self.set_position(position)

    def stop(self):
        pyglet.clock.unschedule(self.play)
        for each in self.hide_while_playing:
            self.find_window(each).visible = True
        play_button = self.find_window('play_button')
        play_button.set_caption('Play')
        play_button.callback = self.on_click_play

    def set_realtime(self):
        self.play_time = self.end_time
        self.find_window('total_edit').doc.text = str(self.end_time)

    def set_position(self, position):
        self.slider.set_position(position)
        time = self.end_time * position
        for slave in self.controllees:
            slave.go_to_time(time)

    def layout_children(self):
        ui.window.layout_children(self)
        if not hasattr(self, 'controllees'):
            if self.controllees_def:
                self.controllees = map(ui.desktop.find_window,
                                       self.controllees_def.strip().split())
            else:
                self.controllees = self.find_views()
            self.end_time = max(c.history[-1].time for c in self.controllees)
            self.set_realtime()

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

def parse(graph_lines, history_lines):
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
    # This function makes heavy use of iterators and itertools.
    #
    # http://docs.python.org/library/itertools.html
    vertices = None
    edges = None
    start = None
    goal = None
    color_history = [obj(time=0.0)]

    it = ifilter(None, imap(str.strip, graph_lines))

    def take_tuples_until(s):
        return imap(str.split,
                    takewhile((lambda l: l != s), it))

    # Vertices.
    assert it.next() == 'begin vertices'
    vertices = {id_: (float(x), float(y))
                for id_, x, y in take_tuples_until('end vertices')}
    vert_list = [(id_, x, y) for id_, (x, y) in vertices.iteritems()]
    vertex_index_by_id = {id_: i for i, (id_, x, y) in enumerate(vert_list)}
    vertex_buffer = (c_float * (len(vert_list) * 2))(
            *ichain((x, y) for (id_, x, y) in vert_list))

    v = obj(coords_by_id=vertices,
            flat_list=vert_list,
            index_by_id=vertex_index_by_id,
            buffer=vertex_buffer)
    len_vert_colors = len(vert_list) * 3
    color_history[0].vertex_colors = (c_ubyte * len_vert_colors)(
        *repeat(colors['default'][0], len_vert_colors))

    # Edges.
    assert it.next() == 'begin edges'
    edges = [frozenset((a, b))
             for a, b in take_tuples_until('end edges')]
    edge_index_by_vertex_ids = {pair:i
                                for i, pair in enumerate(edges)}

    edge_buffer = (c_float * (len(edges) * 4))(
                   *ichain(ichain((vertices[a], 
                                   vertices[b])
                                   for a, b in edges)))
    len_edge_colors = len(edges) * 6
    color_history[0].edge_colors = (c_ubyte * len_edge_colors)(
            *repeat(colors['default'][0], len_edge_colors))

    for rest in it:
        if rest.strip():
            print "Got unexpected line", repr(rest)

    for line in history_lines:
        line = line.strip()
        if not line:
            continue
        cmd, rest = line.split(None, 1)
        args = rest.split()
        if cmd == 'start':
            assert len(args) == 1
            start = vertices[args[0]]
        elif cmd == 'goal':
            assert len(args) == 1
            goal = vertices[args[0]]
        elif cmd == 'step':
            assert len(args) == 1
            timestamp = float(args[0])
            color_history.append(
                obj(time=timestamp,
                    vertex_colors=clone_array(color_history[-1].vertex_colors),
                    edge_colors=clone_array(color_history[-1].edge_colors)))
        elif cmd == 'vertex_color':
            id_, color_name = args
            index = vertex_index_by_id[id_]
            color_history[-1].vertex_colors[index*3:index*3+3] = \
                    colors[color_name]
        elif cmd == 'edge_color':
            a, b, color_name = args
            index = edge_index_by_vertex_ids[frozenset((a, b))]
            color_history[-1].edge_colors[index*6:index*6+6] = \
                    colors[color_name] * 2
        else:
            raise RuntimeError("Unknown command:", cmd)

    assert None not in [vertex_buffer, edge_buffer, start, goal]
    return v, edge_buffer, start, goal, color_history

def even(x):
    return not (x & 1)

def clone_array(a):
    # XXX: assuming c_ubyte array.  Learn how to figure out actual type.
    ret = (c_ubyte * len(a))()
    copy_buffer(ret, a)
    assert len(ret) == len(a)
    return ret

def copy_buffer(dst, src):
    memmove(dst, src, sizeof(dst))

def run(filename):
    w = pyglet.window.Window(resizable=True)
    ui.init(w)
    glPointSize(3)
    glClearColor(.2, .2, .2, 1.)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_BLEND)
    ui.desktop.add_child(ui.window_from_dicttree(yaml.load(file(filename))))
    stackless.tasklet(pyglet.app.run)()
    stackless.run()

if __name__ == '__main__':
    if len(sys.argv) == 2:
        run(sys.argv[1])
    else:
        print "Usage: %s <layout_description>" % sys.argv[0]
