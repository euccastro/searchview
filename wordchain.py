#!/usr/bin/env python

from heapq import heappush, heappop


raw_dict = file('/usr/share/dict/american-english').read()

default_dictionary = set(raw_dict.split())


def memoized_symmetric(f):
    """
    Wrap a function so it remembers the results of former calls to it, ignoring
    argument order.
    """
    d = {}
    def wrapper(*args):
        key = tuple(sorted(args))
        if key not in d:
            d[key] = f(*args)
        return d[key]
    return wrapper

@memoized_symmetric
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


def wordchain(start, goal, dictionary=default_dictionary):
    # I'll do A* with edit_distance as the heuristic.
    # Rather than maintain a visited set, I'll just remove visited entries 
    # from the dictionary.
    mydict = dictionary.copy()
    # Total cost, cost so far, chain.
    frontier = [(0, 0, [start])]
    while frontier:
        estimated_cost, cost_so_far, chain = heappop(frontier)
        last = chain[-1]
        if last == goal:
            return chain
        if last not in mydict:
            # We have considered a chain that reaches this node earlier.
            continue
        mydict.remove(last)
        for word in mydict:
            if edit_distance(word, last) == 1:
                heappush(frontier, (cost_so_far + edit_distance(word, goal), cost_so_far + 1, chain + [word]))
    return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print "Usage: %s <start_word> <goal_word>" % sys.argv[0]
        sys.exit(1)
    words = wordchain(*sys.argv[1:])
    if words is None:
        print "No chain found."
    else:
        for word in words:
            print word,
        print
