from chip.block import Block, Config
import chip.abs as acirc
import chip.conc as ccirc
import sys
import itertools
import logging
logger = logging.getLogger('arco_route')
class RouteGraph:
    class RNode:

        def __init__(self,graph,block,loc):
            self._graph = graph
            self._loc = loc
            self._block = block
            self._inputs = graph.board.block(block).inputs
            self._outputs = graph.board.block(block).outputs
            self._passthrough = (graph.board.block(block).type == Block.BUS)
            self._config = None

        def set_config(self,c):
            assert(not c is None)
            self._config = c
        @property
        def config(self):
            if (self._config is None):
                raise Exception("no configuration: %s" % str(self))
            return self._config

        @property
        def loc(self):
            return self._loc

        @property
        def block_name(self):
            return self._block

        @property
        def key(self):
            return "%s.%s" % (self._block,self._loc)

        def input_key(self,inp):
            return "I.%s.%s" % (self.key,inp)

        def output_key(self,out):
            return "O.%s.%s" % (self.key,out)


        def input_keys(self):
            for inp in self._inputs:
                yield self.input_key(inp)

        def output_keys(self):
            for out in self._outputs:
                yield self.output_key(out)

        def __repr__(self):
            return "%s%s" % (self._block,self._loc)

    def __init__(self,board):
        self._nodes = {}
        self._nodes_by_block = {}
        self.board = board


    def add_node(self,block_name,loc):
        assert(isinstance(loc,str))
        node = RouteGraph.RNode(self,block_name,loc)
        if not block_name in self._nodes_by_block:
            self._nodes_by_block[block_name] = []

        self._nodes_by_block[block_name].append(node.key)
        self._nodes[node.key] = node

    def get_node(self,block_name,loc):
        node = RouteGraph.RNode(self,block_name,loc)
        if not node.key in self._nodes:
            for key in self._nodes.keys():
                logger.info(key)
            raise Exception("no node <%s>" % node.key)
        return self._nodes[node.key]

    def nodes_of_block(self,block_name,used=[]):
        used_keys = list(map(lambda node: node.key, used))
        for node_key in self._nodes_by_block[block_name]:
            node = self._nodes[node_key]
            if not node.key in used_keys:
                yield node



GRAPHS = {}
def build_instance_graph(board):
    if board.name in GRAPHS:
        return GRAPHS[board.name]

    graph = RouteGraph(board)
    for block,loc,metadata in board.instances():
        graph.add_node(block,loc)

    GRAPHS[board.name] = graph
    return graph

class DFSAction:
    def __init__(self):
        pass

    def apply(self,ctx):
        raise NotImplementedError

class RouteDFSContext:

    def __init__(self,state):
        self._state = state
        self._nodes_by_block = {}
        self._nodes_by_fragment_id = {}
        self._conns = {}
        self._resolved = []

    def get_node_by_fragment(self,namespace,frag):
        if not (namespace,frag.id) in self._nodes_by_fragment_id:
            return None

        return self._nodes_by_fragment_id[(namespace,frag.id)]


    def resolve_constraint(self,cstr):
        sns,sn,sp,dns,dn,dp = cstr
        key = "%s.%s.%s->%s.%s.%s" % (sns,sn.id,sp,dns,dn.id,dp)
        assert(not key in self._resolved)
        self._resolved.append(key)

    def unresolved_constraints(self):
        for cstr in self._state.constraints():
            sns,sn,sp,dns,dn,dp = cstr
            key = "%s.%s.%s->%s.%s.%s" % (sns,sn.id,sp,dns,dn.id,dp)
            if not key in self._resolved:
                yield (sns,sn,sp,dns,dn,dp)


    def nodes(self):
        for block in self._nodes_by_block:
            for node in self._nodes_by_block[block]:
                yield node

    def conns(self):
        for n1,p1,n2,p2 in self._conns.values():
            yield n1,p1,n2,p2

    def nodes_of_block(self,block):
        if not block in self._nodes_by_block:
            return []

        return self._nodes_by_block[block]

    @property
    def frag_ids(self):
        return self._nodes_by_fragment_id.keys()

    def in_use(self,board,block_name,loc):
        if not block_name in self._nodes_by_block:
            return False
        for node in self._nodes_by_block[block_name]:
            if node.loc == loc:
                return True

        return False


    def use_node(self,node,config,namespace,fragment):
        # routing node
        if not namespace is None and not fragment is None:
            if (namespace,fragment.id) in self._nodes_by_fragment_id:
                raise Exception ("%s.%d already in context" % \
                                 (namespace,fragment_id))

            self._nodes_by_fragment_id[(namespace,fragment.id)] = node

        node.set_config(config)
        if not node.block_name in self._nodes_by_block:
            self._nodes_by_block[node.block_name] = []

        self._nodes_by_block[node.block_name].append(node)

    def conn_node(self,node1,port1,node2,port2):
        if (node1.output_key(port1) in self._conns):
            _,_,old_node2,old_port2 = self._conns[node1.output_key(port1)]
            print("src:  %s.%s" % (node1,port1))
            print("new-dest: %s.%s" % (node2,port2))
            print("old-dest: %s.%s" % (old_node2,old_port2))
            raise Exception("<%s,%s> already connected." % (node1,port1))
        self._conns[node1.output_key(port1)] = (node1,port1,node2,port2)


