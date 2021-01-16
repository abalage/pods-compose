#!/usr/bin/python3

# Make sure your only locally existing images do not have :latest tag as it will try to alway pull and fail
# during --up
# https://github.com/containers/libpod/blob/1be61789151c80d46c0c4b75a02fb23a6937df7b/pkg/adapter/pods.go#L709

from subprocess import Popen, PIPE
import sys
import argparse
import os
import os.path
import configparser

INIFILE = 'pods-compose.ini'
DOTFILE = '.'+ INIFILE
HOME = os.path.expandvars("$HOME")
ETC = "/etc/pods-compose"
SCRIPT_LOC = os.path.dirname(os.path.abspath(__file__))
for location in HOME, ETC, SCRIPT_LOC:
    CONFIGFILE = os.path.join(location, INIFILE)
    if os.path.exists(CONFIGFILE): break
    if location == HOME:
        CONFIGFILE = os.path.join(location, DOTFILE)
        if os.path.exists(CONFIGFILE): break

config = configparser.ConfigParser()
config.read(CONFIGFILE)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="A wrapper around podman's cli API to mimic basic behavior of docker-compose")

    parser.add_argument(
        "--build", help="Build container images defined in pods-compose.ini", action="store_true")
    parser.add_argument("--down", nargs="?", const="all",
                        help="Destroy existing pod(s) and container(s)")
    parser.add_argument("--generate", nargs="?", const="all",
                        help="Generate Kubernetes Pod YAMLs")
    parser.add_argument(
        "--ps", help="Show status of pods and containers", action="store_true")
    parser.add_argument("--restart", nargs="?", const="all",
                        help="Restart running pod(s)")
    parser.add_argument("--start", nargs="?", const="all",
                        help="Start existing pod(s)")
    parser.add_argument("--stop", nargs="?", const="all",
                        help="Stop existing pod(s)")
    parser.add_argument("--up", nargs="?", const="all",
                        help="Create pods and containers from Kubernetes Pod YAMLs")
    #parser.add_argument("--update", nargs="?", const="all", help="update container images")

    args = parser.parse_args()

    ####### skip #######

    def get_containerimage_configs():
        import re
        images = []
        p = re.compile('^image_.+$')
        # 'builds' should contain config items starting with "image_"
        # they represent a list, first item is a tag, second is the directory of the image description (Containerfile)
        for key in config['builds']:
            if p.match(key):
                images.append(config['builds'][key])

        return images

    def runcmd(text, cmd, echo):
        # https://stackoverflow.com/questions/2715847/read-streaming-input-from-subprocess-communicate
        if echo in ['Y', 'Yes', 'yes']:
            print(text)
        stdout = []
        with Popen([cmd],
                   shell=True,
                   stdout=PIPE,
                   bufsize=1,
                   universal_newlines=True
                   ) as process:

            for line in process.stdout:
                if echo in ['Y', 'Yes', 'yes']:
                    print(line, end='')

                line = line.rstrip()
                stdout.append(line)

        return stdout

    def get_pods_by_name():
        pods = runcmd("Existing pods:",
                      '/usr/bin/podman pod ls --format "{{.Name}}"', "no")
        return pods

    def find_yamls_in_dir(directory):
        iterator = os.scandir(path=directory)
        yamls = []
        for DirEntry in iterator:
            filename, extension = os.path.splitext(DirEntry.name)
            if extension == ".yml":
                yamls.append(DirEntry.name)

        return yamls

    ####### return to argparse #######

    if (args.ps):
        runcmd("Status of running pods:", '/usr/bin/podman pod ls', "yes")
        runcmd("Status of running containers:",
               "/usr/bin/podman ps -p --format 'table {{.ID}} {{.Names}} {{.PodName}} {{.Status}}'", "yes")

    elif (args.start):
        pods = ' '.join(get_pods_by_name()
                        ) if args.start == "all" else args.start
        runcmd("Starting pods '" + pods + "'",
               "/usr/bin/podman pod start " + pods, "yes")

    elif (args.stop):
        pods = ' '.join(get_pods_by_name()
                        ) if args.stop == "all" else args.stop
        runcmd("Stopping pods '" + pods + "'",
               "/usr/bin/podman pod stop " + pods, "yes")

    elif (args.restart):
        pods = ' '.join(get_pods_by_name()
                        ) if args.restart == "all" else args.restart
        runcmd("Restarting pods '" + pods + "'",
               "/usr/bin/podman pod restart " + pods, "yes")

    elif (args.down):
        pods = ' '.join(get_pods_by_name()
                        ) if args.down == "all" else args.down
        runcmd("Tear down pods '" + pods + "'",
               "/usr/bin/podman pod rm -f " + pods, "yes")

    elif (args.build):
        images = get_containerimage_configs()
        for image in images:
            tag, context = image.split(',')
            # FIXME input validation on tag is missing
            if os.path.exists(context):
                runcmd("Building image '" + tag + "' from context " + context,
                       "/usr/bin/podman build -t " + tag + " " + context, "yes")
            else:
                print("Context does not exist: {}".format(context))
                sys.exit(1)

    elif (args.up):
        from pathlib import Path
        kubedir = Path(config['DEFAULT']['kubedir'])
        kubes = find_yamls_in_dir(kubedir)
        if not kubes:
            print("No Kubernetes YAMLs found in directory: {}".format(kubedir))

        # TODO if replay fails then delete the pod anyway

        def _up_kube(kube):
            kubeyml = kubedir / kube
            networks = config['DEFAULT']['networks']
            netcmd = str()
            if networks:
                netcmd = " --network " + networks
            if kubeyml.exists():
                rc = runcmd("Replay Kubernetes YAML for pod '" + kube +
                            "'", "/usr/bin/podman play kube " + str(kubeyml) + netcmd, "yes")
            return rc

        # podman play kube only accepts a single yaml file, so we have to iterate
        if args.up == "all":
            for kube in kubes:
                _up_kube(kube)
        else:
            # just provide the pod's name and I will add the extension
            kube = args.up + ".yml"
            _up_kube(kube)

    elif (args.generate):
        from pathlib import Path
        kubedir = Path(config['DEFAULT']['kubedir'])
        # Check post for limitations: https://developers.redhat.com/blog/2019/01/29/podman-kubernetes-yaml/

        if not kubedir.is_dir():
            kubedir.mkdir(mode=0o755, parents=True)

        def _generate_kube(pod):
            podyml = pod + ".yml"
            kubename = kubedir / podyml
            if kubename.exists():
                kubename.unlink()
            rc = runcmd("Generating YAML file for pod '" + pod + "'",
                        "/usr/bin/podman generate kube -f " + str(kubename) + " " + str(pod), "yes")
            return rc

        # podman generate kube only accepts a single pod or container, so we have to iterate
        if args.generate == "all":
            pods = get_pods_by_name()
            for pod in pods:
                _generate_kube(pod)
        else:
            pod = args.generate
            _generate_kube(pod)
    else:
        print(args)
