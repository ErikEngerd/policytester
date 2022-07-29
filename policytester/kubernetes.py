
from kubernetes import client, config, stream
from kubernetes.client.exceptions import ApiException
from time import time


class Cluster:
    def __init__(self):
        self.corev1 = client.CoreV1Api()

    def find_pods(self, namespace = None):
        if namespace is None:
            pods = self.corev1.list_pod_for_all_namespaces()
        else:
            pods = self.corev1.list_namespaced_pod(namespace)
        return [Pod(p) for p in pods.items]


class Pod:
    def __init__(self, podspec):
        self.corev1 = client.CoreV1Api()
        self.podspec = podspec

    def name(self):
        return self.podspec.metadata.name

    def namespace(self):
        return self.podspec.metadata.namespace

    def phase(self):
        return self.podspec.status.phase

    def is_running(self):
        return self.phase() == "Running"

    def labels(self):
        return self.podspec.metadata.labels

    def label(self, key, value = None):
        metadata = {
            "labels": {
                key: value
            }
        }
        body = client.V1Pod(metadata = metadata)
        self.corev1.patch_namespaced_pod(self.name(), self.namespace(), body)
        self.refresh()

    def has_ephemeral_container(self, name):
        status = self._get_ephemeral_container_status(name)
        return status is not None

    def is_ephemeral_container_running(self, name):
        status = self._get_ephemeral_container_status(name)
        if status:
            return status.state.running is not None
        return False

    def _get_ephemeral_container_status(self, name):
        statuses = self.podspec.status.ephemeral_container_statuses
        if statuses:
            for container in statuses:
                if container.name == name:
                    return container
        return None

    def refresh(self):
        pods = self.corev1.list_namespaced_pod(namespace = self.namespace(), field_selector = f"metadata.name={self.name()}")
        if len(pods.items) > 1:
            raise RuntimeError("programming error")
        elif len(pods.items) == 0:
            self.podspec = None
        else:
            if self.podspec.metadata.uid == pods.items[0].metadata.uid:
                self.podspec = pods.items[0]
            else:
                self.podspec = None

    def create_ephemeral_container(self, name, image, command):
        """
        Create ephemeral container.
        :param name:
        :param image:
        :param command:  Array syntax ["sh", "-c", "sleep 1000000"]
        :return:
        """
        body = client.models.V1EphemeralContainer(
            image=image,
            name=name,
            command=command)
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

    def exec(self, command, container = None, timeoutSeconds = 1000000, debug=False):
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
            raise(e)

    def delete(self):
        self.corev1.delete_namespaced_pod(self.name(), self.namespace())

    def __repr__(self):
        return f"{self.namespace()}/{self.name()}"

