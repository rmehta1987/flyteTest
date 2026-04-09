FROM ubuntu:20.04 AS legacy-blast-builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ncbi-blast+ \
    ncbi-blast+-legacy \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/legacy-blast && \
    cp -f /usr/bin/legacy_blast /usr/bin/blastn /usr/bin/makeblastdb /opt/legacy-blast/ && \
    find /usr/lib /lib -name 'libmbed*.so*' -exec cp -L {} /opt/legacy-blast/ \;

FROM pasapipeline/pasapipeline:2.5.3

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=legacy-blast-builder /opt/legacy-blast/ /usr/local/src/PASApipeline/blast-legacy-bridge/

COPY blastall /usr/local/bin/blastall
COPY formatdb /usr/local/bin/formatdb
RUN chmod 0755 /usr/local/bin/blastall /usr/local/bin/formatdb

RUN command -v seqclean && \
    test -x /usr/local/src/PASApipeline/misc_utilities/accession_extractor.pl && \
    command -v blastall && \
    command -v formatdb

LABEL Author="FLyteTest"
LABEL Description="PASA image with legacy BLAST support for seqclean"
