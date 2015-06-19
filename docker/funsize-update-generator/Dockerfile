FROM ubuntu:vivid
MAINTAINER Rail Aliiev <rail@mozilla.com>

# Required software
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -q && \
    apt-get install -yyq python python-pip python-cryptography \
    clamav clamav-freshclam
RUN useradd -d /home/worker -s /bin/bash -m worker
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
# cleanup
RUN apt-get purge -y python-pip && apt-get autoremove -y
RUN rm -f /tmp/requirements.txt

# scripts
RUN mkdir /home/worker/bin
COPY scripts/* /home/worker/bin/
COPY runme.sh /runme.sh
RUN chmod 755 /home/worker/bin/* /runme.sh
RUN mkdir /home/worker/keys
COPY *.pubkey /home/worker/keys/
RUN freshclam --verbose

ENV           HOME          /home/worker
ENV           SHELL         /bin/bash
ENV           USER          worker
ENV           LOGNAME       worker
