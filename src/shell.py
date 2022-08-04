
import subprocess

class Cmd:
    def __init__(self, cmd):
        self.cmd = cmd

    def status(self):
        return self.proc.wait()

    def __enter__(self):
        self.proc = subprocess.Popen(["sh", "-c", self.cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return self

    def __iter__(self):
        for line in self.proc.stdout:
            yield line.decode("UTF-8").rstrip("\n")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.proc.__exit__(exc_type, exc_val, exc_tb)


def get_pods(condition):
    res = []
    with Cmd("""
        kubectl get pods -A | 
        awk 'NR > 1 { print $1 " " $2}'
        """) as cmd:
        for line in cmd:
            print(line)
            namespace, name = line.split()
            if condition(namespace, name):
                res.append((namespace, name))

    return res, cmd.status()



res = get_pods(lambda ns,n: ns == "exposure")
print(res)