class DFSResolveConstraint(DFSAction):

    def __init__(self,cstr):
        DFSAction.__init__(self)
        self._cstr = cstr


    def apply(self,ctx):
        ctx.resolve_constraint(self._cstr)

    def __repr__(self):
        return "rslv %s" % (self._cstr)



class DFSUseNode(DFSAction):

    def __init__(self,node,namespace,fragment,config):
        assert(not isinstance(fragment,int))
        DFSAction.__init__(self)
        self._namespace = namespace
        self._frag  = fragment
        self._node = node
        assert(not config is None)
        self._config = config


    def apply(self,ctx):
        ctx.use_node(self._node,self._config,self._namespace,self._frag)

    def __repr__(self):
        if self._frag.id is None:
            raise Exception("fragment has no id <%s>" % self._frag)
        return "%s [%s.%d]" % (self._node,self._namespace,self._frag.id)

class DFSConnNode(DFSAction):

    def __init__(self,node1,port1,node2,port2):
        self._n1 = node1
        self._n2 = node2
        self._p1 = port1
        self._p2 = port2

    def apply(self,ctx):
        ctx.conn_node(self._n1,self._p1,self._n2,self._p2)

    def __repr__(self):
        return "(%s.%s)->(%s.%s)" % (self._n1,self._p1,self._n2,self._p2)

class DFSState:
    def __init__(self):
        self._stack = []
        self._frame = []
        self._ctx = None

    def make_new(self):
        return DFSState()

    def destroy(self):
        self._frame = []

    def copy(self):
        newstate = self.make_new()
        for frame in self._stack:
            newstate._stack.append(list(frame))

        return newstate

    def add(self,v):
        assert(isinstance(v,DFSAction))
        self._frame.append(v)

    def commit(self):
        if len(self._frame) > 0:
            self._stack.append(self._frame)
        self._frame = []

    def pop(self):
        self._stack = self._stack[:-1]

    def new_ctx(self):
        raise NotImplementedError

    def context(self):
        ctx = self.new_ctx()

        for frame in self._stack:
            for op in frame:
                op.apply(ctx)

        return ctx

    def __repr__(self):
        rep = ""
        for frame in self._stack:
            for op in frame:
                rep += str(op) + "\n"
            rep += "-----\n"
        return rep



class RouteDFSState(DFSState):

    def __init__(self,fragment_map,cstrs):
        DFSState.__init__(self)
        self._fragments = fragment_map
        idents = []
        self._cstrs = []
        for sns,sn,sp,dns,dn,dp in cstrs:
            key = "%s.%d.%s->%s.%d.%s" % (sns,sn.id,sp,dns,dn.id,dp)
            if not key in idents:
                idents.append(key)
                self._cstrs.append((sns,sn,sp,dns,dn,dp))


    def make_new(self):
        return RouteDFSState(self._fragments,self._cstrs)


    def new_ctx(self):
        return RouteDFSContext(self)


    def constraints(self):
        return self._cstrs

    def relevent_constraints(self,fragment):
        for sn,sp,dn,dp in self._cstrs:
            if sn.id == fragment.id or dn.id == fragment.id:
                yield (sn,sp,dn,dp)



def tac_collect_sources(graph,namespace,frag,port):
    sources = []
    if isinstance(frag,acirc.AInput):
        if frag.source is None:
            raise Exception("input isn't routed: <%s>" % frag)
        srcfrag,srcport = frag.source
        sources += tac_collect_sources(graph,namespace,srcfrag,srcport)

    elif isinstance(frag,acirc.AJoin):
        for parent in frag.parents():
            assert(isinstance(parent,acirc.AConn))
            srcfrag,srcport = parent.source
            if isinstance(srcfrag,acirc.ABlockInst):
                sources.append((srcfrag,srcport))
            elif isinstance(srcfrag,acirc.AJoin):
                sources += tac_collect_sources(graph,
                                               namespace,
                                               srcfrag,
                                               srcport)

            else:
                logger.info(srcfrag)
                raise NotImplementedError

    elif isinstance(frag,acirc.ABlockInst):
        sources.append((frag,port))

    else:
        raise NotImplementedError

    return sources



