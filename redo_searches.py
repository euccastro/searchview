import os

for search_type in ['depth_first',
                    'breadth_first',
                    'uniform_cost',
                    'iterative_deepening_df',
                    'best_first',
                    'astar']:
    os.system('python search.py %s prettygraph 4510 1407 %s_history' 
              % (search_type, search_type))
