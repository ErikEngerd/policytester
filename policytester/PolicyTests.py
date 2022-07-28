import re

import cerberus
import yaml
from attrdict import AttrDict


class PolicyTests:
    OPTIONAL_LIST_OF_STRINGS = {
        "type": "list",
        "schema": {"type": "string"},
        "required": False
    }
    SCHEMA = {
        "pods": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": {
                    "name": {"type": "string"},
                    "namespace": {"type": "string", "required": False},
                    "podname": {"type": "string", "required": False},
                    "pods": OPTIONAL_LIST_OF_STRINGS
                }
            }
        },
        "addresses": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": {
                    "name": {"type": "string"},
                    "hosts": OPTIONAL_LIST_OF_STRINGS,
                    "addresses": OPTIONAL_LIST_OF_STRINGS
                }
            }
        },
        "connections": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": {
                    "name": {"type": "string"},
                    "pods": OPTIONAL_LIST_OF_STRINGS,
                    "addresses": OPTIONAL_LIST_OF_STRINGS,
                    "targets": OPTIONAL_LIST_OF_STRINGS,
                    "ports": {
                        "type": "list",
                        "required": False,
                        "schema": {
                            "type": "dict",
                            "schema": {
                                "port": {"anyof": [{"type": "string"}, {"type": "integer"}]},
                                "type": {"type": "string", "required": False, "allowed": ["TCP", "UDP"],
                                         "default": "TCP"}
                            }
                        }
                    },
                    "targets": OPTIONAL_LIST_OF_STRINGS
                }
            }
        },
        "rules": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": {
                    "name": {"type": "string"},
                    "from": OPTIONAL_LIST_OF_STRINGS,
                    "allowed": OPTIONAL_LIST_OF_STRINGS,
                    "denied": OPTIONAL_LIST_OF_STRINGS
                }
            }
        }
    }

    def __init__(self, config):
        self.config = AttrDict(config)

        v = cerberus.Validator(PolicyTests.SCHEMA, require_all=True)

        v.validate(self.remove_field(self.config, "__line__"))
        self.cerberus_errors = v.errors

        flat_errors = self.errors_to_flat_list(self.cerberus_errors)
        self.error_messages = self.flat_list_to_messages(flat_errors)

        self.normalized_data = v.document

        # pod names must be unique and pod must have either podname of pods element. In case of pods element, the
        # references must refer to pod names defined before.

        self.setup_pods()
        self.setup_addresses()
        self.setup_connections()

    def setup_pods(self):
        self.pods = {}
        for pod in self.config.pods:
            if "podname" in pod:
                # single pod
                if "pods" in pod:
                    self.error_messages.append(
                        f"LINE {pod['__line__']}: Pod '{pod.name}' cannot have 'pods' set because it is a single pod")
                else:
                    if pod.name in self.pods:
                        self.error_messages.append(
                            f"LINE {pod['__line__']}: A pod with name '{pod.name}' already exists")
                    else:
                        podsource = Pod(pod.name, pod.namespace, pod.podname)
                        self.pods[pod.name] = podsource

            else:
                # pod group
                if "podname" in pod or "namespace" in pod:
                    self.error_messages.append(
                        f"LINE {pod['__line__']}: Pod '${pod.name}' is a pod group and may not have 'namespace' or 'podname' defined")
                if 'pods' not in pod:
                    self.error_messages.append(
                        f"LINE {pod['__line__']}: Pod '${pod.name}' expected pod group but 'pods' element is missing")
                podlist = set()
                for podname in pod.pods:
                    podlist.update(self.get_pods(f"LINE {pod['__line__']}: Pod '{pod.name}'", podname))
                podgroup = PodGroup(pod.name, podlist)
                self.pods[pod.name] = podgroup

    def get_pods(self, context, reference):
        if reference not in self.pods:
            self.error_messages.append(
                f"LINE {context}: pod or pod group with name '{reference}' not found")
            return []
        return self.pods[reference].pods()

    def setup_addresses(self):
        self.addresses = {}

        # address names must be unique
        for address in self.config.addresses:
            if address.name in self.pods:
                self.error_messages.append(f"LINE {address['__line__']}: duplicate address '{address.name}, there is already a pod definition with that name")
            elif address.name in self.addresses:
                self.error_messages.append(f"LINE {address['__line__']}: duplicate address '{address.name}'")
            else:
                if "hosts" not in address:
                    address.hosts = []
                if "addresses" not in address:
                    address.addresses = []
                hostlist = address.hosts
                for host in address.addresses:
                    if host not in self.addresses:
                        self.error_messages.append(f"LINE {address['__line__']}: address reference '{host}' not found")
                    else:
                        hostlist += self.addresses[host].hosts
                self.addresses[address.name] = Addresses(address.name, hostlist)

    def setup_connections(self):
        self.connections = {}

        for connection in self.config.connections:
            if connection.name in self. connections:
                self.error_messages.append(
                    f"LINE {address['__line__']}: duplicate address '{address.name}, there is already a pod definition with that name")

    def remove_field(self, x, field):
        if isinstance(x, dict):
            x = x.copy()
            if field in x:
                del x[field]
            for k in x:
                x[k] = self.remove_field(x[k], field)
            return x

        elif isinstance(x, list) or isinstance(x, tuple):
            return [self.remove_field(k, field) for k in x]
        else:
            return x

    def errors_to_flat_list(self, x, path=[]):
        """

        :param x:
        :return: List of tuples of (path, msg) where path is a list of
                 str and int indicating a path to the error
        """

        res = []

        if isinstance(x, dict):
            for k in x:
                if type(k) == str:
                    res += self.errors_to_flat_list(x[k], path + [k])
                elif type(k) == int:
                    res += self.errors_to_flat_list(x[k], path + [k])
                else:
                    raise RuntimeError("programming error, map traversal")
        elif isinstance(x, list) or isinstance(x, tuple):
            for k in x:
                if type(k) == dict:
                    res += self.errors_to_flat_list(k, path)
                elif type(k) == str:
                    res.append((path, k))
                else:
                    raise RuntimeError("programming error, array traversal")
        return res

    def flat_list_to_messages(self, flat_errors):
        res = []
        for flat_error in flat_errors:
            path = flat_error[0]
            msg = flat_error[1]
            i = 0
            line = -1
            context = self.config
            last_context_with_line_info = context
            for j in range(len(path)):
                if type(path[j]) == str and path[j] not in context:
                    break

                context = context[path[j]]
                if isinstance(context, dict) and "__line__" in context:
                    line = context["__line__"]
                    last_context_with_line_info = context
                    i = j

            errorpath = "".join([x if type(x) == str else '[' + str(x) + ']' for x in path[:i + 1]])
            remainingpath = "".join([x if type(x) == str else '[' + str(x) + ']' for x in path[i + 1:]])

            yaml_context = yaml.dump(self.remove_field(last_context_with_line_info, "__line__"))
            yaml_context = re.sub("^", "    ", yaml_context, flags=re.MULTILINE)
            yaml_context = "  CONTEXT: \n" + yaml_context
            res.append(f"ERROR: line {line}: {errorpath}: '{remainingpath}': {msg}\n{yaml_context}")

        return res


class PodReference:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        if isinstance(other, PodReference):
            return self.name == other.name
        else:
            return False

    def __hash__(self):
        return hash(self.name)

    def pods(self):
        raise NotImplementedError()


class Pod(PodReference):
    def __init__(self, name, namespace, podname):
        super().__init__(name)
        self.namespace = namespace
        self.podname = podname

    def pods(self):
        return [self]

    def __repr__(self):
        return f"pod: {self.name}: {self.namespace}/{self.podname}"


class PodGroup(PodReference):
    def __init__(self, name, pods):
        super().__init__(name)
        self.pods = pods

    def pods(self):
        return self.pods

    def __repr__(self):
        s = f"pod: {self.name}["
        for pod in self.pods:
            s += str(pod) + ","
        s += "]"
        return s

class Addresses:
    def __init__(self, name, hosts):
        self.name = name
        self.hosts = hosts

    def __repr__(self):
        s = f"Address: {self.name}: ["
        s += ", ".join(self.hosts)
        s += "]"
        return s

class Port:
    def __init__(self, port, type):
        self.port = port
        self.type = type

class Connection:
    def __init__(self, pods, addresses, ports):
        self.pods = pods
        self.addresses = addresses
        self.ports = ports


