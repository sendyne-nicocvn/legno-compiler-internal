from compiler import arco, jaunt
import argparse

#import conc
#import srcgen

def compile(board,problem):
    files = []
    prob = benchmark1()
    for idx1,idx2,circ in compile(hdacv2_board,prob):
        srcgen.Logger.DEBUG = True
        srcgen.Logger.NATIVE = True
        circ.name = "%s_%d_%d" % (circ_name,idx1,idx2)
        labels,circ_cpp, circ_h = srcgen.generate(circ)
        files = []
        files.append((labels,circ.name,circ_cpp,circ_h))
        srcgen.write_file(experiment,files,out_name,
                        circs=[circ])



parser = argparse.ArgumentParser(description='Legno compiler.')

subparsers = parser.add_subparsers(dest='subparser_name',
                                   help='compilers/compilation passes.')

arco_subp = subparsers.add_parser('arco', help='generate circuit')
arco_subp.add_argument('benchmark', type=str,help='benchmark to compile')
arco_subp.add_argument('--xforms', type=int,default=3,
                       help='number of abs circuits to generate.')
arco_subp.add_argument('--abs-circuits', type=int,default=100,
                       help='number of abs circuits to generate.')
arco_subp.add_argument('--conc-circuits', type=str,default=3,
                       help='number of conc circuits to generate.')
arco_subp.add_argument('--output-dir', type=str,help='output directory to output files to.')



jaunt_subp = subparsers.add_parser('jaunt', help='scale circuit parameters.')
jaunt_subp.add_argument('benchmark', type=str,help='benchmark to compile')
jaunt_subp.add_argument('--experiment', type=str,help='experiment to run')
jaunt_subp.add_argument('--input-dir', type=str,help='output directory to output files to.')
jaunt_subp.add_argument('--noise', type=str,help='perform noise analysis.')



args = parser.parse_args()
if args.subparser_name == "arco":
    from chip.hcdc import board as hdacv2_board
    import bmark.bmarks as bmark

    problem = bmark.get_bmark(args.benchmark)

    for indices,conc_circ in \
        enumerate(arco.compile(hdacv2_board,
                               problem,
                               depth=args.xforms,
                               max_abs_circs=args.abs_circuits,
                               max_conc_circs=args.conc_circuits)):
        print(indices)
        print(conc_circ)
        raw_input()
