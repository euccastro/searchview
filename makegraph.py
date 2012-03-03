from __future__ import division

from itertools import *
ichain = chain.from_iterable
import random

import gv
import wordchain as wc


def make_graph(connections):
    """
    Take a description of the connectivity of a graph and return a 
    representation of that graph in 2D cartesian space.

    Input:

        `connections`

            An iterable over pairs of 'nodes' that are connected.

            A 'node' is an arbitrary object in this context, with the only
            restriction that nodes are uniquely identified by their string
            representations, that is:
            
                (str(node1) == str(node2)) implies (node1 == node2).
    
    Output: a (`vertices`, `edges`) pair, where

        `vertices`

            An iterable yielding something like

                `x_1`, `y_1`, ..., `x_i`, `y_i`, ..., `x_n`, y_n` 

            where `x_i, y_i` are the string representations of the cartesian
            coordinates of a vertex.  It is a bit dirty to return strings
            rather than the values themselves, but these are meant to be
            written out to a file anyway, so I'm avoiding redundant
            conversions.

            Only the vertices that are connected to some other vertex are
            listed here (i.e. don't provide vertices linked to themselves), 
            and the vertex order is arbitrary.
            
            Nothing should be assumed about the coordinate system in which
            these vertices are described.  Neither scale nor origin are
            defined.  You may need to normalize them and rescale them if you
            have specific requirements in this regard.  

        `edges`
            
            An iterable yielding something like
            
                `e_1a, e_1b, ..., e_ia, e_ib, ..., e_na, e_nb`

            where `e_ia, e_ib` are the string representations of the 
            indices of the endpoints of edge `i`, and index `k` corresponds
            to the vertex with coordinates 
            `x=vertices[2*k]`, `y=vertices[2*k+1]`.  I only return strings
            here for consistency with `vertices`.

    Not coincidentially, this is the data expected in the graph description
    of searchview.py '*.history' description files.
    """

    print "Adding edges to graphviz..."
    graph = gv.strictgraph('graph')
    for a, b in connections:
        gv.edge(graph, str(a), str(b))

    print "Laying out..."

    gv.layout(graph, 'sfdp')

    print "Rendering..."

    gv.render(graph)

    print "Creating vertices..."

    vertex_names = set(imap(str, ichain(connections)))

    vertices = ichain(gv.getv(gv.findnode(graph, name), 'pos').split(",")
                      for name in vertex_names)
    print "Creating edges..."

    # So tempted to say dict(reversed(enumerate(vertex_names))) :)
    vertex_indices_by_name = {name: str(i) 
                              for i, name in enumerate(vertex_names)}
    edges = imap(vertex_indices_by_name.__getitem__,
                 chain.from_iterable(connections))

    return vertices, edges

def test():
    print "Generating connections..."
    connections = set(frozenset((word, edit))
                      for word in wc.default_dictionary
                          if word.startswith('a')  # For performance while testing.
                      for edit in wc.single_edits(word)
                          if edit != word
                          and edit in wc.default_dictionary)
    vertices, edges = map(list, make_graph(connections))
    def random_index(l):
        return random.randint(0, len(l)//2-1)
    with file('test.history', 'w') as out:
        out.write("vertices")
        for coord in vertices:
            out.write(" " + coord)
        out.write("\nedges")
        for edge in edges:
            out.write(" " + edge)
        out.write("\n")
        for each in ["start", "goal"]:
            out.write("%s %s\n" % (each, random_index(vertices)))
        colors = ['red', 'green', 'blue', 'cyan', 'yellow', 'magenta']
        for tenth_second in xrange(100):
            out.write("step %s\n" % (tenth_second / 10))
            vert_color = random.choice(colors)
            for vert in (random_index(vertices) for blah in xrange(20)):
                out.write("vertex_color %s %s\n" % (vert, vert_color))
            edge_color = random.choice(colors)
            for edge in (random_index(edges) for blah in xrange(20)):
                out.write("edge_color %s %s\n" % (edge, edge_color))

if __name__ == '__main__':
    test()





