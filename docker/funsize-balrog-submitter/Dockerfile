FROM ubuntu:trusty
MAINTAINER Rail Aliiev <rail@mozilla.com>

# Required software
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update -q && apt-get install -yyq python mercurial wget
RUN hg clone https://hg.mozilla.org/build/tools /home/worker/tools

RUN \
    for url in \
      https://pypi.python.org/packages/source/b/boto/boto-2.38.0.tar.gz \
      https://pypi.python.org/packages/source/c/certifi/certifi-2015.04.28.tar.gz; do \
        wget -O- $url | tar -C /home/worker/tools/lib/python/vendor -xzf -; done


RUN useradd -d /home/worker -s /bin/bash -m worker

RUN mkdir /home/worker/bin
COPY scripts/* /home/worker/bin/
COPY runme.sh /runme.sh
RUN chmod 755 /home/worker/bin/* /runme.sh

ENV           HOME          /home/worker
ENV           SHELL         /bin/bash
ENV           USER          worker
ENV           LOGNAME       worker
