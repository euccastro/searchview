import os
import sys
from itertools import *

import pyglet
from pyglet.gl import *

colors = {'white': (1., 1., 1.),
          'light_grey': (.8, .8, .8),
          'dark_grey': (.4, .4, .4),
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

    def end(self, vertex):
        self.view.end(int(vertex))

    def vertex_color(self, vertex, color):
        self.view.vertex_color(int(vertex), colors[color])

    def edge_color(self, edge, color):
        self.view.edge_color(int(edge), colors[color])


if __name__ == '__main__':
    if len(sys.argv) == 1:
        filename = "pipe"
    elif len(sys.argv) == 2:
        filename = sys.argv[1]
    os.mkfifo(filename)
    it = interpreter(searchview())
    for line in file(filename):
        words = line.split()
        getattr(it, "cmd_" + words[0], words[1:])
    os.remove(filename)
