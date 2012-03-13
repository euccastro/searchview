import os

for search_type in ['depth_first',
                    'breadth_first',
                    'uniform_cost',
                    'best_first',
                    'astar',
                    'bidirectional_astar'][-2:]:
    os.system('python search.py %s prettygraph 2715 1407 %s_history' 
              % (search_type, search_type))
