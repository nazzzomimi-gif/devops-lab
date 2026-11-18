FROM public.ecr.aws/docker/library/python:3.11-alpine
WORKDIR /app
RUN pip install --no-cache-dir flask redis
COPY app.py .
CMD ["python", "app.py"]
