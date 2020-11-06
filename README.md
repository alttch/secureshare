# SecureShare

Simple secure file sharing personal server, Docker/Kubernetes compatible.
SecureShare can share any text information (pastebin-like) and small binary
files as well.

## What is SecureShare

SecureShare allows quickly and securely share small files, documents and
command pipe outputs. The files are uploaded via HTTP POST to your host or
SecureShare Kubernetes pod, encrypted and securely stored inside the database.

After the server returns you the shared HTTP URL. It's not possible to retrieve
uploaded file contents without the URL, as the file content is AES256-encrypted
inside the database.

The URLS can be one-shot (self-destructing after the first access). Also, all
URLs expire after the specified period of time.

SecureShare is useful for:

* sharing sensitive data with co-workers/customers
* requesting sensitive data from co-workers/customers
* get rid of garbage-full public "exchange" directories.

SecureShare isn't yet-another cloud service. You run your own secure dedicated
instance, on any Linux system or inside K8S-cluster.

<img src="https://github.com/alttch/secureshare/blob/main/media/demo.gif?raw=true" width="750" />

## Installing

```
pip3 install secureshare
# install gunicorn for Python3, if not present in system
pip3 install gunicorn
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

## Launching server

Use *secureshare-control* script to manage the server.

## Using client

Secure sharing files from the command line has never been easier:

```
# share a file
sshare path/to/file
```

```
# share a file with self-destructing one-shot link
sshare path/to/file -s
```

```
# share a command output
cat /etc/passwd | sshare
# don't share that ;)
```

## Usage without a client on 3rd party servers:

```
# generate one-time token (on a trusted system)
sshare c:token
```

```
# upload desired file with generated token (on an untrusted system)
curl -v -F 'oneshot=1' -F 'file=@path/to/file' -Hx-auth-key:GENERATED_TOKEN https://YOUR_DOMAIN/u
```

## API

### Authentication

Set *X-Auth-Key* HTTP header to *upload-key* value from the server config.
There's only one upload / management key (at this moment) but one-time tokens
can be additionally generated.

### Generating new one-time token

A HTTP POST request to /api/v1/token will return new one-time authentication
token, arguments:

* **expires** set token expiration time (in seconds from now), optional

### Uploading

Send files as multipart MIME forms POST requests to 

```
    http://YOURDOMAIN/u
```

with arguments:

* **file** file data (required)
* **oneshot=1** generate one-shot (self-destructing) link
* **expires** set link expiration time (in seconds from now)
* **fname** override file name
* **sha256sum** ask server to check SHA256 sum of the received file
* **raw=1** store raw (don't encrypt) file in DB. Useful for already encrypted
  data.

### Deleting files / tokens

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
encrypted, so the server can't decrypt a requested file without the complete
generated URL.

If the URL is lost, file decryption becomes impossible.

### Previews

When sharing links with messengers, they may fetch content for preview, which's
insecure and may destroy one-shot links. The following messenger user agents
are banned automatically:

* WhatsApp
* Viber
* Telegram
* Facebook Messenger
* Skype

The list is located in secureshare/server.py BANNED_AGENTS variable (send me a
pull request to extend).

## WebUI

Maybe later.

## Size limits

SecureShare is created to securely share small files < 100MB. Sharing larger
files isn't recommended, as it may produce DB / encryption overheads.
