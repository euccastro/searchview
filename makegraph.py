from __future__ import division

from itertools import *
ichain = chain.from_iterable
import random

import gv
import wordchain as wc


def layout_graph(edges):
    """
    Take a description of the connectivity of a graph and return a 
    representation of that graph in 2D cartesian space.

    Input:

        `edges`

            An iterable over pairs of 'node_id's that are connected.

            A 'node_id' is an arbitrary object in this context, with the only
            restriction that it's uniquely identified by its string
            representation, that is:
            
                (str(node1) == str(node2)) implies (node1 == node2).
    
    Output:

            An iterable yielding triples of the form 

                (`id`, `x`, `y`) 

            where `id` is the string representation of the node_id that this
            vertex represents, and `x`, `y` are the string representations of
            the cartesian coordinates of said vertex.  It is a bit dirty to
            return strings rather than the values themselves, but these are
            meant to be written out to a file anyway, so I'm avoiding
            redundant conversions.

            Only the vertices that are connected to some other vertex are
            listed here (i.e. don't provide vertices linked to themselves), 
            and the vertex order is arbitrary.
            
            Nothing should be assumed about the coordinate system in which
            these vertices are described.  Neither scale nor origin are
            defined.  You may need to normalize them and rescale them if you
            have specific requirements in this regard.  

        `edges`
            
            An iterable yielding pairs of the form
            
                (`id_a`, `id_b`)

            where `id_a`, `id_b` are the string representations of the 
            `node_id` of the endpoints of this edge.

    Not coincidentially, this is the data expected in the graph description
    referred to in searchview.py '*.history' description files.
    """

    print "Adding edges to graphviz..."
    graph = gv.strictgraph('graph')
    for a, b in edges:
        gv.edge(graph, str(a), str(b))

    print "Laying out..."

    gv.layout(graph, 'sfdp')

    print "Rendering..."

    gv.render(graph)

    print "Creating vertices..."

    vertex_names = set(imap(str, ichain(edges)))

    return (tuple([name] 
                  + gv.getv(gv.findnode(graph, name), 'pos').split(","))
            for name in vertex_names)

def get_edges():
    print "Generating edges..."
    return [(word, edit)
             for word in wc.default_dictionary
                 if word.startswith('b')
             for edit in wc.single_edits(word)
                 if edit != word
                 and edit in wc.default_dictionary]
def test_graph():
    write_graph(get_edges(), file('graph', 'w'))

def test_search():

    edges = get_edges()

    def random_vertex():
        return random_edge()[0]

    def random_color():
        return random.choice(['red', 'green', 'blue', 
                              'cyan', 'magenta', 'yellow'])
    def random_edge():
        return random.choice(edges)

    with file('history', 'w') as out:
        out.write("start %s\n" % random_vertex())
        out.write("goal %s\n" % random_vertex())
        for sixtieth_second in xrange(60 * 10):
            out.write("step %s\n" % (sixtieth_second / 60))
            color = random_color()
            for i in xrange(100):
                out.write("vertex_color %s %s\n" % (random_vertex(),
                                                    color))
            for i in xrange(100):
                a, b = random_edge()
                out.write("edge_color %s %s %s\n" % (a, b, color))


def write_graph(edges, out):
    """
    Generate the 2D representation data as searchview expects it.

    See the docstring of layout_graph for the format expected by this
    function.  This function does normalization of vertex order in edges so
    you don't have to do this yourself.  That is, if you provide both `(a, b)`
    and `(b, a)`, only one edge will be generated.
    """
    edges = set(imap(frozenset, edges))
    vertices = layout_graph(edges)
    out.write("begin vertices\n")
    for id_, x, y in vertices:
        out.write("%s %s %s\n" % (id_, x, y))
    out.write("end vertices\n\nbegin edges\n")
    for a, b in edges:
        out.write("%s %s\n" % (a, b))
    out.write("end edges\n")

if __name__ == '__main__':
    test_search()





