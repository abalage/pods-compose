# pods-compose

A wrapper around podman CLI to provide similar experince for PODs as docker-compose gives to services.

It has a [configuration file](#configuration-of-pods-compose) to store image build descriptions and other settings.

# Synopsis

Usage: **pods-compose** [*options*] [pod]

# Options:
```
optional arguments:
  -h, --help            show this help message and exit
  --build               build container images
  --up [UP]             create and start pods by using kubectl YMLs
  --down [DOWN]         tear down existing pods
  --start [START]       start up existing pods
  --stop [STOP]         stop existing pods
  --restart [RESTART]   restart running pods
  --ps                  show status of running pods and containers
  --generate [GENERATE]
                        generate kube YMLs
```

# Comparison with docker-compose

The design goas was to following the [KISS principle](https://en.wikipedia.org/wiki/KISS_principle) and mimic docker-compose's behavior as much as possible to minimize the learning curve of new users.

Here are the similarities and differences **pods-compose** supports.

| | pods-compose | docker-compose |
| --- | --- | --- |
| Deploy pod(s) | --up [POD] | up [SERVICE] |
| Tear down pod(s) | --down [POD] | down [SERVICE] |
| Start pod(s) | --start [POD] | start [SERVICE] |
| Stop pod(s) | --stop [POD] | stop [SERVICE] |
| Restart pod(s) | --restart [POD] | restart [SERVICE] |
| Build container images | --build | build |
| Status of pods and containers | --status | |
| Generate Kubernetes Pod YAML(s) | --generate [POD] | |

## Deployment of PODs

tl;dr: You must [create pods and containers](#describe-pods-and-containers) with podman CLI and snapshot their descriptions in [Kubernetes Pod YAMLs](https://github.com/containers/libpod/blob/master/docs/source/markdown/podman-generate-kube.1.md) with pods-compose to be able to deploy them.

**docker-compose** uses a YML file for describing and managing services. Normally you create one manually.

**pods-compose** also relies on YML files for describing pods and containers, however you do not have to create them manually.

You need to create your pods and containers by using the command line interface of podman.
The CLI is well documented and mostly behaves the same way as [docker CLI](https://podman.io/whatis.html) does.

Then pod-compose generates Kubernetes compatible YML files for each pod and uses them to deploy your pods and containers.

### Describe pods and containers

Although you can do this manually, the following scripts will show an example of deploying two pods containing Nextcloud (and its dependencies) and a reverse proxy.

Notice how similar the CLI arguments are compared to Docker's CLI arguments.

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
And another pod with a single Nginx containers as a reverse proxy.

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

You can read more about **publish IPs** is the following blog. "[Convert docker-compose services to pods with podman](https://balagetech.com/convert-docker-compose-services-to-pods/)"
### Generate Kubernetes Pod YAML definitions

Once you have your pods defined, let's create a snapshot of their description in YAMLs.

```bash
# pods-compose --generate
Generating YML file for pod 'nextcloud'
Generating YML file for pod 'reverse_proxy'
```

All the YAML files are saved in *kubedir* defined in [pods-compose.ini](#configuration-of-pods-compose)

### Deploy and destroy

You may want to throw away your local pods to avoid any issues.

```bash
# pods-compose --down
Tear down pods 'nextcloud reverse_proxy'
```

```bash
# pods-compose --up
Replay Kubernetes YAML for pod 'nextcloud'
Replay Kubernetes YAML for pod 'reverse_proxy'
```

### Building container images
In the [configuration file](#configuration-of-pods-compose) you can set which container images should be built by using the **--build** option.

You can use the commented example as a basis.
```ini
[builds]
#image_php = example/php74-fpm-debian:%(default_tag)s,%(basedir)s/containerfiles/php74-fpm/php-upstream-debian
```

**Notice:** The configuration key must have an **"image_"** prefix. The value is separated by a single comma to TAG and CONTEXT. CONTEXT is expected to be a directory and must contain either a Dockerfile or a Containerfile.

### Autostart of pods and containers upon system reboot
As podman is daemonless, there is no system daemon which should start pods and containers upon reboot.
To achieve that we must create a systemd service unit for pods-compose to start up our deployment.

**pods.compose.service**
```
[Unit]
Description=Deploy all my pods
After=var.mount var-cache.mount usr.mount usr-share.mount

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh /usr/local/bin/pods-compose --up
ExecStop=/bin/sh /usr/local/bin/pods-compose --down

[Install]
WantedBy=multi-user.target
```

#### Overriding mounts
You may need to add more *.mount* arguments to *After=* in case your volumes reside on special mounts like NFS or 9p.

You can do it like this:
```
# systemctl edit pods-compose.service

>[Unit]
After= srv.mount
```

Place the service unit file into **/etc/systemd/system/pods-compose.service** and enable it.
```
# systemctl daemon-reload
# systemctl enable pods-compose
```

## Configuration of pods-compose
The tool itself has a configuration file to set a couple of settings like where to put the generated YAMLs or how to build container images.

The configuration file is placed next to the executable and called *pods-compose.ini*.

### Define which images should be built

Open up pods-compose.ini and add more options

