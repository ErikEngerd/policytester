import functools
from time import time
from typing import List, Dict

from kubernetes import client, stream
from kubernetes.client import V1Pod
from kubernetes.client.exceptions import ApiException


class ContainerSpec:
    def __init__(self, name: str, image: str, command: List[str]):
        self.name = name
        self.image = image
        self.command = command

class Pod:
    def __init__(self, podspec: V1Pod):
        self.corev1 = client.CoreV1Api()
        self.podspec = podspec

    def is_valid(self) -> bool:
        return self.podspec is not None

    def valid_only(method):
        @functools.wraps(method)
        def decorator(self, *args, **kwargs):
            if not self.is_valid():
                raise RuntimeError("Attempt to invoke method on deleted pod")
            return method(self, *args, **kwargs)

        return decorator

    def refresh_after(method):
        @functools.wraps(method)
        def decorator(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            self.refresh()
            return result

        return decorator

    def refresh_before(method):
        @functools.wraps(method)
        def decorator(self, *args, **kwargs):
            self.refresh()
            result = method(self, *args, **kwargs)
            return result

        return decorator

    @valid_only
    def name(self) -> str:
        return self.podspec.metadata.name

    @valid_only
    def namespace(self) -> str:
        return self.podspec.metadata.namespace

    def clusterIP(self) -> str:
        return self.podspec.status.pod_ip

    @refresh_before
    @valid_only
    def phase(self) -> str:
        return self.podspec.status.phase

    @refresh_before
    @valid_only
    def is_running(self) -> bool:
        return self.phase() == "Running"

    @valid_only
    def labels(self) -> Dict[str, str]:
        return self.podspec.metadata.labels

    @valid_only
    @refresh_after
    def label(self, key: str, value: str = None):
        metadata = {
            "labels": {
                key: value
            }
        }
        body = client.V1Pod(metadata=metadata)
        self.corev1.patch_namespaced_pod(self.name(), self.namespace(), body)
        self.refresh()

    @valid_only
    def has_ephemeral_container(self, name: str):
        status = self._get_ephemeral_container_status(name)
        return status is not None

    @refresh_before
    @valid_only
    def is_ephemeral_container_running(self, name: str):
        status = self._get_ephemeral_container_status(name)
        if status:
            return status.state.running is not None
        return False

    def _get_ephemeral_container_status(self, name: str):
        statuses = self.podspec.status.ephemeral_container_statuses
        if statuses:
            for container in statuses:
                if container.name == name:
                    return container
        return None

    def refresh(self):
        if not self.is_valid():
            return
        pods = self.corev1.list_namespaced_pod(namespace=self.namespace(),
                                               field_selector=f"metadata.name={self.name()}")
        if len(pods.items) > 1:
            raise RuntimeError("programming error")
        elif len(pods.items) == 0:
            self.podspec = None
        else:
            if self.podspec.metadata.uid == pods.items[0].metadata.uid:
                self.podspec = pods.items[0]
            else:
                self.podspec = None

    @refresh_after
    def create_ephemeral_container(self, container_spec: ContainerSpec):
        """
        Create ephemeral container.
        :param name:
        :param image:
        :param command:  Array syntax ["sh", "-c", "sleep 1000000"]
        :return:
        """
        body = client.models.V1EphemeralContainer(
            image=container_spec.image,
            name=container_spec.name,
            command=container_spec.command)
        body = {
            "spec": {
                "ephemeralContainers": [
                    body.to_dict()
                ]
            }
        }
        res = self.corev1.patch_namespaced_pod_ephemeralcontainers(
            self.podspec.metadata.name,
            self.podspec.metadata.namespace,
            body,
            _preload_content=False)
        status = res.status
        if status != 200:
            raise RuntimeError("Could not create ephemeral container '{name}' in pod {str(self)}")

    @refresh_after
    def exec(self, command: List[str], container: str = None, timeoutSeconds: int = 1000000, debug: bool = False):
        """
        Executes a command synchronously
        :param command: command to execute
        :param container: container in which to execute command
        :return: tuple (exit status (int), output (str))
        """

        output = ""

        try:
            res = stream.stream(self.corev1.connect_get_namespaced_pod_exec,
                                self.podspec.metadata.name,
                                self.podspec.metadata.namespace,
                                container=container,
                                command=command,
                                stderr=True, stdin=False,
                                stdout=True, tty=False,
                                _preload_content=False)
            maxtime = time() + timeoutSeconds
            while res.is_open() and time() < maxtime:
                res.update(timeout=1)
                if res.peek_stdout():
                    out = res.read_stdout()
                    output += out
                    if debug:
                        print(out, end="")
                if res.peek_stderr():
                    err = res.read_stderr()
                    output += err
                    if debug:
                        print(err, end="")

            res.close()

            if time() >= maxtime:
                return (None, output)

            return res.returncode, output
        except ApiException as e:
            print(f"Error executing request: {e.reason}")
            raise (e)

    @refresh_after
    def delete(self):
        self.corev1.delete_namespaced_pod(self.name(), self.namespace())

    def __repr__(self):
        return f"{self.namespace()}/{self.name()}"


class Cluster:
    def __init__(self):
        self.corev1 = client.CoreV1Api()

    def find_pods(self, namespace=None) -> List[Pod]:
        if namespace is None:
            pods = self.corev1.list_pod_for_all_namespaces()
        else:
            pods = self.corev1.list_namespaced_pod(namespace)
        return [Pod(p) for p in pods.items]
