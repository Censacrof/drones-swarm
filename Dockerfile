FROM ghcr.io/censacrof/netlogo-nl4py:latest
COPY sciadro-3.1/ .
CMD python3 differntial_evolution/differential_evolution.py \
    /netlogo \
    SCD\ src.nlogo \
    fire1 \
    differntial_evolution/parameters.json
