# READ ME

## A few things to look out for

### SSL

Replace  the `https` with `http` depeneding on whether or not you're using SSL in the index.html page under templates.

```
socket = io.connect('https://' + document.domain + ':' + location.port);
```

### To run on the language server, do:

```
source ~/.bashrc; source activate gan-server; gunicorn -k gevent -w 1 -b 127.0.0.1:1234 server:app;
```