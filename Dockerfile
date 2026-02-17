FROM ubuntu:latest
LABEL authors="al"

ENTRYPOINT ["top", "-b"]