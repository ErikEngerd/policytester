import sys
import time
from attrdict import AttrDict
import datetime
import re

class TestReport:

    def __init__(self, name = "NetworkPolicyTests"):
        self.name = name
        self.clear()

    def clear(self):
        self.ntests = 0
        self.nfail = 0
        self.suites = []
        self.t0 = time.time()

    def start_suite(self, name):
        print(f"RULE {name}")
        self.current_suite = AttrDict()
        self.current_suite.id = name
        self.current_suite.name = name
        self.current_suite.tests = self.ntests
        self.current_suite.failures = self.nfail
        self.current_suite.t0 = time.time()
        self.current_suite.timestamp = datetime.datetime.now()
        self.current_suite.cases = []
        self.suites.append(self.current_suite)

    def end_suite(self):
        self.current_suite.tests = self.ntests - self.current_suite.tests
        self.current_suite.failures = self.nfail - self.current_suite.failures
        self.current_suite.time = time.time() - self.current_suite.t0
        del self.current_suite.t0
        print(f"  PASS={self.current_suite.tests - self.current_suite.failures} FAIL={self.current_suite.failures} TIME={self.current_suite.time}")

    def start_case(self, name):
        print(f"  CASE {name}", end="")
        self.current_case = AttrDict()
        self.current_case.name = name
        self.current_case.suite = self.current_suite.name
        self.current_case.t0 = time.time()
        self.current_case.tests = self.ntests
        self.current_case.failures = self.nfail
        self.current_suite["cases"].append(self.current_case)

    def end_case(self, ok: bool, output: str):
        self.ntests += 1
        self.nfail += not ok
        self.current_case.tests = self.ntests - self.current_case.tests
        self.current_case.failures = self.nfail - self.current_case.failures
        self.current_case.time = time.time() - self.current_case.t0
        self.current_case.ok = ok
        self.current_case.output = output
        del self.current_case.t0
        print(f"  PASS={self.current_case.tests - self.current_case.failures} FAIL={self.current_case.failures} TIME={self.current_case.time}")


    def finish(self):
        self.time = time.time() - self.t0
        print(f"TOTAL PASS={self.ntests} FAIL={self.nfail} TIME={self.time}")


    def failed_tests(self):
        res = []
        for suite in self.suites:
            if not suite.failures:
                continue
            for case in suite.cases:
                if case.failures:
                    res.append(case)
        return res

    def write_junit(self, f):
        original = sys.stdout
        sys.stdout = f
        try:
            print(f"<testsuites>")
            id = 0
            for suite in self.suites:
                systemout = ""
                id += 1
                ts = suite.timestamp.isoformat()
                ts = re.sub("[.].*$", "", ts)
                print(f"  <testsuite package='networkpolicy' name='{suite.name}' hostname='pod' id='{id}' tests='{suite.tests}' failures='{suite.failures}' timestamp='{ts}' errors='0' time='{suite.time}'>")
                print(f"    <properties>")
                print(f"    </properties>")
                for case in suite.cases:
                    print(f"    <testcase name='{case.name}' classname='{suite.id}' time='{case.time}'>")
                    if not case.ok:
                        print(f"      <failure message='failed' type='FAIL'>")
                        print(f"         {self.cdata(case.output)}")
                        print(f"      </failure>")
                    systemout += "="*80 + "\n" + f"CASE {suite.name} {case.name}\n\n{case.output}\n\n\n"
                    print(f"    </testcase>")
                print(f"    <system-out>{self.cdata(systemout)}</system-out>")
                print(f"    <system-err></system-err>")
                print(f"  </testsuite>")
            print("</testsuites>")
        finally:
            sys.stdout = original

    def cdata(self, s):
        return f"<![CDATA[{s}]]>"
