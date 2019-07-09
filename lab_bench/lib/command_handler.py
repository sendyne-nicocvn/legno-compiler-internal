import lab_bench.lib.command as cmd
import sys


def execute(state,line):
    if line.startswith("#"):
        print(line)
        print("<comment, skipping..>")
        return True

    command_obj = cmd.parse(line)
    if command_obj is None:
        print("<unknown command: (%s)>" % line)
        return False

    if not command_obj.test():
        print("[error] %s" % command_obj.error_msg())
        return False


    if isinstance(command_obj,cmd.Command):
        command_obj.execute(state)
        return True

    else:
        print("unhandled..")
        print(command_obj)
        return False

def main_stdout(state):
    while True:
        line = input("ardc>> ")
        if line == "quit":
            sys.exit(0)
        elif line.strip() == "":
            continue

        execute(state,line)


def main_dump_db(state):
    keys = {}
    for data in state.state_db.get_all():
        key = (data.block,data.loc)
        if not key in keys:
            keys[key] = data

    for key,obj in keys.items():
        obj.write_dataset(state.state_db)



def main_script_profile(state,filename, \
                        recompute=False,
                        clear=False,
                        bootstrap=False,
                        n=5):
    with open(filename,'r') as fh:
        for idx,line in enumerate(fh):
            if line == "quit":
                sys.exit(0)
            elif line.strip() == "":
                continue

            if line.startswith("#"):
                print(line)
                print("<comment, skipping..>")

            command_obj = cmd.parse(line)
            succ = cmd.profile(state,command_obj, \
                               recompute=recompute,
                               bootstrap=bootstrap,
                               clear=clear,
                               n=5)


def main_script_calibrate(state,filename, \
                          characterize=True,
                          recompute=False,
                          targeted=False):
    successes = []
    failures = []
    with open(filename,'r') as fh:
        for idx,line in enumerate(fh):
            if line == "quit":
                sys.exit(0)
            elif line.strip() == "":
                continue

            if line.startswith("#"):
                print(line)
                print("<comment, skipping..>")

            print("==== CALIBRATE BLOCK ====")
            command_obj = cmd.parse(line)
            succ = cmd.calibrate(state,command_obj, \
                                 recompute=recompute,
                                 targeted_calibrate=targeted,
                                 targeted_measure=targeted)
            if succ is None:
                continue

            scale = 2.0
            while not succ and scale < 200.0:
                succ = cmd.calibrate(state,command_obj, \
                                     recompute=recompute,
                                     targeted_calibrate=targeted,
                                     targeted_measure=targeted,
                                     error_scale=scale)
                scale *= 2.0


            if succ:
                successes.append(command_obj)
            else:
                failures.append(command_obj)

    total = len(successes) + len(failures)
    print("=== Successes [%d/%d] ===" % (len(successes), total))
    for succ in successes:
        print(succ)

    print("=== Failures [%d/%d] ===" % (len(failures),total))
    for fail in failures:
        print(fail)

    return len(failures) == 0

def main_script(state,filename):
    with open(filename,'r') as fh:
        for idx,line in enumerate(fh):
            print("ardc>> %s" % line.strip())
            if line == "quit":
                sys.exit(0)
            elif line.strip() == "":
                continue
            if not (execute(state,line.strip())):
                sys.exit(1)

