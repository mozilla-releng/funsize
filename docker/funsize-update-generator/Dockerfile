FROM ubuntu:trusty
MAINTAINER Rail Aliiev <rail@mozilla.com>

RUN useradd -d /home/worker -s /bin/bash -m worker

COPY runme.sh /runme.sh
RUN chmod 755 runme.sh

ENV           HOME          /home/worker
ENV           SHELL         /bin/bash
ENV           USER          worker
ENV           LOGNAME       worker
