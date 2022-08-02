import time
from attrdict import AttrDict

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



