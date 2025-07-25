ARG NETBOX_BASE_IMAGE=docker.io/netboxcommunity/netbox:v3.2.9

FROM ${NETBOX_BASE_IMAGE} as netbox-test

USER 0

RUN pip install coverage==7.2.7

USER 999 