

# Kubernetes Network Policy Tester

Network security is often overlooked in Kubernetes. Without network policies 
kubernetes deployments are basically identical to a traditional infrastructure 
without firewalls. Network policies in Kubernetes
can provide the required network segmentation, see
[the introduction post](https://brakkee.org/site/index.php/2022/07/23/securing-network-communication-on-kubernetes-using-network-policies/).

However, network policies must be verified since it is easy to make a mistake in configuration. 
This is 
where the policy tester comes in. The tool is written in python and uses existing pods 
running in a kubernetes cluster to verify network commmunication. It does this by 
attaching an ephemeral container to an existing pod so it can verify communications from
this pod to other pods and the internet. Ephemeral contains are a beta feature since 
kubernetes 1.23 which allows to add new containers to existing pods. The main purpose of 
this is for debugging (testing), so these containers are sometimes also called debug
containers. 

This approach allows to test network communication 
within the cluster and also from within the cluster to the internet. The advantage of 
using ephemeral containers is that it uses existing pods, so the testing environment is 
identical to the actual environmnet, since no separate test pods are created. Therefore,
the tests are representative of the actual situation. The only thing that cannot be tested
are rules from traffic coming in from outside the cluster to the cluster.

## Installation 

```angular2html
pip install policytester
```

## Usage

```angular2html
# prepare pods by adding debug containers to them
policytester prepare tests.yaml

# execute tests for pods
policytester execute tests.yaml

# delete pods that got debug containers attached in any previous prepare steps.
policytester cleanup tests.yaml
```

The separation of prepare, execute, and cleanup allows for tests toe be rerun without
having to wait for instrumentation of pods. 

The current version of the policy tester uses the default kubectl context to connect to.
Future versions of the tool can provide ways to explicitly define a connection to a 
cluster. 

## Example

### Verify that a pod can reach the java maven repository but (most likely) not any other hosts 

```angular2html

pods:
  - name: httpd-wamblee-org
    namespace: exposure
    podname: httpd-wamblee-org
    
addresses:
  - name: internet
    hosts:
      - github.com
      - google.com
  - name: maven-repo
    hosts:
      - repo1.maven.org

connections:
  - name: internet
    addresses:
      - internet
    ports:
      - port: 80
      - port: 443
  - name: maven-repo
    addresses:
      - maven-repo
    ports:
      - port: 80
      - port: 443

rules:
  - name: internet-access
    from: 
      - httpd-wamblee-org
    allowed:
      - maven-repo
    denied:
      - internet
```

A more complete example is [here](policytests.yaml).

## Structure of the input file 

The example shows the structure of an input file. First, we need to define the pods
that we will use. This is done by the following attributes:
* *name*: a symbolic name of the pod by which it can be referred to in the connections section, 
  or as pod in the `from` part of a rule. 
* *namespace*: the namespace of the pod
* *podname*: the string that the actual pod name must start with. For instance for deployments,
  pod names are composed of the deployment name followed by a unique id. 

At this moment no other ways of identifying a pod are possible. Future 
versions of the tool could support podSelectors in the same syntax as kubernetes does
in for instance deployment yaml files. Based on a pod identification, a single pod that
matches the specification is chosen. This is to avoid a combinatoric explosion of tests. 

Next, addresses must be defined. Each address has the following fields: 
* *name*: a symbolic name of the address by which it can be referred to in the
  connections section. 
* *hosts*: A list of host names or IP adddresses

Addresses are simply fixed IP addresses or hostnames.
They are an alternative to a pod address which is simply the cluster IP of a pod. 
The difference between a pod and address is that a pod can not only be used as the 
target (server side) of a network check but also as the client part from which a connection
to a server is established. The names of addresses and pods may not conflict. 
In the example above, the `internet` 
address is used which refers to an address, but this could also have been the `name` of 
a pod defined in the pods section. 

The next section defines the connections that can be tested as a combination of pod/address
in the addresses field, and ports:
* *name*: a symbolic name of the connection by which it can be referenced in the 
  rules section of by other connection objects. 
* *addresses*: A list of names of pods or addresses
* *ports*: A list of ports that must be tested. Each port is defined by its `port` which 
  defines the numeric port and by an optional `type` (UDP or TCP) which by default is 
  TCP. 

Finally, the rules section describes from which source pods, the
connections are allowed or denied. In the example above, we specify that the 
`httpd-wamblee-org` pod can connect to the maven repo at ports 80 and 443, but that 
it cannot connect to github.com and google.com: 
* *name*: the name of the rule
* *from*: pod references. Because of pod groups (see later) 
  this can resolve to more than one pod
* *allowed*: A list of connections that are allowed.
* *denied*: A list of connections that are denied. 


### Pod groups

Since it is annoying to repeat the same rules, it is possible to define
groups of pods in the pods section. These pod groups may be referenced just like
any other pod or address using its `name`.

```angular2html
pods:
  - name: httpd-wamblee-org
    namespace: exposure
    podname: httpd-wamblee-org
  - name: httpd-brakkee-org
    namespace: exposure
    podname: httpd-brakkee-org
  # pod group
  - name: all-exposure-pods
    pods:
      - httpd-wamblee-org # refers to earlier pod name
      - httpd-brakkee-org # same...
```

### Address groups

Similar to pod groups address groups can be defined. 

```angular2html
addresses:
  - name: internet
    hosts:
      - github.com
      - google.com 
  - name: dns
    hosts:
      - 192.168.178.1
      - 8.8.8.8
  # address group
  - name: alladdresses
    addresses:
      - internet
      - dns
```

### Protocols

The default protocl is TCP, but UDP may also be specified using the `type` field. 
TCP may also be explicitly specified in this way but it is default. Note however, that 
UDP tests are unreliable. This is because of the nature of UDP. To work around this, a 
future version of this tool could use protocol specific tests for UDP based protocols. 

```angular2html
connections
  - name: dns
    addresses:
    - dns
    ports:
      - port: 53
        type: TCP
      - port: 53
        type: UDP
```

## Test output

The test will output a `junit.xml` file which is suitable for continuous integration.
The test will also show on screen output.

## Under the hood

### Prepare

In the prepare step, the policy tester examines all rules and identifies the pod
specifications that are referenced in the `from` parts of the rules. From each 
pod specification, the pods that match the specification are looked up. If one of 
the pods that is found already contains a debug contqiner than that pod is used. 
Otherwise, the debug container is added to one of these pods, so-called instrumenting
the pod for test. The policy tester only uses
this single pod for testing even when more than one eligble pod was found. 
This is to avoid a combinatoric explosion in testing, and 
also assumes that the network policies are such that it equally effects all pods in 
for the same pod specification. 

Each pod is given a specific label to identify it 
as a pod to which a debug container is added. The label is set before the debug container
is added to make sure we can never have pods with debug containers but without a label. 
This label is used in the cleanup phase to delete pods. 

### Execute

In the execute phase all rules are processed. This means that all source pods 
mentioned in the `from` part of the rule are looked up and for each target connection
in the `allowed` and `denied` sections a command is run in the ephemeral container
that verifies network access. This can be a `netcat` or `nmap` command. 

### Cleanup

In the cleanup phase, the policy tester simply deletes the pods with debug containers 
using the label that was added. 

## Caveats

* incoming network connections cannot be tested by this tool
* UDP tests are, for obvious reasons, not really possible in a generic way. Even though
  policytester supports it, these tests are unreliabnle
* the cleanup phase simply deletes instrumented pods. Your setup must be able to handle
  this. Use this tool on a staging production-like environmnet or use with greatest
  care on a production system. In particular, downtime can occur if you are testing 
  network access from deployments and replicasets with replica count 1. 


