ifc-pipeline
------------

A processing queue that uses [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell/) to convert IFC input files into a graphic display using glTF 2.0 and [BIMSurfer2](https://github.com/AECgeeks/BIMsurfer2/) for visualization.

There is a small web application in Flask that accepts file uploads. HTTPS is provided by Nginx. Everything is tied together using Docker Compose.

~~~
./init.sh my.domain.name.com
docker-compose up -d
~~~

## Development notes

Remember to store credentials as environment variables in `/etc/environment`

### Nginx proxy on dev server

~~~
apt install nginx snapd
snap install --classic certbot
certbot --nginx
~~~

Add section below to /etc/nginx/sites-enabled/default

~~~
        client_max_body_size 4G;
        keepalive_timeout 5;


        location @app {
        proxy_pass http://localhost:5000;
        proxy_redirect off;

        proxy_set_header   Host                 $http_host;
        proxy_set_header   X-Real-IP            $remote_addr;
        proxy_set_header   X-Forwarded-For      $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto    $scheme;
    }
~~~ 

Comment out lines (not consecutive in file)

~~~
root /var/www/html;
index index.html index.htm index.nginx-debian.html;
~~~

Change to

~~~
try_files $uri @app;
~~~

Finally run to restart nginx

~~~
systemctl restart nginx
~~~

Start flask with

~~~
./run_local.sh
~~~
