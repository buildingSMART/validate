#!/bin/sh

git pull
make fetch-modules
sudo make stop
sudo make rebuild
sudo make start
