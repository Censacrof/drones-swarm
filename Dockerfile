FROM openjdk:8-jdk
WORKDIR /netlogo
RUN wget https://ccl.northwestern.edu/netlogo/6.2.2/NetLogo-6.2.2-64.tgz \
    && tar zxvpf NetLogo-6.2.2-64.tgz \
    && rm NetLogo-6.2.2-64.tgz \
    && mv NetLogo\ 6.2.2/* . \
    && rm -rf mv NetLogo\ 6.2.2
WORKDIR /app
RUN apt-get update -y
RUN apt-get install -y python3
RUN apt-get install -y python3-pip
COPY python-requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY sciadro-3.1/ .
CMD python3 differntial_evolution/differential_evolution.py \
    /netlogo \
    SCD\ src.nlogo \
    fire1 \
    differntial_evolution/parameters.json