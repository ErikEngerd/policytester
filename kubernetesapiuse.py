
from kubernetes import client, config, stream
from kubernetes.client.exceptions import ApiException

config.load_kube_config()

corev1 = client.CoreV1Api()

pods = corev1.list_namespaced_pod("exposure")

pod = next(p for p in pods.items if p.metadata.name.startswith("httpd-wamblee-org"))

import kubernetes
print(kubernetes.__version__)

#%% creating a debug container.

body = client.models.V1EphemeralContainer(
    image="centos:7",
    name="debugger",
    command=["sh", "-c", "sleep 1000000"])
body = {
    "spec": {
        "ephemeralContainers": [
            body.to_dict()
        ]
    }
}
res = corev1.patch_namespaced_pod_ephemeralcontainers(pod.metadata.name, pod.metadata.namespace, body, _preload_content=False)
print(f"HTTP status: {res.status}")


#%%

# test to see whether output is immediately availabl on the client side, even if it is not line-terminated.

try:

    exec_command = ["bash" , "-c", '''
      echo before;
      count=0
      while [[ $count -lt 5 ]]
      do
        echo -n "$count."
        sleep 1 
        count="$(( $count + 1 ))"
      done 
      ls -l
      exit 3
    ''']

    res = stream.stream(corev1.connect_get_namespaced_pod_exec,
                  pod.metadata.name,
                  pod.metadata.namespace,
                  container = "debugger",
                  command=exec_command,
                  stderr=True, stdin=False,
                  stdout=True, tty=False,
                  _preload_content=False)
    #print(f"HTTP status: {res.status}")

    print("Start reading result")
    while res.is_open():
        res.update(timeout=1)
        if res.peek_stdout():
            #print(f"STDOUT: \n{res.read_stdout()}")
            print(res.read_stdout(), end="")
        if res.peek_stderr():
            print(f"STDERR: \n{res.read_stderr()}")

    res.close()

    if res.returncode != 0:
        print(f"Command exit code {res.returncode}")
except ApiException as e:
    print(f"Error executing request: {e.reason}")

#%% get pod status

from attrdict import AttrDict

res = corev1.list_namespaced_pod("exposure", field_selector=f"metadata.name={pod.metadata.name}")
res = res.items
assert len(res) == 1
res = res[0]
print(res.status.ephemeral_container_statuses[0].state)

#%%
res = AttrDict(res.to_dict())
