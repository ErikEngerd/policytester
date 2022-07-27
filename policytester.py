####!/usr/bin/env python3

from policytester import SafeLineLoader
from policytester import PolicyTests

import yaml
import sys

filename = "policytests.yaml"
with open(filename) as f:
    data = yaml.load(f, SafeLineLoader)

tests = PolicyTests(data)


for error_message in tests.error_messages:
    print(error_message)

tests.sources


#%%
sys.exit(1)

addresses = AttrDict()
address_groups = AttrDict()
source_addresses_used = set()


def validate_keys(context, actual, expected):
    actual = sorted(actual)
    ok = False
    for exp in expected:
        if actual == sorted(exp):
            ok = True

    if not ok:
        msg = f"ERROR: wrong keys for {context}: {str(actual)}: expected one of: \n"
        for exp in expected:
            msg += "    " + str(exp) + "\n"
        print(msg)
        sys.exit(1)

    return sorted(actual) == sorted(expected)

def validate_main(data):
    validate_keys("main document", data, [["addresses", "addressGroups", "rules"]])

def validate_address_group(group):
    validate_keys(f"addressGroup '{group.name}'", group, [["name", "addresses"]])

def validate_port(context, port):
    validate_keys(context, port, [["port"], ["port", "type"]])
    if not "type" in port:
        port.type = "TCP"
    else:
        if port.type not in ["TCP", "UDP"]:
            print(f"ERROR {context}: Unknown port type {port.type}: allowed are TCP and UDP")
            sys.exit(1)

def validate_address(actual):
    if actual.name in addresses:
        print(f"ERROR: duplicate address '{actual.name}'")
        sys.exit(1)
    ADDRESS_KEYS_POD = ["name", "namespace", "pod", "ports"]
    ADDRESS_KEYS_HOST = ["name", "host", "ports"]
    validate_keys(f"address '{actual.name}'", actual, [ADDRESS_KEYS_POD, ADDRESS_KEYS_HOST])

    ports = []
    for port in actual.ports:
        validate_port(f"address '{actual.name}'", port)
        ports.append(port)

    actual.ports = ports

def process_address_reference(rule, ref, is_source = False):
    if ref not in addresses and ref not in address_groups:
        print(f"ERROR: Rule '{rule.name}' refers to non-existent address or addressgroup '{ref}'")
        sys.exit(1)
    if ref in addresses:
        if is_source:
            source_addresses_used.add(ref)
        return [addresses[ref]]
    else:
        if is_source:
            for address in address_groups[ref].addresses:
                source_addresses_used.add(address.name)
        return [*address_groups[ref].addresses]

def process_address_list(rule, refs):
    resolved = []
    for ref in refs:
        resolved = resolved + process_address_reference(rule, ref)
    return resolved

def validate_rule(rule):
    validate_keys(f"rule {rule.name}", rule,
                  [["name", "from", "allowed", "denied"],
                   ["name", "from", "allowed"],
                   ["name", "from", "denied"],
                   ["name", "from"]])

    if "allowed" not in rule:
        rule.allowed = []
    if "denied" not in rule:
        rule.denied = []

    rule.source = process_address_reference(rule, rule["from"], True)
    del rule["from"]
    rule.allowed = process_address_list(rule, rule.allowed)
    rule.denied = process_address_list(rule, rule.denied)


validate_main(data)


for address in data.addresses:
    keys = address.keys()
    validate_address(address)
    addresses[address.name] = address


for group in data.addressGroups:
    if group.name in addresses:
        print(f"ERROR: group name '{group.name}' is already used by an address")
        sys.exit(1)
    if group.name in address_groups:
        print(f"ERROR: group name '{group.name}' is already used by an address group")
        sys.exit(1)
    validate_address_group(group)
    group_addresses = []
    for address in group.addresses:
        if address not in addresses:
            print(f"ERROR: unknown address reference '{address}' in addressGroup '{group.name}'")
            sys.exit(1)
        group_addresses.append(addresses[address])

    group.addresses = group_addresses
    address_groups[group.name] = group

if type(data.rules) != tuple:
    print(f"ERROR: rules should not have any attributes")
    sys.exit(1)

rules = []
for rule in data.rules:
    validate_rule(rule)
    rules.append(rule)

