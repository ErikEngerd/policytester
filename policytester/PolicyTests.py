
from attrdict import AttrDict
import cerberus
import yaml
import re

class PolicyTests:
    SCHEMA = {
        "pods": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": {
                    "name": {"type": "string"},
                    "namespace": {"type": "string"},
                    "podname": {"type": "string"}
                }
            }
        },
        "addresses": {
            "type": "list",
            "schema": {}
        },
        "targets": {
            "type": "list",
            "schema": {}
        },
        "rules": {
            "type": "list",
            "schema": {}
        }
    }

    def __init__(self, config):
        self.config = AttrDict(config)

        v = cerberus.Validator(PolicyTests.SCHEMA)

        v.validate(self.remove_field(self.config, "__line__"))
        self.cerberus_errors = v.errors

        flat_errors = self.errors_to_flat_list(self.cerberus_errors)
        self.error_messages = self.flat_list_to_messages(flat_errors)

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
