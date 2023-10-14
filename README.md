# buildingSMART validation service

ifc-pipeline is a processing queue that uses [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell/) to convert IFC input files into a graphic display using glTF 2.0 and [BIMSurfer2](https://github.com/AECgeeks/BIMsurfer2/) for visualization. There is a small web application in Flask that accepts file uploads. HTTPS is provided by Nginx. Everything is tied together using Docker Compose.

## Validation

For buildingSMART international, ifc-pipeline has been adapted to perform IFC file validation on (currently) 4 levels:

1. IFC-SPF syntax using https://github.com/IfcOpenShell/step-file-parser
2. Schema validation ([inverse] attribute types and cardinalities) using https://github.com/IfcOpenShell/IfcOpenShell/blob/v0.7.0/src/ifcopenshell-python/ifcopenshell/validate.py
3. Informal Propositions (IP) and Implementer Agreements (IA) using behavioural driven development and the Gherkin language
4. bSDD integrity

## Architecture

![](ifc-pipeline-validation-architecture.png)

The service is deployed using docker compose. 

The deployment consists of a python front-end and worker(s) (using the same underlying docker container), nginx proxy, postgres database and redis for implementing a synchronised task queue.

Uploaded models are stored on disk.

The worker executes a series of validation tasks on the models. These are all modules that can act as stand-alone code repositories in themselves. For the purpose of the validation service, they each have an associated runner task that knows how to invoke the module, capture output and write to the database.

## Database schema

![](db-schema.png)

## Usage

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

## Running `psql`

~~~
docker exec -it $(docker ps -q --filter name=db) psql -U postgres bimsurfer2
~~~

### Observability notes

#### Uploads per day

```sql
select date_trunc('day', models.date) as day, count(*) as num_uploads from models group by date_trunc('day', models.date) order by day desc;
```

```bash
sudo docker exec -it $(sudo docker ps -q --filter name=db) psql -P pager=off -tA -F, -U postgres bimsurfer2 -c "select date_trunc('day', models.date) as day, count(*) as num_uploads from models group by date_trunc('day', models.date) order by day desc;" > uploads_per_day.csv
```

```python
import matplotlib.pyplot as plt
import datetime

fn = 'uploads_per_day.csv'
lns = [l.strip().split(',') for l in open(fn) if l.strip()]
t0 = datetime.datetime.strptime(lns[-1][0].split(' ')[0], '%Y-%m-%d')
xs = [(datetime.datetime.strptime(l[0].split(' ')[0], '%Y-%m-%d') - t0).days for l in lns]
ys = [int(l[1]) for l in lns]
plt.plot(xs, ys)
plt.savefig('uploads-per-day.png')
```

### Runtime of checks

```sql
select models.size, task_type, extract(epoch from  validation_end_time - validation_start_time) as time  from models, validation_tasks where models.id=validation_tasks.validated_file and not validation_end_time is
null order by date desc;
```

```bash
sudo docker exec -it $(sudo docker ps -q --filter name=db) psql -P pager=off -tA -F, -U postgres bimsurfer2 -c "select code, models.size, task_type, extract(epoch from  validation_end_time - validation_start_time) as time from models, validation_tasks where models.id=validation_tasks.validated_file and not validation_end_time is null order by date desc;" > check_runtime.csv
```

```python
import matplotlib.pyplot as plt
from itertools import groupby
from collections import defaultdict

plt.figure(figsize=(16,9))

fn = 'check_runtime.csv'
di = {'syntax_validation_task': 'syntax', 'bsdd_validation_task' : 'bsdd', 'informal_propositions_task' : 'rules', 'schema_validation_task' : 'schema', 'implementer_agreements_task' : 'rules'}
lns = [l.strip().split(',') for l in open(fn) if l.strip()]
m = defaultdict(lambda: defaultdict(float))
for ln in lns:
    m[ln[0]][di[ln[2]]] += float(ln[3])

def to_bytes(s):
    if not s.strip(): return 0
    n, u = s.split(' ')
    return float(n) * {'B' : 1, 'KB': 1024, 'MB': 1024 * 1024, 'GB': 1024 * 1024 * 1024}[u] / 1024 / 1024

sz = {x[0]: to_bytes(list(x[1])[0][1]) for x in groupby(lns, key=lambda l: l[0])}
xs = [sz[k] for k in m.keys()]

for l in set(di.values()):
    ys = [dd.get(l, 0.) for dd in m.values()]
    plt.scatter(xs, ys, label=l)

plt.legend()

plt.savefig('runtime-of-checks.png')
```

### Queue time of checks

```sql
select extract(epoch from validation_start_time - models.date) as time from models, validation_tasks where models.id=validation_tasks.validated_file and not validation_end_time is
null and task_type = 'syntax_validation_task' order by date desc;
```