def create_instance_set_identifier(route):
    if len(route) == 0:
        return "@",[]

    ident_arr = list(set(map(lambda args: "%s:%s:%s" % args, route)))
    ident_arr.sort()
    raise NotImplementedError


def tac_abs_input(graph,namespace,fragment,ctx,cutoff):
    assert(not fragment.source is None)
    new_frag,output = fragment.source
    new_namespace = fragment.label
    for new_ctx in traverse_abs_circuit(graph,
                                        new_namespace,
                                        new_frag,
                                        ctx=ctx, \
                                        cutoff=cutoff):
        yield new_ctx



def tac_abs_get_resolutions(graph,ctx,cutoff,debug=False):
    choice_list = []
    route_list = []
    node_list = []
    cstr_list = []
    # compute all the valid routes
    for cstr in ctx.context().unresolved_constraints():
        src_ns,src_node,src_port, \
            dest_ns,dest_node,dest_port = cstr
        src_rnode = ctx.context().get_node_by_fragment(src_ns,src_node)
        dest_rnode= ctx.context().get_node_by_fragment(dest_ns,dest_node)
        if src_rnode is None or dest_rnode is None:

            if debug:
                print("src: %s.%d:%s -> %s" % (src_ns,src_node.id,src_port,src_rnode))
                print("dst: %s.%d:%s -> %s" % (dest_ns,dest_node.id,dest_port,dest_rnode))
                print("---")
            continue

        paths= list(graph.board.find_routes(
                src_rnode.block_name,src_rnode.loc,src_port,
                dest_rnode.block_name,dest_rnode.loc,dest_port,
                cutoff=cutoff
        ))
        routes = []
        for path in paths:
            route = []
            for i in range(0,len(path)-1):
                sb,sl,sp = path[i]
                db,dl,dp = path[i+1]
                # internal connection
                if sb == db and sl == dl:
                    continue
                route += [(sb,sl,sp),(db,dl,dp)]
            routes.append(route)

        nodes = []
        for route in routes:
            nodes.append(set([(blk,loc) for blk,loc,port in route[1:-1]]))

        choice_list.append(range(0,len(routes)))
        route_list.append(routes)
        node_list.append(nodes)
        cstr_list.append(cstr)


    for choices in itertools.product(*choice_list):
        nodes = []
        conns = []
        for idx in range(0,len(choices)):
            nodes += node_list[idx][choices[idx]]
            this_route = route_list[idx][choices[idx]]
            for i in range(0,len(this_route)-1):
                sb,sl,sp = this_route[i]
                db,dl,dp = this_route[i+1]
                # internal edge. ignore me
                if sb == db and sl == dl:
                    continue
                conns.append((this_route[i], this_route[i+1]))

        yield cstr_list,nodes,conns


def tac_abs_rslv_constraints(graph,ctx,cutoff,debug=False):
    for cstrs,intermediate_nodes,conns in \
        tac_abs_get_resolutions(graph,ctx,cutoff,debug=debug):
        if len(cstrs) == 0:
            assert(len(intermediate_nodes) == 0)
            assert(len(conns) == 0)
            yield ctx
            return

        base_ctx=ctx.copy()
        for cstr in cstrs:
            step = DFSResolveConstraint(cstr)
            base_ctx.add(step)

        for blk,loc in intermediate_nodes:
            node = RouteGraph.RNode(graph,blk,loc)
            step = DFSUseNode(node,
                              config=Config(), \
                              namespace=None,
                              fragment=None)
            base_ctx.add(step)

        for (sblk,sloc,sport),(dblk,dloc,dport) in conns:
            src_node = RouteGraph.RNode(graph,sblk,sloc)
            dest_node = RouteGraph.RNode(graph,dblk,dloc)
            step = DFSConnNode(src_node,sport, \
                               dest_node,dport)
            base_ctx.add(step)

        base_ctx.commit()
        yield base_ctx



