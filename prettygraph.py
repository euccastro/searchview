from __future__ import division

import random
import time

from la import vec2


# Parameters.
world_width = 700
world_height = 500
min_dist = 4
packedness = .6


class vec2wid(vec2):
    def __init__(self, x, y, id_=None):
        vec2.__init__(self, x, y)
        self.id = id

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
    def rec_edges(hsorted, vsorted):
        """
        Populate the `ret` array with a suitable list of edges.

        This algorithm tries to absolutely avoid crossing edges and islands,
        and reduce the probability of extreme angles and lengths.

        Target time complexity is n*log(n).
        """
        assert len(hsorted) == len(vsorted)
        if len(hsorted) < 2:
            return
        hdelta = hsorted[-1].x - hsorted[0].x
        vdelta = vsorted[-1].y - vsorted[0].y

        if hdelta < vdelta:
            # Space is vertically elongated, split about horizontal axis, that
            # is, according to y value.

            # Index of lowest element in top partition.
            mid_index = len(l)//2+1
            mid_y = vsorted[mid_index].y
            bottom_vsorted = vsorted[:mid_index]
            top_vsorted = vsorted[mid_index:]
            bottom_hsorted = [v
                              for v in hsorted
                              if v.y < mid_y]
            top_hsorted = [v
                           for v in hsorted
                           if v.y >= mid_y]
            rec_vertices(bottom_hsorted, bottom_vsorted)
            rec_vertices(top_hsorted, top_vsorted)
            # At this point I have hopefully done a decent job of connecting
            # both divisions internally.  I'll add some edges to connect top
            # to bottom.

            # If possible, I'd rather connect only edges that are not too far
            # from each other.  First I'll try to isolate a horizontal strip
            # around the division point.
            strip_height = min_dist * 2
            top_strip = [(i, v)
                         for i, v in top_hsorted
                         if v.y - mid_y < strip_height]
            # Give bottom half a bit more of leeway.
            bottom_strip = [(i, v)
                            for i, v in bottom_hsorted
                            if mid_y - v.y < strip_height]

            # If this doesn't give me some candidate vertices at both sides,
            # I'll default to just sloppily connect the division vertex with
            # the highest vertex in the low division.  This last resource
            # should avoid islands.
            if not bottom_strip:
                edges.append(top_vsorted[0][0],
                             bottom_vsorted[-1][0])
                return

            # In order to guarantee that I don't cross any edges internal to
            # each subdivision, for each strip I'll discard all vertices but
            # the ones in the 'front-facing' side of its convex hull.  A simple
            # way to discard 'back-facing' vertices is to add two additional
            # vertices that are guaranteed to form the whole backside, then
            # remove those.

            def frontside(strip, direction):
                behind = mid_y - direction * strip_height * 2
                backyard_eaters = [vec2(strip[0].x,
                                        behind),
                                   vec2(strip[-1].x,
                                        behind)]
                ret = la.convex_hull(strip + backyard_eaters)
                for bogus in backyard_eaters:
                    strip.remove(bogus)
                return strip
            
            bottom_strip = frontside(bottom_strip, +1)
            top_strip = frontside(top_strip, -1)
            
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
                    if a[0].x < b[0].x:
                        a = a_strip.pop(0)
                    else:
                        b = b_strip.pop(0)

            linked_any = False
            # I get this now because merge destroys the strips.
            default = a_strip[len(a_strip)//2], b_strip[len(b_strip//2)]
            for bottom, top in merge(bottom_strip, top_strip):
                if random.random() <= prob_link:
                    ret.append((bottom, top))
                    linked_any = True
            if not linked_any:
                ret.append(default)
                

    return rec_vertices(sorted(verts, key=(lambda v: v.x)), 
                        sorted(verts, key=(lambda v: v.y)))

def write_verts():
    v = verts()
    with file('verts', 'w') as out:
        out.write("begin vertices\n")
        for vec in v:
            out.write("%s %s %s\n" % (v.id, v.x, v.y))
        out.write("end vertices\n")
    print "Dun.", len(v)
