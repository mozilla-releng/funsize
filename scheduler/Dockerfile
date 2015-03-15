
FROM ubuntu:trusty
# "Forked" from https://github.com/lightsofapollo/docker-node/blob/master/Dockerfile
MAINTAINER Rail Aliiev <rail@mozilla.com>

ENV DEBIAN_FRONTEND noninteractive
# python is needed for many node operations (gyp)
RUN apt-get install -y python

RUN useradd -d /home/worker -s /bin/bash -m worker

ENV NODE_VERSION v0.12.0

ADD http://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-linux-x64.tar.gz /tmp/node/

RUN tar -C /tmp/node -zxvf /tmp/node/node* && rm /tmp/node/*.tar.gz
RUN cp -R -n /tmp/node/*/* /usr/local
RUN rm -Rf /tmp/node.tar.gz
RUN node -v

COPY . /home/worker/funsize-scheduler
WORKDIR /home/worker/funsize-scheduler
RUN npm install

ENV           HOME          /home/worker
ENV           SHELL         /bin/bash
ENV           USER          worker
ENV           LOGNAME       worker
