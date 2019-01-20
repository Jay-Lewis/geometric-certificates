""" File that contains the algorithm for geometric certificates in piecewise
    linear neural nets or general unions of perfectly glued polytopes

"""

from _polytope_ import Polytope, Face, from_polytope_dict
import utilities as utils
import torch
import numpy as np
import heapq

##############################################################################
#                                                                            #
#                               BATCHED GEOCERT                              #
#                                                                            #
##############################################################################

# Batched algorithm is when the union of polytopes is specified beforehand

def compute_boundary_batch(polytope_list, comparison_method = 'slow'):
    """ Takes in a list of polytopes and outputs the facets that define the
        boundary
    """

    total_facets = [facet for poly in polytope_list for facet in poly.generate_facets(check_feasible=True)]

    print('num total facets:', len(total_facets))

    unshared_facets = []
    shared_facets = []

    for og_facet in total_facets:

        if comparison_method == 'slow':
            bool_unshared = [og_facet.check_same_facet_pg_slow(ex_facet)
                             for ex_facet in unshared_facets]

            bool_shared = [og_facet.check_same_facet_pg_slow(ex_facet)
                           for ex_facet in shared_facets]

        elif comparison_method == 'unstable':
            bool_unshared = [og_facet.check_same_facet_pg(ex_facet)
                   for ex_facet in unshared_facets]
            bool_shared = [og_facet.check_same_facet_pg(ex_facet)
                   for ex_facet in shared_facets]

        elif comparison_method == 'fast_ReLu':
            bool_unshared = [og_facet.check_same_facet_config(ex_facet)
                   for ex_facet in unshared_facets]
            bool_shared = [og_facet.check_same_facet_config(ex_facet)
                   for ex_facet in shared_facets]

        if any(bool_shared):
            continue
        elif any(bool_unshared):
            index = bool_unshared.index(True)
            shared_facet = unshared_facets[index]
            unshared_facets.remove(shared_facet)
            shared_facets.append(shared_facet)
        else:
            unshared_facets.append(og_facet)

    print('num boundary_facets', len(unshared_facets))
    print('num shared_facets',  len(shared_facets))

    return unshared_facets, shared_facets



def compute_l_inf_ball_batch(polytope_list, x, comp_method = 'slow'):
    """ Computes the distance from x to the boundary of the union of polytopes

        Comparison method options: {slow | unstable | fast_ReLu}
    """

    # First check if x is in one of the polytopes
    if not any(poly.is_point_feasible(x) for poly in polytope_list):
        return -1

    print('========================================')
    print('Computing Boundary')
    print('========================================')
    boundary, shared_facets = compute_boundary_batch(polytope_list, comp_method)

    dist_to_boundary = [facet.linf_dist(x) for facet in boundary]

    return min(dist_to_boundary), boundary, shared_facets



##########################################################################
#                                                                        #
#                           INCREMENTAL GEOCERT                          #
#                                                                        #
##########################################################################

class HeapElement(object):
    """ Wrapper of the element to be pushed around the priority queue
        in the incremental algorithm
    """
    def __init__(self, linf_dist, facet,
                 decision_bound=False,
                 exact_or_estimate='exact'):
        self.linf_dist = linf_dist
        self.facet = facet
        self.decision_bound = decision_bound
        self.exact_or_estimate = exact_or_estimate

    def __cmp__(self, other):
        return __cmp__(self.l_inf_dist, other.l_inf_dist)


def incremental_geocert(plnn, x):
    """ Computes l_inf distance to decision boundary in
    """

    true_label = int(net(x).max(1)[1].item()) # what the classifier outputs
    seen_to_polytope_map = {} # binary config str -> Polytope object
    seen_to_facet_map = {} # binary config str -> Facet list
    pq = [] # Priority queue that contains HeapElements


    ###########################################################################
    #   Initialization phase: compute polytope containing x                   #
    ###########################################################################

    p_0_dict = net.compute_polytope(x)
    p_0 = from_polytope_dict(p_0_dict)
    p_0_facets = p_0.generate_facets(check_feasible=True)
    p_0_config = utils.flatten_config(p_0_dict['config'])
    p_0_adv_constraints = net.make_adversarial_constraints(p_0_dict['config'],
                                                           true_label)
    seen_to_polytope_map[p_0_config] = p_0
    seen_to_facet_map[p_0_config] = p_0_facets
    for facet in p_0_facets:
        linf_dist = facet.linf_dist(x)
        heap_el = HeapElement(linf_dist, facet, decision_bound=False,
                              exact_or_estimate='exact')
        heapq.heappush(pq, heap_el)

    for facet in p_0_adv_constraints:
        linf_dist = facet.linf_dist(x)
        heap_el = HeapElement(linf_dist, facet, decision_bound=True,
                              exact_or_estimate='exact')


    # ADD ADVERSARIAL CONFIGS
    ##########################################################################
    #   Incremental phase -- repeat until we hit a decision boundary         #
    ##########################################################################

    pop_el = heapq.heappop(pq)

    # If only an estimate, make it exact and push it back onto the heap
    if pop_el.exact_or_estimate == 'estimate':
        exact_linf = pop_el.facet.linf_dist(x)
        new_heap_el = HeapElement(exact_linf, pop_el.facet,
                                  decision_bound=pop_el.decision_bound,
                                  exact_or_estimate='exact')

        # BROKEN BUT PUSHING ANYWAY

    if pop_el.decision_bound:
        return pop_el
