FROM ubuntu:trusty
MAINTAINER Rail Aliiev <rail@mozilla.com>

# Required software
ENV DEBIAN_FRONTEND noninteractive
# TODO: RUN apt-get update -q && apt-get install -yyq python mercurial wget
RUN apt-get update -q && apt-get install -yyq python git wget
RUN useradd -d /home/worker -s /bin/bash -m worker

# scripts
# TODO: RUN hg clone https://hg.mozilla.org/build/tools /home/worker/tools
RUN git clone https://github.com/rail/build-tools /home/worker/tools/
RUN cd /home/worker/tools && git checkout -b balrog-submitter-partials-only origin/balrog-submitter-partials-only

COPY runme.sh /runme.sh
RUN chmod 755 /runme.sh

ENV           HOME          /home/worker
ENV           SHELL         /bin/bash
ENV           USER          worker
ENV           LOGNAME       worker
