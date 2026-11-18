FROM public.ecr.aws/nginx/nginx:alpine
RUN echo '<meta charset="utf-8"><h1 style="color: #00aa00;">Привет из Docker-контейнера!</h1><p>Собрано вручную в DevOps Lab.</p>' > /usr/share/nginx/html/index.html