def tac_abs_block_inst(graph,namespace,fragment,ctx=None,cutoff=1):
    node = ctx.context().get_node_by_fragment(namespace,fragment)
    if not node is None:
        yield ctx
        return

    used_nodes = ctx.context().nodes_of_block(fragment.block.name)
    free_nodes = list(graph.nodes_of_block(fragment.block.name,
                                           used=used_nodes))

    print("use %s.%d" % (namespace,fragment.id))
    for node in free_nodes:
        base_ctx=ctx.copy()
        base_ctx.add(DFSUseNode(node,namespace,
                                    fragment,
                                    fragment.config))
        base_ctx.commit()
        for new_base_ctx in tac_abs_rslv_constraints(graph, ctx=base_ctx,\
                                                 cutoff=cutoff):
            for new_ctx in tac_iterate_over_sources(graph,\
                                                    namespace,
                                                    new_base_ctx,
                                                    src_list=fragment.subnodes(),
                                                    cutoff=cutoff):
                yield new_ctx

        #ctx.pop()


def tac_abs_conn(graph,namespace,fragment,ctx,cutoff):
    for new_ctx in tac_iterate_over_sources(graph,namespace, \
                                        src_list=fragment.subnodes(),
                                        ctx=ctx,\
                                        cutoff=cutoff):
        yield new_ctx

def tac_abs_join(graph,namespace,fragment,ctx,cutoff):
    for new_ctx in tac_iterate_over_sources(graph,namespace, \
                                        ctx=ctx,\
                                        src_list=fragment.subnodes(), \
                                        cutoff=cutoff):
        yield new_ctx

'''
resolve the join source to a node
'''

def tac_iterate_over_sources(graph,namespace,ctx, src_list,cutoff=1):
    src_list = list(src_list)
    if len(src_list) == 0:
        yield ctx
    else:
        src_frag = src_list[0]
        for new_ctx in \
            traverse_abs_circuit(graph,
                                 namespace,
                                 src_frag,
                                 ctx=ctx,
                                 cutoff=cutoff):
            for very_new_ctx in tac_iterate_over_sources(graph,
                                                            namespace,
                                                            new_ctx,
                                                            src_list[1:],
                                                            cutoff):
                yield very_new_ctx




def traverse_abs_circuit(graph,namespace,fragment,ctx=None,cutoff=1):
    assert(isinstance(ctx,RouteDFSState))
    if isinstance(fragment,acirc.ABlockInst):
        for ctx in tac_abs_block_inst(graph,namespace,fragment,ctx,cutoff):
            yield ctx

    elif isinstance(fragment,acirc.AConn):
        for ctx in tac_abs_conn(graph,namespace,fragment,ctx,cutoff):
            yield ctx

    elif isinstance(fragment,acirc.AInput):
        for ctx in tac_abs_input(graph,namespace,fragment,ctx,cutoff):
            yield ctx

    elif isinstance(fragment,acirc.AJoin):
        for ctx in tac_abs_join(graph,namespace,fragment,ctx,cutoff):
            yield ctx

    else:
        raise Exception(fragment)

def der_abs_block_inst(namespace,fragment,ids,upstream=None):
    for node in fragment.subnodes():
        for cstr in derive_fragment_constraints(namespace,node,ids,upstream):
            yield cstr

def der_abs_input(namespace,fragment,ids,upstream=None):
    new_frag,output = fragment.source
    for cstr in derive_fragment_constraints(namespace,new_frag,ids,upstream):
        yield cstr

def der_abs_conn(namespace,fragment,ids,upstream=None):
    src_node,src_port = fragment.source
    dest_node,dest_port = fragment.dest
    new_upstream = None
    new_namespace = namespace
    if isinstance(src_node,acirc.ABlockInst) and \
       isinstance(dest_node,acirc.ABlockInst):
        yield (namespace,src_node,src_port, \
               namespace,dest_node,dest_port)

    elif isinstance(src_node,acirc.AInput) and \
       isinstance(dest_node,acirc.ABlockInst):
        rslv_src_node,rslv_src_port = src_node.source
        rslv_namespace = src_node.label
        new_namespace = rslv_namespace
        if isinstance(rslv_src_node,acirc.ABlockInst):
            yield (rslv_namespace,rslv_src_node,rslv_src_port, \
                   namespace,dest_node,dest_port)
        else:
            new_upstream = (namespace,dest_node,dest_port)
            pass

    elif isinstance(src_node,acirc.AJoin) and \
       isinstance(dest_node,acirc.ABlockInst):
        new_upstream = (namespace,dest_node,dest_port)
        pass

    elif isinstance(src_node,acirc.ABlockInst) and \
       isinstance(dest_node,acirc.AJoin):
        if not dest_node.is_root():
            assert(not upstream is None)

        if not upstream is None:
            upstream_namespace,upstream_node,upstream_port = upstream
            yield (namespace,src_node,src_port, \
                upstream_namespace,upstream_node,upstream_port)
    else:
        raise Exception("implement conn: %s" % fragment)

    for subnode in fragment.subnodes():
        for cstr in derive_fragment_constraints(new_namespace,subnode,ids,\
                                                upstream=new_upstream):
            yield cstr

