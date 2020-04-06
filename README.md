# pods-compose

A wrapper around [Podman](https://github.com/containers/libpod) CLI to provide similar experince for PODs as docker-compose gives to services.

It has a [configuration file](#configuration-of-pods-compose) to store image build descriptions and other settings.

# Synopsis

Usage: **pods-compose** [*options*] [pod]

# Options:
A wrapper around Podman's cli API to mimic basic behavior of docker-compose
```
optional arguments:
  -h, --help            show this help message and exit
  --build               Build container images defined in pods-compose.ini
  --down [DOWN]         Destroy existing pod(s) and container(s)
  --generate [GENERATE] 
                        Generate Kubernetes Pod YAMLs
  --ps                  Show status of pods and containers
  --restart [RESTART]   Restart running pod(s)
  --start [START]       Start existing pod(s)
  --stop [STOP]         Stop existing pod(s)
  --up [UP]             Create pods and containers from Kubernetes Pod YAMLs
```

# Comparison with docker-compose

This script tries to mimic some of docker-compose's features to minimize the learning curve of new users.

It is not a replacement for docker-compose. If you are looking for a replacement for docker-compose then check out [podman-compose](https://github.com/containers/podman-compose).

Here are the similarities and differences between **docker-compose** and **pods-compose**.

| | pods-compose | docker-compose |
| --- | --- | --- |
| Deploy pod(s) | --up [POD] | up [SERVICE] |
| Tear down pod(s) | --down [POD] | down [SERVICE] |
| Start pod(s) | --start [POD] | start [SERVICE] |
| Stop pod(s) | --stop [POD] | stop [SERVICE] |
| Restart pod(s) | --restart [POD] | restart [SERVICE] |
| Build all container images | --build | build |
| Status of pods and containers | --ps | ps |
| Generate Kubernetes Pod YAML(s) | --generate [POD] | |

## Install

tl;dr: Adjust *kubedir* in **pods-compose.ini** then execute [install.sh](install.sh). This directory should be writable by the running user.

### Configuration of pods-compose
The tool itself has a configuration file to set a couple of settings.

- *kubedir* - A permanent directory where the generated YAMLs will be placed.
- *basedir* - The parent directory of image build contexts.
- *default_tag* - Simplifies maintaining generated YAMLs. Do not set it to "latest". Defaults to 'prod'.

The configuration file is placed next to the executable and called **pods-compose.ini**.

#### Define which images should be built

In [pods-compose.ini](pods-compose.ini) you can add image build descriptions according to the commented examples.

You just need to make sure that all has the prefix of **"image_"**. The value will be separated by a single comma to TAG and CONTEXT. CONTEXT is expected to be a directory and must contain either a Dockerfile or a Containerfile.

#### Autostart of pods and containers upon system reboot
As Podman is daemonless, there is no system daemon which should start pods and containers upon reboot.
To achieve that one can create a systemd service unit to start the deployment automatically. An example of [pods-compose.service](systemd/pods-compose.service) is included in the repo.

The provided [install.sh](install.sh) script will install it for you. In order to systemd recognize it, you have to run these commands.
```
# systemctl daemon-reload
# systemctl enable pods-compose.service
```

##### Overriding mounts
Should your deployment depends on other mount points (like NFS, 9p) to be available, then add them to an systemd unit override.

You can do it like this:
```
# systemctl edit pods-compose.service

[Unit]
After= srv.mount
```

## Deploying pods and containers

**docker-compose** uses a YAML file for describing and managing services. Normally you have create one manually.

**pods-compose** also relies on YAML files for describing pods and containers, however you do not have to create them manually.

1. You need to [create pods and containers](#1-describe-pods-and-containers) using the command line interface of Podman. The CLI is well documented and mostly behaves the same way as [docker CLI](https://podman.io/whatis.html) does.
2. Then use pod-compose to generate [Kubernetes Pod YAML](https://github.com/containers/libpod/blob/master/docs/source/markdown/podman-generate-kube.1.md) files for each pod.
3. The YAMLs will be used to deploy your pods and containers with '**--up**'.

### 1. Describe pods and containers

Although you can do this manually, the following scripts will show an example of deploying two pods containing Nextcloud (and its dependencies) and a reverse proxy. Notice how similar the CLI arguments are compared to Docker's CLI arguments.

```bash
#!/bin/bash

podname="nextcloud"
publish_ip="10.88.0.1"

podman pod rm -f ${podname}
podman pod create --name ${podname} --hostname ${podname} -p ${publish_ip}:8080:80

podman run -d --name nextcloud-php --hostname nextcloud-php --expose 9000 --pod ${podname} \
    -v /srv/www/nextcloud:/var/www \
    localhost/example/php74-fpm-debian:prod

podman run -d --name nextcloud-www --hostname nextcloud-www --expose 80 --pod ${podname} \
    -v /var/containers/config/nginx/backend_nextcloud/conf.d/nextcloud.conf:/etc/nginx/conf.d/default.conf:ro \
    -v /var/containers/config/nginx/backend_nextcloud/nginx.conf:/etc/nginx/nginx.conf:ro \
    -v /srv/www/nextcloud:/var/www \
    nginx:1.16

podman run -d --name nextcloud-redis --hostname nextcloud-redis --expose 6379 --pod ${podname} \
    -v /var/containers/volumes/redis:/data \
    redis:5
```
And another pod with a single Nginx container as a reverse proxy.

```bash
#!/bin/bash

podname="reverse_proxy"
publish_ip="1.2.3.4"

podman pod rm -f ${podname}
podman pod create --name ${podname} --hostname ${podname} -p ${publish_ip}:80:80 -p ${publish_ip}:443:443

podman run -d --name proxy --hostname proxy --expose 80 --expose 443 --pod ${podname} \
    -v /var/containers/config/nginx/proxy/conf.d/reverse_proxy.conf:/etc/nginx/conf.d/default.conf:ro \
    nginx:1.16
```

You can read more about **publish IPs** is the following blog: [Convert docker-compose services to pods with Podman](https://balagetech.com/convert-docker-compose-services-to-pods/)
### 2. Generate Kubernetes Pod YAML definitions

Once you have your pods defined, let's create a snapshot of their description in YAMLs.

```bash
# pods-compose --generate
Generating YAML file for pod 'nextcloud'
Generating YAML file for pod 'reverse_proxy'
```

### 3. Deploy and destroy

You may want to throw away your local pods to avoid any issues and simply rely on the generated YAMLs.

```bash
# pods-compose --down
Tear down pods 'nextcloud reverse_proxy'
```

```bash
# pods-compose --up
Replay Kubernetes YAML for pod 'nextcloud'
Replay Kubernetes YAML for pod 'reverse_proxy'
```

