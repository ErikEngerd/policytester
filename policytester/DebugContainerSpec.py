from typing import List

from .kubernetes import ContainerSpec
from .PolicyTests import Port

class DebugContainerSpec(ContainerSpec):
    def __init__(self,  name: str, image: str, command: List[str],
                 tcp_check_command,
                 udp_check_command):
        """

        :param name:
        :param image:
        :param command:
        :param tcp_check_command: command (str or array) with f-string like {host} and {port}
        :param udp_check_command: command (str or array) with f-string like {host} and {port}
        """
        super().__init__(name, image, command)
        self.tcp_check_command = self._command_to_array(tcp_check_command)
        self.udp_check_command = self._command_to_array(udp_check_command)

    def _command_to_array(self, cmd):
        if type(cmd) == str:
            return ["sh", "-c", cmd]
        elif type(cmd) == list:
            return cmd
        else:
            raise ValueError(f"Type error, command must be of type string or list of strings {str(cmd)}")

    def get_command(self, host: str, port: Port):
        if port.type == "TCP":
            return self._format(self.tcp_check_command, host, port.port)
        elif port.type == "UDP":
            return self._format(self.udp_check_command, host, port.port)
        else:
            raise ValueError("Invalid port type '{str(port)}")

    def _format(self, cmd: str, host: str, port: int):
        return [s.format(host=host, port=port) for s in cmd]
