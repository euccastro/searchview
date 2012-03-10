from __future__ import division

import random
import time

from la import convex_hull, vec2


# Parameters.
world_width = 700
world_height = 500
min_dist = 10
prob_link = 1. 


class vec2wid(vec2):
    def __init__(self, x, y, id_=None):
        vec2.__init__(self, x, y)
        self.id = id_
    def __repr__(self):
        return "<vec2 %s: %s, %s>" % (self.id, self.x, self.y)

def verts():
    ret = []

    begin = time.time()
    seen = 0
    screen = set([(x, y) 
                  for x in xrange(world_width) 
                  for y in xrange(world_height)])
    while screen:
        x, y = random.choice(list(screen))
        ret.append(vec2wid(x, y, len(ret)))
        for nx in xrange(x-min_dist, x+min_dist):
            for ny in xrange(y-min_dist, y+min_dist):
                try:
                    screen.remove((nx, ny))
                except KeyError:
                    pass
        if (len(ret) % 100) == 0 and len(ret) > seen:
            seen = len(ret)
            now = time.time()
            print now-begin, ": Got", len(ret), "ret."
            begin = now
    return ret

def edges(vertices):

    ret = []
    def add_edge(a, b):
        ret.append((a, b))

    def rec_edges(hsorted, vsorted, indentation=0):
        """
        Populate the `ret` array with a suitable list of edges.

        This algorithm tries to absolutely avoid crossing edges and islands,
        and reduce the probability of extreme angles and lengths.

        Target time complexity is n*log(n).
        """
        def prindent(*args):
            return
            print ("    " * indentation) + " ".join(map(str, args))
        assert len(hsorted) == len(vsorted)
        if len(hsorted) < 2:
            return
        hdelta = hsorted[-1].x - hsorted[0].x
        vdelta = vsorted[-1].y - vsorted[0].y

        # If True, space is vertically elongated, split about horizontal axis,
        # that is, according to y value.
        vertical = int(hdelta < vdelta)

        if vertical:
            array, other_array = vsorted, hsorted

        else:
            array, other_array = hsorted, vsorted

        # Index of lowest element in top partition.
        mid_index = len(array)//2
        mid_coord = array[mid_index][vertical]
        less_sorted = array[:mid_index]
        more_sorted = array[mid_index:]

        if vertical:
            prindent("Vertical split around %s." % array[mid_index].id)
            prindent("below:", *(v.id for v in less_sorted))
            prindent("above:", *(v.id for v in more_sorted))
        else:
            prindent("Horizontal split around %s." % array[mid_index].id)
            prindent("left:", *(v.id for v in less_sorted))
            prindent("right:", *(v.id for v in more_sorted))

        # XXX: sleazy hack.  Not sure that this is correct, but if I get a
        #      good-looking graph I'll happily sweep this under the rug.
        #      To ensure correctness, I should do this as a preprocess instead.
        epsilon = .0001
        for v in reversed(less_sorted):
            if v[vertical] == mid_coord:
                v[vertical] -= epsilon
            else:
                break

        other_less_sorted = [v
                             for v in other_array
                             if v[vertical] < mid_coord]
        other_more_sorted = [v
                             for v in other_array
                             if v[vertical] >= mid_coord]
        if vertical:
            rec_edges(other_less_sorted, less_sorted, indentation+1)
            rec_edges(other_more_sorted, more_sorted, indentation+1)
        else:
            rec_edges(less_sorted, other_less_sorted, indentation+1)
            rec_edges(more_sorted, other_more_sorted, indentation+1)

        # At this point I have hopefully done a decent job of connecting
        # both divisions internally.  I'll add some edges to connect top
        # to bottom.

        # If possible, I'd rather connect only edges that are not too far
        # from each other.  First I'll try to isolate a horizontal strip
        # around the division point.
        # I want this strip ordered in the 'other' direction.
        strip_breadth = min_dist * 2
        def filter_strip(division):
            return [v
                    for v in division
                    if abs(v[vertical] - mid_coord) < strip_breadth]

        less_strip = filter_strip(other_less_sorted)
        more_strip = filter_strip(other_more_sorted)

        # If this doesn't give me some candidate vertices at both sides,
        # I'll default to just sloppily connect the division vertex with
        # the highest vertex in the low division.  This last resource
        # should avoid islands.
        if not less_strip:
            prindent("something crazy", more_sorted[0].id, less_sorted[-1].id)
            #add_edge(more_sorted[0], less_sorted[-1])
            return

        # In order to guarantee that I don't cross any edges internal to
        # each subdivision, for each strip I'll discard all vertices but
        # the ones in the 'front-facing' side of its convex hull.  A simple
        # way to discard 'back-facing' vertices is to add two additional
        # vertices that are guaranteed to form the whole backside, then
        # remove those.

        def frontside(strip, direction):
            behind = mid_coord - direction * strip_breadth * 2
            backyard_eaters = [vec2(0, 0), vec2(0, 0)]
            backyard_eaters[0][vertical] = behind
            backyard_eaters[0][not vertical] = strip[0][not vertical]
            backyard_eaters[1][vertical] = behind
            backyard_eaters[1][not vertical] = strip[-1][not vertical]
            ret = convex_hull(strip + backyard_eaters)
            for bogus in backyard_eaters:
                try:
                    ret.remove(bogus)
                except ValueError:
                    # Special case: we had only one vertex, or several aligned
                    # vertices.
                    assert len(ret) == 1
            # convex_hull() messes with the ordering of our lists!
            # I need to re-sort here :/
            ret.sort(key=(lambda v: v[not vertical]))
            return ret
        
        less_strip = frontside(less_strip, +1)
        more_strip = frontside(more_strip, -1)
        
        def merge(a_strip, b_strip):
            a = a_strip.pop(0)
            b = b_strip.pop(0)
            while True:
                yield a, b
                if not a_strip:
                    for b in b_strip:
                        yield a, b
                    return
                if not b_strip:
                    for a in a_strip:
                        yield a, b
                    return
                if a_strip[0][not vertical] < b_strip[0][not vertical]:
                    a = a_strip.pop(0)
                else:
                    b = b_strip.pop(0)

        linked_any = False
        # I get this now because merge destroys the strips.
        default_edge = (less_strip[len(less_strip)//2], 
                        more_strip[len(more_strip)//2])
        for less, more in merge(less_strip, more_strip):
            prindent("considering", less.id, more.id)
            if random.random() <= prob_link:
                prindent("adding edge", less.id, more.id)
                add_edge(less, more)
                linked_any = True
        if not linked_any:
            prindent("default edge", default_edge[0].id, default_edge[1].id)
            add_edge(*default_edge)
        prindent("end split")

    rec_edges(sorted(vertices, key=(lambda v: v.x)), 
              sorted(vertices, key=(lambda v: v.y)))
    return ret

def write_verts_and_edges():
    v = verts()
    e = edges(v)
    with file('prettygraph', 'w') as out:
        out.write("begin vertices\n")
        for vec in v:
            out.write("%s %s %s\n" % (vec.id, vec.x, vec.y))
        out.write("end vertices\n\nbegin edges\n")
        for a, b in e:
            out.write("%s %s\n" % (a.id, b.id))
        out.write("end edges\n")
    
def debug_edges():
    import itertools as it
    lines = iter(it.imap(str.strip, file('prettygraph')))
    for line in lines:
        if line == 'begin vertices':
            break
    vertices = []
    for line in lines:
        if line == 'end vertices':
            break
        id_, x, y = line.split()
        vertices.append(vec2wid(float(x), float(y), id_))
    import pdb
    pdb.set_trace()
    e = edges(vertices)

if __name__ == '__main__':
    write_verts_and_edges()
    #debug_edges()
