#!/bin/bash

service="pods-compose.service"

cp -v systemd/${service} /etc/systemd/system/
cp -v pods-compose.ini /usr/local/bin/
cp -v pods-compose.py /usr/local/bin/pods-compose
