
class Visitor:

  def __init__(self,circ):
    self._visited = {}
    self._circ = circ

  def clear(self):
    self._visited = {}

  def visit(self,blkname,loc,port):
    print("visit %s[%s].%s" % (blkname,loc,port))
    self._visited[(blkname,loc,port)] = True

  def visited(self,blkname,loc,port):
    return (blkname,loc,port) in self._visited

  def is_free(self,config,variable):
    raise NotImplementedError

  @property
  def circ(self):
    return self._circ

  def classify(self,block_name,loc,variables):
    free,bound = [],[]
    config = self._circ.config(block_name,loc)
    for variable in variables:
      if self.is_free(config,variable):
        free.append(variable)
      else:
        bound.append(variable)

    return free,bound

  def output_port(self,block_name,loc,port):
    circ = self._circ
    block = circ.board.block(block_name)
    config = circ.config(block_name,loc)

    expr = config.dynamics(block,port)
    free,bound = self.classify(block_name,loc,expr.vars())
    if self.visited(block.name,loc,port):
      return

    self.visit(block.name,loc,port)
    for free_var in free:
      self.port(block.name,loc,free_var)


  def input_port(self,block_name,loc,port):
    circ = self._circ
    block = circ.board.block(block_name)
    config = circ.config(block_name,loc)

    self.visit(block.name,loc,port)
    for sblk,sloc,sport in \
      circ.get_conns_by_dest(block_name,loc,port):
      if self.is_free(circ.config(sblk,sloc),sport):
        self.port(sblk,sloc,sport)

  def block(self,block_name,loc):
    circ = self._circ
    block = circ.board.block(block_name)
    for out_port in block.outputs:
      self.output_port(block_name,loc,out_port)

  def port(self,block_name,loc,port):
    circ = self._circ
    block = circ.board.block(block_name)
    if block.is_input(port):
      self.input_port(block_name,loc,port)
    elif block.is_output(port):
      self.output_port(block_name,loc,port)
    else:
      raise Exception("???")

  def toplevel(self):
    circ = self._circ
    for handle,block_name,loc in circ.board.handles():
      if circ.in_use(block_name,loc):
        config = circ.config(block_name,loc)
        for port,label,kind in config.labels():
          self.port(block_name,loc,port)


  def all(self):
    circ = self._circ
    for block_name,loc,config in circ.instances():
      self.block(block_name,loc)