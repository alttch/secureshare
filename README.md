 secureshare

Simple secure file sharing personal server, Docker/Kubernetes compatible.

## Installing

```
pip3 install secureshare
```

SQL database is required. Supported and tested:

* SQLite
* MySQL
* PostgreSQL

Docker image: https://hub.docker.com/r/altertech/secureshare

(config should be mounted as /config/secureshare.yml)

## Client

https://github.com/alttch/sshare

```
pip3 install sshare
```

## Usage without a client on 3rd party servers:

```
# generate one-time token
sshare c:token
# upload desired file
curl -v -F 'oneshot=1' -F 'file=@path/to/file' -Hx-auth-key:GENERATED_TOKEN https://YOUR_DOMAIN/u
```

## Deleting files / tokens

Uploaded files and tokens can be deleted with DELETE HTTP method (requires
valid key)

Files can be also deleted by specifying *?c=delete* URL ending (requires URL
knowledge only)

## Security

A shared file URL looks like:

```
    http://YOURDOMAIN/d/<ID>/<KEY>/<FILENAME>
```

ID is used to locate file in the storage database. The database stores files
encrypted (AES256), so the server can't decrypt a requested file without the
complete generated URL.

If the URL is lost, file decryption becomes impossible.
