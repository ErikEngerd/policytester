import yaml

class SafeLineLoader(yaml.SafeLoader):
    """
    Parse yaml with line number added as __line__ attributes to the dictionaries.
    See https://stackoverflow.com/questions/13319067/parsing-yaml-return-with-line-number
    """
    def construct_mapping(self, node, deep=False):
        mapping = super(SafeLineLoader, self).construct_mapping(node, deep=deep)
        # Add 1 so line numbering starts at 1
        mapping['__line__'] = node.start_mark.line + 1
        return mapping

