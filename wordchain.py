#!/usr/bin/env python

import gc
from heapq import heappush, heappop
from itertools import *
import string
import time


default_dictionary = set([
        s.lower()
        for s in imap(str.strip, file('/usr/share/dict/american-english'))
        if s and "'" not in s])

def memoized(f):
    """
    Wrap a function so it remembers the results of former calls to it, ignoring
    argument order.
    """
    d = {}
    def wrapper(w1, w2):
        if (w1, w2) not in d:
            d[w1, w2] = f(w1, w2)
        return d[w1, w2]
    return wrapper

@memoized
def edit_distance(w1, w2):
    if not w1 or not w2:
        return max(len(w1), len(w2))
    elif w1[0] == w2[0]:
        # First character matches, move on.
        return edit_distance(w1[1:], w2[1:])
    else:
        # In the general case I want to reduce everything to an operation that
        # reduces the length of either word.  To be sure that's correct, I
        # need to prove that it's ok to substitute the removal of a letter in
        # word `a` for the addition of a letter in word `b`.  This is perhaps
        # the same as assuming that adding letters to the longer word never
        # gives you a shorter path from one word to the other (prove this too).
        #
        # I'm assuming this/these for the time being.
        # Edit: the Wikipedia version does the same thing, just building a 
        # table instead of abusing the stack.  So the above assumptions must
        # be right.  I'll keep this for the time being.
        return min(edit_distance(w1[1:], w2),
                   edit_distance(w1, w2[1:]),
                   edit_distance(w1[1:], w2[1:])  # substitute the first letter 
                                                  # of one word to match the 
                                                  # other
                   ) + 1

# I want to use memoization only for a lookup table of size up to (n^2)/2 the 
# dictionary size, not for every recursive call of edit_distance.  The latter
# approach might be an overall win, but I don't know an upper bound on the
# size of the table that would be needed for it.
#ms_edit_distance = memoized_symmetric(edit_distance)


def wordchain(start, 
              goal, 
              dictionary=default_dictionary, 
              log_fn=None,
              graph=None):

    if log_fn is None:
        def log(*what):
            pass
    else:
        def log(*what):
            log_fn(" ".join(map(str, what)) + "\n")

    if graph is None:
        def add_edge(a, b):
            pass
    else:
        def add_edge(a, b):
            graph.append((a, b))

    log("start", start)
    log("goal", goal)

    gc.disable()

    # Bidirectional A* with edit_distance as the heuristic.
    search_from_start = AStarSearchState(start, goal)
    search_from_goal = AStarSearchState(goal, start)

    permutations = [(search_from_start, search_from_goal, 'red'),
                    (search_from_goal, search_from_start, 'blue')]

    start_time = time.time()
    while search_from_start.frontier and search_from_goal.frontier:
        log("step", time.time() - start_time)
        for search, other, color in permutations:
            estimated_cost, cost_so_far, chain, contact = heappop(search.frontier)
            last = chain[-1]
            if last in search.visited:
                # We have considered a chain that reaches this node earlier.
                continue
            log("vertex_color", last, color)
            if len(chain) > 1:
                log("edge_color", chain[-2], last, color)
            search.visited.add(last)
            if contact:
                solution = chain + list(reversed(contact[0]))
                if search is search_from_goal:
                    solution.reverse()
                log("step", time.time() - start_time)
                for a, b in izip(solution[:-1], solution[1:]):
                    if a != last:
                        log("vertex_color", a, "green")
                    if b != last:
                        log("vertex_color", b, "green")
                    log("edge_color", a, b, "green")
                log("vertex_color", last, "yellow")
                print "solution has length", len(solution)
                return solution
            for ec, csf, other_chain, other_contact in other.frontier:
                if other_chain[-1] == last:
                    # If I had visited this word before I would have `continue`d
                    # in the first check above.
                    assert not other_contact
                    other_contact.append(chain[:-1])
            for word in single_edits(last):
                if word in dictionary and word != last:
                    add_edge(last, word) 
                    if word not in search.visited:
                        log("vertex_color", word, 'dark_' + color)
                        log("edge_color", last, word, 'dark_' + color)
                        heappush(search.frontier, 
                                 (cost_so_far + edit_distance(word, search.goal), 
                                  cost_so_far + 1, 
                                  chain + [word], 
                                  []))
    log("step", time.time() - start_time)
    return None

def endnodes(frontier):
    for estimated_cost, cost_so_far, chain in frontier:
        yield chain[-1]

class AStarSearchState:
    def __init__(self, start, goal):
        self.visited = set()
        # Estimated cost, cost so far, chain, contact.
        #
        # I pick a list for contact to make it mutable and easy to check 
        # for (non)emptiness.
        self.frontier = [(0, 0, [start], [])]
        self.goal = goal

def single_edits(word):
    for letter in string.lowercase:
        yield letter + word  # insert letter at beginning
        if word:
            yield letter + word[1:]  # substitute first letter
    if word:
        suffix = word[1:]
        yield suffix  # remove first letter
        for edit in single_edits(suffix):
            # add all edits to subsequent letter positions
            if edit != suffix:
                yield word[0] + edit

if __name__ == '__main__':
    import sys
    if len(sys.argv) not in [3, 4]:
        print "Usage: %s <start_word> <goal_word> [<times>=1]" % sys.argv[0]
        sys.exit(1)
    if len(sys.argv) == 4:
        times = int(sys.argv[3])
    else:
        times = 1
    for i in xrange(times-1):
        wordchain(*sys.argv[1:3])
    # XXX: temporary hack to check something...
    graph = []
    with file('history', 'w') as out:
        words = wordchain(sys.argv[1], sys.argv[2], log_fn=out.write, graph=graph)
    import makegraph
    makegraph.write_graph(graph, file('-'.join(sys.argv[1:3]) + '.graph', 'w'))
    if words is None:
        print "No chain found."
    else:
        for word in words:
            print word,
        print
