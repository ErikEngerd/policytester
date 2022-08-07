####!/usr/bin/env python3
import time

from policytester import SafeLineLoader
from policytester import PolicyTests

import yaml
from time import sleep

filename = "policytests.yaml"
with open(filename) as f:
    data = yaml.load(f, SafeLineLoader)

tests = PolicyTests(data)
# test without config and use lower level API.
#tests = PolicyTests({})



for error_message in tests.error_messages:
    print(error_message)

print("Sources:")
print(tests.pods)
print("Addresses")
print(tests.addresses)
print("Connections")
print(tests.connections)
print("Rules")
print(tests.rules)

from kubernetes import config
from policytester import *

config.load_kube_config()
cluster = Cluster()
debug_container = DebugContainerSpec(
    "debugger", "appropriate/nc", ["sh", "-c", "tail -f /dev/null"],
    tcp_check_command="nc -v -z -i 2 -w 2 {host} {port}",
    udp_check_command="nc -v -zu -i 2 -w 2 {host} {port}"
)

tester = PolicyTester(tests, cluster, debug_container)

#%%
pods = tester.cleanup()
tester.wait_until_pods_deleted(pods, 60)

#%%

pods = tester.prepare()
pods = tester.wait_until_debug_container_ready(pods, 60)
print(f"Pods still not ready {str(pods)}")


#%%

tester.test_report.clear()
tester.test()

  #%%

test_report = tester.test_report
failed = test_report.failed_tests()

with open("junit.xml", "w") as f:
    test_report.write_junit(f)
