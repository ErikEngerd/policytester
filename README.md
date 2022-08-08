

# Kubernetes Network Policy Tester

Network security is often overlooked in Kubernetes. However, without any network policies 
in place kubernetes deployments are basically identical to a traditional infrastructure 
where tehre is no network segmentation at all. Luckily network policies in Kubernetes
can provide the required network segmentation, see
[the introduction post](https://brakkee.org/site/index.php/2022/07/23/securing-network-communication-on-kubernetes-using-network-policies/).

However, network policies must be verified since it is easy to make a mistake. That is 
where the policy tester comes in. The tool is written in python and uses existing pods 
running in a kubernetes cluster to verify network commmunication. It does this by 
attaching an epehmeral container to an existing pod so it can verify communications from
this pod to other pods and the internet. Ephemeral contains are a beta feature since 
kubernetes 1.24 which allows to add new containers to existing pods. The main purpose of 
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

The current version of the policy tester uses the default kubectl context to connect to.
Future versions of the tool can provide ways to explicitly define a connection to a 
cluster. 

## Documentation

### Verify that a pod can reach the java maven repository at 
`repo1.maven.org` but (most likely) not any other ones. 

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

The example shows the structure of an input file. First of all we need to define the pods
that we will use. This is done by the following attributes:
* *name*: a symbolic name of the pod by which it can be referred to in the connections section.
* *namespace*: the namespace of the pod
* *podname*: the string that the actual pod name must start with. For instance for deployments,
  pod names are composed of the deployment name followed by a unique id. 

At this moment no other ways of identifyin a pod are possible, but in effect future 
versions of the tool could support podSelectors in the same syntax as kubernetes does
in for instance deployment yaml files. 

Next, addresses must be defined. Addresses are simply fixed IP addresses or hostnames.
They are an alternative to a pod address which is simply the cluster IP of a pod.
Therefore, pods and addresses are similar in that they can represent IP addresses. Therefore,
the names of addresses and pods may not conflict. In the example above, the `internet` 
address is used which refers to an address, but this could also have been the `name` of 
a pod defined in the pods section. 

The next section defines the connections that can be tested as a combination of pod/address
in the addresses field, and ports. 

Finally, there si the rules section that describes from which source addresses which 
connections are allowed or denied. In the example above, we specify that the 
`httpd-wamblee-org` pod can connect to the maven repo at ports 80 and 443, but that 
it cannot connect to github.com and google.com. 


### Pod groups

Since it is annoying to repeat the same rules, there is a possibility to define
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
      - httpd-brakkee-org
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

### Test output

The test will output a `junit.xml` file which is suitable for continuous integration, 
as well as some on screen output. 


