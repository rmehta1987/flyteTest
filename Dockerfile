FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    fastqc \
    salmon \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root

COPY requirements.txt /root/requirements.txt
RUN pip install --no-cache-dir -r /root/requirements.txt

COPY src /root/src
COPY flyte_rnaseq_workflow.py /root/flyte_rnaseq_workflow.py
