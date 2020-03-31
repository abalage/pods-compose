#!/bin/bash

service="pods-compose.service"

cp -v systemd/${service} /etc/systemd/system/
systemctl daemon-reload
systemctl enable ${service}
cp -v pods-compose.* /usr/local/bin/
