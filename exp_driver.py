import argparse
import scripts.run_experiments as runchip
import scripts.analyze_experiments as analyze
import scripts.visualize_experiments as visualize
import scripts.annotate_experiments as annotate
from scripts.db import ExperimentDB

parser = argparse.ArgumentParser(description='toplevel chip runner.')

subparsers = parser.add_subparsers(dest='subparser_name',
                                   help='compilers/compilation passes.')


scan_subp = subparsers.add_parser('scan', help='scan for new grendel scripts')
list_subp = subparsers.add_parser('list', help='list database entries')
list_subp.add_argument('--bmark', type=str,
                       help='bmark to run.')
list_subp.add_argument('--obj', type=str,
                       help='objective function to run.')


del_subp = subparsers.add_parser('clear', help='delete a benchmark/opt-run')
del_subp.add_argument('--bmark', type=str,
                       help='benchmark to delete.')
del_subp.add_argument('--obj', type=str,
                       help='optimization objective function to delete.')

run_subp = subparsers.add_parser('run', help='run any pending grendel scripts')
run_subp.add_argument('--calibrate', action="store_true",
                       help='calibrate.')
run_subp.add_argument('--email', type=str,
                       help='email address.')
run_subp.add_argument('--native', action='store_true',
                       help='use ttyACM0.')
run_subp.add_argument('--bmark', type=str,
                       help='bmark to run.')
run_subp.add_argument('--obj', type=str,
                       help='objective function to run.')


analyze_subp = subparsers.add_parser('analyze', help='run any pending grendel scripts')
analyze_subp.add_argument('--recompute-energy', action='store_true',
                       help='.')
analyze_subp.add_argument('--recompute-params', action='store_true',
                       help='.')
analyze_subp.add_argument('--recompute-quality', action='store_true',
                       help='.')
analyze_subp.add_argument('--monitor', action='store_true',
                       help='.')
analyze_subp.add_argument('--rank-method', type=str, default='skelter', \
                            help='.')
analyze_subp.add_argument('--rank-pending', action='store_true', help='.')

visualize_subp = subparsers.add_parser('visualize', help='produce graphs.')
visualize_subp.add_argument('type', help='visualization type [rank-vs-quality,correlation,etc]')


annotate_subp = subparsers.add_parser('annotate', help='annotate mismatched graphs.')
annotate_subp.add_argument('bmark', type=str,help='benchmark to annotate.')
annotate_subp.add_argument('--recompute', action='store_true',
                       help='.')


args = parser.parse_args()

if args.subparser_name == "scan":
  db = ExperimentDB()
  print("=== added ===")
  for exp in db.scan():
    print(exp)

elif args.subparser_name == "annotate":
  annotate.execute(args)

elif args.subparser_name == "list":
  db = ExperimentDB()
  print("=== all entries ===")
  for entry in db.get_all():
    if entry.bmark != args.bmark and not args.bmark is None:
      continue
    if entry.objective_fun != args.obj and not args.obj is None:
      continue

    print(entry)

elif args.subparser_name == "clear":
  db = ExperimentDB()
  print("==== deleted ====")
  for entry in db.delete(args.bmark,args.obj):
    print(entry)

elif args.subparser_name == 'run':
  runchip.execute(args)

elif args.subparser_name == 'analyze':
  analyze.execute(args)

elif args.subparser_name == 'visualize':
  visualize.execute(args)