def der_abs_join(namespace,fragment,ids,upstream=None):
    for subnode in fragment.subnodes():
        for cstr in derive_fragment_constraints(namespace,subnode,ids, \
                                                upstream=upstream):
            yield cstr


def derive_fragment_constraints(namespace,fragment,ids,upstream=None):
    if fragment.id in ids:
        return

    ids.append(fragment.id)
    if isinstance(fragment,acirc.ABlockInst):
        for cstr in der_abs_block_inst(namespace,fragment,ids,upstream=upstream):
            yield cstr

    elif isinstance(fragment,acirc.AInput):
        for cstr in der_abs_input(namespace,fragment,ids,upstream=upstream):
            yield cstr


    elif isinstance(fragment,acirc.AConn):
        for cstr in der_abs_conn(namespace,fragment,ids,upstream=upstream):
            yield cstr

    elif isinstance(fragment,acirc.AJoin):
        for cstr in der_abs_join(namespace,fragment,ids,upstream=upstream):
            yield cstr
    else:
        raise Exception("unknown: %s" % fragment)

def derive_abs_circuit_constraints(fragment_map):

    for variable,fragment in fragment_map.items():
        print(fragment)
        for sns,sn,sp,dns,dn,dp in derive_fragment_constraints(variable,fragment,[]):
            print("--- src  ---")
            print(sn)
            print("--- dest ---")
            print(dn)
            assert(isinstance(sn,acirc.ABlockInst))
            assert(isinstance(dn,acirc.ABlockInst))
            yield (sns,sn,sp,dns,dn,dp)


def traverse_abs_circuits(graph,variables,fragment_map,ctx=None,cutoff=1):
    variable = variables[0]
    fragment = fragment_map[variable]
    print(">>> compute variable [%s] <<<" % variable)
    for result in \
        traverse_abs_circuit(graph,variable,fragment,
                             ctx=ctx,
                             cutoff=cutoff):
        if len(variables) > 1:
            for subresult in traverse_abs_circuits(graph,
                                                   variables[1:],
                                                   fragment_map,
                                                   ctx=result,
                                                   cutoff=cutoff):
                yield subresult

        else:

            for new_result in \
                tac_abs_rslv_constraints(graph,result,cutoff,debug=True):
                unresolved = list(new_result.context().unresolved_constraints())
                total = len(new_result.constraints())
                if len(unresolved) > 0:
                    print("-> skipping <%d/%d> unresolved configs" % \
                          (len(unresolved),total))
                    input("<continue>")
                    continue

                print(">>> found solution [%d/%d unresolved] <<<" % (len(unresolved),\
                                                                   total))
                yield new_result

def build_concrete_circuit(name,graph,fragment_map):
    variables = list(fragment_map.keys())
    for var,frag in fragment_map.items():
        logger.info("=== %s ===" % var)

    print(">>> derive constraints <<<")
    all_cstrs = list(derive_abs_circuit_constraints(fragment_map))
    starting_ctx = RouteDFSState(fragment_map,all_cstrs)
    for idx,result in \
        enumerate(traverse_abs_circuits(graph, \
                                        variables, \
                                        fragment_map,
                                        ctx=starting_ctx,
                                        cutoff=3)):
        state = result.context()

        circ = ccirc.ConcCirc(graph.board,"%s_%d" % (name,idx))

        for n1,p1,n2,p2 in state.conns():
            print("%s[%s].%s -> %s[%s].%s" % \
            (n1.block_name,n1.loc,p1,n2.block_name,n2.loc,p2))
        for node in state.nodes():
            print(node.block_name,node.loc)
            circ.use(node.block_name,node.loc,config=node.config)

        for n1,p1,n2,p2 in state.conns():
            circ.conn(n1.block_name,n1.loc,p1,
                      n2.block_name,n2.loc,p2)

        yield circ

    return


def route(basename,board,node_map):
    #sys.setrecursionlimit(1000)
    graph = build_instance_graph(board)
    logger.info('--- concrete circuit ---')
    for conc_circ in build_concrete_circuit(basename,graph,node_map):
        print("<<<< CONCRETE CIRCUIT >>>>")
        yield conc_circ
