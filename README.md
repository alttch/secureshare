 secureshare

Simple secure file sharing personal server, Docker/Kubernetes compatible.

## Installing:

```
pip3 install secureshare
```

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
