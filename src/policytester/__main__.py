import sys
from os import access, R_OK
from os.path import isfile
from attrdict import AttrDict # add def
import yaml
import kubernetes
from .kubernetes import *
from .PolicyTests import *
from .SafeLineLoader import *
from .DebugContainerSpec import *
from .PolicyTester import *



def print_help(message=""):
    print("""
Usage:
  # prepare pods for testing 
  policytester prepare <config.yaml>
  
  # execute tests
  policytester execute <config.yaml>
  
  # delete earlier prepared pods
  policytester cleanup <config.yaml>

Tests network policies following the rules in the config file. Tests are done by using the 
current kubectl context. Then using the specifications in the yaml config file, a number
of source pods get extra debug containers from which network tests are done. Thus the tests
are executed from the actual running pods so that the tests are representative. 

For this to work, the policy tester can work in three modes: 
- prepare: prepares the required pods by adding the debug container if it is not already there
- execute: performs the tests
- cleanup: dleetes the pods to which debug containers were added in previous perpare steps. This is
  done based on a label.   

    """, file=sys.stderr)
    sys.exit(1)

def prepare(tester: PolicyTester):
    podstoinstrument = tester.prepare()
    pods = tester.wait_until_debug_container_ready(podstoinstrument, 60)
    if pods:
        print(f"Pods still not ready {str(pods)}")
        sys.exit(1)
    else:
        print("\nAll pods are instrumneted:")
        for pod in podstoinstrument:
            print(f"  {str(pod)}")

def execute(tester: PolicyTester):
    tester.test()
    test_report = tester.test_report
    failed = test_report.failed_tests()

    junit_output = "junit.xml"
    with open(junit_output, "w") as f:
        test_report.write_junit(f)
    print(f"Wrote: {junit_output} with test results")

    if failed:
        for fail in failed:
            print(f"FAIL: {str(dict(fail))}")
        sys.exit(1)

def cleanup(tester: PolicyTester):
    pods = tester.cleanup()
    pods = tester.wait_until_pods_deleted(pods, 60)
    if pods:
        print(f"Pods still not deleted {str(pods)}")
        sys.exit(1)
    else:
        print("\nAll instrumented pods were deleted")


modes = {
    "prepare": prepare,
    "execute": execute,
    "cleanup": cleanup
}

def parse_config(filename: str):
    with open(filename) as f:
        config = yaml.load(f, SafeLineLoader)

    tests = PolicyTests(config)
    # test without config and use lower level API.
    # tests = PolicyTests({})

    if tests.error_messages:
        for error_message in tests.error_messages:
            print(error_message)
        sys.exit(1)


    kubernetes.config.load_kube_config()
    cluster = Cluster()
    debug_container = DebugContainerSpec(
        "debugger", "appropriate/nc", ["sh", "-c", "tail -f /dev/null"],
        tcp_check_command="nc -v -z -i 2 -w 2 {host} {port}",
        udp_check_command="nc -v -zu -i 2 -w 2 {host} {port}"
    )

    tester = PolicyTester(tests, cluster, debug_container)

    return tester

def main():
    sys.argv.pop(0)
    if len(sys.argv) == 0:
        print_help()

    mode = sys.argv.pop(0)
    if mode not in ["prepare", "execute", "cleanup"]:
        print("2")
        print_help(f"Invalid mode '{mode}")

    filename = sys.argv.pop(0)
    if not (isfile(filename) and access(filename, R_OK)):
        print_help(f"Cannot read file '{filename}")
    tester = parse_config(filename)

    if sys.argv:
        print_help()

    modes[mode](tester)






