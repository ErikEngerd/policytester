import setuptools.wheel

from .PolicyTests import *
from .kubernetes import *
from time import sleep

class PolicyTester:

    def __init__(self, policy_tests: PolicyTests, cluster: Cluster, debug_container: ContainerSpec,
                 labelkey: str = 'policytester.instrumented',
                 labelvalue:str = "true" ):
        self.policy_tests = policy_tests
        self.cluster = cluster
        self.debug_container = debug_container
        self.labelkey = labelkey
        self.labelvalue = labelvalue

    def prepare(self)-> List[Pod]:
        """

        :return: List of pods that have a debug container.
        """
        rules = self.policy_tests.rules.values()

        # gather all used source pods
        print("Gathering source pods")

        source_pods: Set[SinglePodReference] = set()
        for rule in rules:
            source_pods.update(rule.sources)

        all_pods = self.cluster.find_pods()
        eligible_pods = []
        for source_pod in source_pods:
            print(f"Used pod ref: {source_pod}")
            eligible_pod = self.find_eligible_pod(source_pod, all_pods)
            print(f"Eligble pods found: {eligible_pod}")
            if not eligible_pod:
                raise RuntimeError(f"Cannot find eligble pod for {str(source_pod)}")
            eligible_pods.append(eligible_pod)
            if not eligible_pod.has_ephemeral_container(self.debug_container.name):
                print(f"Creating ephemeral debug container in pod {str(eligible_pod)}")
                eligible_pod.label(self.labelkey, self.labelvalue)
                eligible_pod.create_ephemeral_container(self.debug_container)


        return eligible_pods

    def wait_until_ready(self, pods: List[Pod], timeoutSeconds: int):
        count = timeoutSeconds
        while count > 0 and pods:
            pods = [p for p in pods if not p.is_ephemeral_container_running(self.debug_container.name)]
            sleep(1)
            count -= 1
            print("Not ready pods:")
            for p in pods:
                print("  " + str(p))
        return pods

    def test(self):
        all_pods = self.cluster.find_pods()
        for rule in self.policy_tests.rules.values():
            print(f"RULE {rule.name}")
            source_pods = rule.sources
            self.test_rule(source_pods, rule.allowed, True, all_pods)
            self.test_rule(source_pods, rule.denied, False, all_pods)

    def test_rule(self, source_pods: List[SinglePodReference], connections: Connections, allowed: bool, all_pods: List[Pod]):
        for source_pod in source_pods:
            pod = self.find_eligible_pod(source_pod, all_pods)
            for target in connections.connections:
                for port in connections.connections[target]:
                    address_or_pod = connections.connections[target][port]
                    if isinstance(address_or_pod, SinglePodReference):
                        running_pod = self.find_pod_reference(address_or_pod, all_pods)
                        if running_pod:
                            pod_ip = running_pod.podspec.status.pod_ip
                            print(f"  {str(pod):<50} {pod_ip:<20} {str(port):<10} {str(allowed):<10} {running_pod.namespace()}/{running_pod.name()}")
                        else:
                            raise RuntimeError(f"Cannot find target pod for {str(address_or_pod)}")
                    else:
                        print(f"  {str(pod):<50} {address_or_pod:<20} {str(port):<10} {str(allowed):<10}")


    def find_pod_reference(self, pod: SinglePodReference, all_pods) -> Union[Pod, None]:
        pods = [p for p in all_pods if p.namespace() == pod.namespace and p.name().startswith(pod.podname)]
        if pods:
           return pods[0]
        return None


    def cleanup(self):
        pods = self.cluster.find_pods()
        pods = [p for p in pods if p.labels().get(self.labelkey, None) == self.labelvalue]
        for pod in pods:
            print(f"Deleting pod {pod.namespace()}/{pod.name()}")
            pod.delete()


    def find_eligible_pod(self, source_pod: SinglePodReference, all_pods: List[Pod], debug=False) -> Pod:
        pods = [p for p in all_pods if p.name().startswith(source_pod.podname)]

        # pods with the mentioned debug container
        debug_pods = [p for p in pods if p.has_ephemeral_container(self.debug_container.name)]
        if debug_pods:
            # now find a container with a running debug pod
            working_debug_pods = [p for p in debug_pods if p.is_ephemeral_container_running(self.debug_container.name)]
            if not working_debug_pods:
                if debug:
                    print(f"Pod with debug container found {str(debug_pods)} but the debug container is not running")
                return debug_pods[0]
            else:
                if debug:
                    print(f"Existing pod with debug container already running was found {str(debug_pods[0])}")
                return working_debug_pods[0]
        return pods[0] if pods else None



